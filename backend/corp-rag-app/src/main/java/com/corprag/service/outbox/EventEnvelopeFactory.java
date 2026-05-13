package com.corprag.service.outbox;

import com.corprag.adapter.amqp.AmqpHeaderNames;
import com.corprag.contracts.constants.EventRoutingKeys;
import com.corprag.contracts.constants.ExchangeNames;
import com.corprag.domain.DocumentRecord;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Component;

@Component
public class EventEnvelopeFactory {

    static final String EVENT_VERSION = "1.0.0";
    static final String SOURCE_SERVICE = "corp-rag-backend";

    private final ObjectMapper objectMapper;

    public EventEnvelopeFactory(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public EventEnvelope documentUploaded(DocumentRecord document, UUID correlationId, Instant occurredAt) {
        UUID eventId = UUID.randomUUID();
        return new EventEnvelope(
                eventId,
                EventRoutingKeys.DOCUMENT_UPLOADED,
                EventRoutingKeys.DOCUMENT_UPLOADED,
                ExchangeNames.DOCUMENTS_TOPIC,
                json(envelope(metadata(eventId, EventRoutingKeys.DOCUMENT_UPLOADED, correlationId, occurredAt),
                        uploadedPayload(document))),
                json(headers(correlationId, EventRoutingKeys.DOCUMENT_UPLOADED)));
    }

    public EventEnvelope documentDeleted(
            DocumentRecord document,
            UUID deletedBy,
            UUID correlationId,
            Instant deletedAt) {
        UUID eventId = UUID.randomUUID();
        return new EventEnvelope(
                eventId,
                EventRoutingKeys.DOCUMENT_DELETED,
                EventRoutingKeys.DOCUMENT_DELETED,
                ExchangeNames.DOCUMENTS_TOPIC,
                json(envelope(metadata(eventId, EventRoutingKeys.DOCUMENT_DELETED, correlationId, deletedAt),
                        deletedPayload(document.id(), deletedBy, deletedAt))),
                json(headers(correlationId, EventRoutingKeys.DOCUMENT_DELETED)));
    }

    private static Map<String, Object> metadata(
            UUID eventId,
            String eventType,
            UUID correlationId,
            Instant occurredAt) {
        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("eventId", eventId);
        metadata.put("eventType", eventType);
        metadata.put("eventVersion", EVENT_VERSION);
        metadata.put("occurredAt", occurredAt);
        metadata.put("correlationId", correlationId);
        metadata.put("sourceService", SOURCE_SERVICE);
        return metadata;
    }

    private static Map<String, Object> uploadedPayload(DocumentRecord document) {
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
        return payload;
    }

    private static Map<String, Object> deletedPayload(UUID documentId, UUID deletedBy, Instant deletedAt) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("documentId", documentId);
        payload.put("deletedBy", deletedBy);
        payload.put("deletedAt", deletedAt);
        return payload;
    }

    private static Map<String, Object> envelope(Map<String, Object> metadata, Map<String, Object> payload) {
        Map<String, Object> envelope = new LinkedHashMap<>();
        envelope.put("metadata", metadata);
        envelope.put("payload", payload);
        return envelope;
    }

    private static Map<String, Object> headers(UUID correlationId, String eventType) {
        Map<String, Object> headers = new LinkedHashMap<>();
        headers.put(AmqpHeaderNames.CORRELATION_ID, correlationId);
        headers.put(AmqpHeaderNames.EVENT_TYPE, eventType);
        headers.put(AmqpHeaderNames.EVENT_VERSION, EVENT_VERSION);
        return headers;
    }

    private String json(Map<String, Object> value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Could not serialize outbox event", exception);
        }
    }

    public record EventEnvelope(
            UUID eventId,
            String eventType,
            String routingKey,
            String exchangeName,
            String payloadJson,
            String headersJson) {
    }
}
