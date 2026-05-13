package com.corprag.service.outbox;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import com.corprag.contracts.constants.EventRoutingKeys;
import com.corprag.contracts.constants.ExchangeNames;
import com.corprag.domain.AccessLevel;
import com.corprag.domain.DocType;
import com.corprag.domain.DocumentRecord;
import com.corprag.domain.DocumentStatus;
import com.corprag.domain.OutboxEventRecord;
import com.corprag.repository.OutboxEventRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class OutboxServiceTest {

    private static final UUID DOCUMENT_ID = UUID.fromString("d8f3a1c2-e89b-42d3-a456-426614174000");
    private static final UUID OWNER_ID = UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final UUID CORRELATION_ID = UUID.fromString("22222222-2222-4222-8222-222222222222");
    private static final Instant UPLOADED_AT = Instant.parse("2026-05-13T12:00:00Z");

    private final OutboxEventRepository repository = mock(OutboxEventRepository.class);
    private final ObjectMapper objectMapper = new ObjectMapper()
            .registerModule(new JavaTimeModule())
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    private final EventEnvelopeFactory eventEnvelopeFactory = new EventEnvelopeFactory(objectMapper);
    private final OutboxService service = new OutboxService(repository, eventEnvelopeFactory);

    @Test
    void createDocumentUploadedPersistsAsyncApiEnvelopeAndCorrelationHeaders() throws Exception {
        OutboxEventRecord returned = service.createDocumentUploaded(document(), CORRELATION_ID, UPLOADED_AT);

        ArgumentCaptor<OutboxEventRecord> captor = ArgumentCaptor.forClass(OutboxEventRecord.class);
        verify(repository).insert(captor.capture());
        OutboxEventRecord event = captor.getValue();
        assertThat(returned).isEqualTo(event);
        assertThat(event.aggregateType()).isEqualTo("DOCUMENT");
        assertThat(event.aggregateId()).isEqualTo(DOCUMENT_ID);
        assertThat(event.eventType()).isEqualTo(EventRoutingKeys.DOCUMENT_UPLOADED);
        assertThat(event.routingKey()).isEqualTo(EventRoutingKeys.DOCUMENT_UPLOADED);
        assertThat(event.exchangeName()).isEqualTo(ExchangeNames.DOCUMENTS_TOPIC);
        assertThat(event.correlationId()).isEqualTo(CORRELATION_ID);
        assertThat(event.createdAt()).isEqualTo(UPLOADED_AT);
        assertThat(event.nextAttemptAt()).isEqualTo(UPLOADED_AT);
        assertThat(event.publishAttempts()).isZero();

        Map<String, Object> envelope = read(event.payloadJson());
        @SuppressWarnings("unchecked")
        Map<String, Object> metadata = (Map<String, Object>) envelope.get("metadata");
        @SuppressWarnings("unchecked")
        Map<String, Object> payload = (Map<String, Object>) envelope.get("payload");
        assertThat(metadata)
                .containsEntry("eventId", event.id().toString())
                .containsEntry("eventType", EventRoutingKeys.DOCUMENT_UPLOADED)
                .containsEntry("eventVersion", "1.0.0")
                .containsEntry("occurredAt", UPLOADED_AT.toString())
                .containsEntry("correlationId", CORRELATION_ID.toString())
                .containsEntry("sourceService", "corp-rag-backend");
        assertThat(payload)
                .containsEntry("documentId", DOCUMENT_ID.toString())
                .containsEntry("title", "Policy")
                .containsEntry("ownerUserId", OWNER_ID.toString())
                .containsEntry("contentSha256", "0".repeat(64))
                .containsEntry("accessLevel", "INTERNAL")
                .containsEntry("department", "HR")
                .containsEntry("docType", "POLICY")
                .containsEntry("language", "en")
                .containsEntry("minioBucket", "corp-rag-documents")
                .containsEntry("minioObjectKey", "2026/05/" + DOCUMENT_ID + ".txt")
                .containsEntry("mimeType", "text/plain")
                .containsEntry("sizeBytes", 10)
                .containsEntry("originalFilename", "policy.txt")
                .containsEntry("uploadedAt", UPLOADED_AT.toString());

        assertThat(read(event.headersJson()))
                .containsEntry("x-correlation-id", CORRELATION_ID.toString())
                .containsEntry("x-event-type", EventRoutingKeys.DOCUMENT_UPLOADED)
                .containsEntry("x-event-version", "1.0.0");
    }

    @Test
    void createDocumentDeletedPersistsAsyncApiEnvelopeAndCorrelationHeaders() throws Exception {
        OutboxEventRecord returned = service.createDocumentDeleted(document(), OWNER_ID, CORRELATION_ID, UPLOADED_AT);

        ArgumentCaptor<OutboxEventRecord> captor = ArgumentCaptor.forClass(OutboxEventRecord.class);
        verify(repository).insert(captor.capture());
        OutboxEventRecord event = captor.getValue();
        assertThat(returned).isEqualTo(event);
        assertThat(event.aggregateType()).isEqualTo("DOCUMENT");
        assertThat(event.aggregateId()).isEqualTo(DOCUMENT_ID);
        assertThat(event.eventType()).isEqualTo(EventRoutingKeys.DOCUMENT_DELETED);
        assertThat(event.routingKey()).isEqualTo(EventRoutingKeys.DOCUMENT_DELETED);
        assertThat(event.exchangeName()).isEqualTo(ExchangeNames.DOCUMENTS_TOPIC);
        assertThat(event.correlationId()).isEqualTo(CORRELATION_ID);
        assertThat(event.createdAt()).isEqualTo(UPLOADED_AT);
        assertThat(event.nextAttemptAt()).isEqualTo(UPLOADED_AT);

        Map<String, Object> envelope = read(event.payloadJson());
        @SuppressWarnings("unchecked")
        Map<String, Object> metadata = (Map<String, Object>) envelope.get("metadata");
        @SuppressWarnings("unchecked")
        Map<String, Object> payload = (Map<String, Object>) envelope.get("payload");
        assertThat(metadata)
                .containsEntry("eventId", event.id().toString())
                .containsEntry("eventType", EventRoutingKeys.DOCUMENT_DELETED)
                .containsEntry("eventVersion", "1.0.0")
                .containsEntry("occurredAt", UPLOADED_AT.toString())
                .containsEntry("correlationId", CORRELATION_ID.toString())
                .containsEntry("sourceService", "corp-rag-backend");
        assertThat(payload)
                .containsEntry("documentId", DOCUMENT_ID.toString())
                .containsEntry("deletedBy", OWNER_ID.toString())
                .containsEntry("deletedAt", UPLOADED_AT.toString());
        assertThat(read(event.headersJson()))
                .containsEntry("x-correlation-id", CORRELATION_ID.toString())
                .containsEntry("x-event-type", EventRoutingKeys.DOCUMENT_DELETED)
                .containsEntry("x-event-version", "1.0.0");
    }

    private Map<String, Object> read(String json) throws Exception {
        return objectMapper.readValue(json, new TypeReference<>() {
        });
    }

    private static DocumentRecord document() {
        return new DocumentRecord(
                DOCUMENT_ID,
                "Policy",
                "Upload test",
                "policy.txt",
                "text/plain",
                10,
                AccessLevel.INTERNAL,
                "HR",
                DocType.POLICY,
                "en",
                DocumentStatus.UPLOADED,
                OWNER_ID,
                "corp-rag-documents",
                "2026/05/" + DOCUMENT_ID + ".txt",
                "0".repeat(64),
                UPLOADED_AT,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null);
    }
}
