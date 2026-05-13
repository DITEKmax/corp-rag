package com.corprag.service.outbox;

import com.corprag.contracts.constants.EventRoutingKeys;
import com.corprag.contracts.constants.ExchangeNames;
import com.corprag.domain.DocumentRecord;
import com.corprag.domain.OutboxEventRecord;
import com.corprag.repository.OutboxEventRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class OutboxService {

    private static final String EVENT_VERSION = "1.0.0";
    private static final String SOURCE_SERVICE = "corp-rag-backend";

    private final OutboxEventRepository outboxEventRepository;
    private final ObjectMapper objectMapper;

    public OutboxService(OutboxEventRepository outboxEventRepository, ObjectMapper objectMapper) {
        this.outboxEventRepository = outboxEventRepository;
        this.objectMapper = objectMapper;
    }

    public OutboxEventRecord createDocumentUploaded(DocumentRecord document, UUID correlationId, Instant occurredAt) {
        UUID eventId = UUID.randomUUID();
        OutboxEventRecord event = new OutboxEventRecord(
                eventId,
                "DOCUMENT",
                document.id(),
                EventRoutingKeys.DOCUMENT_UPLOADED,
                EventRoutingKeys.DOCUMENT_UPLOADED,
                ExchangeNames.DOCUMENTS_TOPIC,
                json(envelope(eventId, correlationId, occurredAt, document)),
                json(headers(correlationId)),
                correlationId,
                occurredAt,
                null,
                0,
                null,
                occurredAt);
        outboxEventRepository.insert(event);
        return event;
    }

    private static Map<String, Object> envelope(
            UUID eventId,
            UUID correlationId,
            Instant occurredAt,
            DocumentRecord document) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("documentId", document.id());
        payload.put("title", document.title());
        payload.put("ownerUserId", document.ownerUserId());
        payload.put("contentSha256", document.contentSha256());
        payload.put("accessLevel", document.accessLevel().name());
        payload.put("department", document.department());
        payload.put("docType", document.docType().name());
        payload.put("language", document.language());
        payload.put("minioBucket", document.storageBucket());
        payload.put("minioObjectKey", document.storageKey());
        payload.put("mimeType", document.mimeType());
        payload.put("sizeBytes", document.sizeBytes());
        payload.put("originalFilename", document.originalFilename());
        payload.put("uploadedAt", document.uploadedAt());

        return Map.of(
                "metadata", Map.of(
                        "eventId", eventId,
                        "eventType", EventRoutingKeys.DOCUMENT_UPLOADED,
                        "eventVersion", EVENT_VERSION,
                        "occurredAt", occurredAt,
                        "correlationId", correlationId,
                        "sourceService", SOURCE_SERVICE),
                "payload", payload);
    }

    private static Map<String, Object> headers(UUID correlationId) {
        return Map.of(
                "x-correlation-id", correlationId,
                "x-event-type", EventRoutingKeys.DOCUMENT_UPLOADED,
                "x-event-version", EVENT_VERSION);
    }

    private String json(Map<String, Object> value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Could not serialize outbox event", exception);
        }
    }
}
