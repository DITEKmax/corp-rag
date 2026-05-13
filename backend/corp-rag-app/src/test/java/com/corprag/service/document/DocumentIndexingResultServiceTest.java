package com.corprag.service.document;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.AuditOutcome;
import com.corprag.repository.DocumentRepository;
import com.corprag.service.audit.AuditEventWriter;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class DocumentIndexingResultServiceTest {

    private static final UUID EVENT_ID = UUID.fromString("550e8400-e29b-41d4-a716-446655440003");
    private static final UUID CORRELATION_ID = UUID.fromString("22222222-2222-4222-8222-222222222222");
    private static final UUID DOCUMENT_ID = UUID.fromString("d8f3a1c2-e89b-42d3-a456-426614174000");
    private static final Instant INDEXED_AT = Instant.parse("2026-05-13T12:01:00Z");
    private static final Instant FAILED_AT = Instant.parse("2026-05-13T12:02:00Z");

    private final DocumentRepository documentRepository = mock(DocumentRepository.class);
    private final AuditEventWriter auditEventWriter = mock(AuditEventWriter.class);
    private final DocumentIndexingResultService service =
            new DocumentIndexingResultService(documentRepository, auditEventWriter);

    @Test
    void indexedEventUpdatesUploadedDocumentAndWritesD53AuditDetails() {
        when(documentRepository.markIndexed(DOCUMENT_ID, INDEXED_AT, 42, "documents_chunks", 18, 87520L))
                .thenReturn(true);

        service.handleIndexed(indexedEvent());

        @SuppressWarnings("rawtypes")
        ArgumentCaptor<Map> details = ArgumentCaptor.forClass(Map.class);
        verify(auditEventWriter).writeEvent(
                eq("DOCUMENT"),
                eq("DOCUMENT_INDEXED"),
                eq(AuditOutcome.SUCCESS),
                eq(null),
                eq(null),
                eq("DOCUMENT"),
                eq(DOCUMENT_ID),
                eq(null),
                eq(null),
                details.capture());
        assertThat(details.getValue())
                .containsEntry("chunkCount", 42)
                .containsEntry("durationMs", 87520L)
                .containsEntry("qdrantCollection", "documents_chunks")
                .containsEntry("neo4jEntityCount", 18)
                .containsEntry("statusUpdated", true);
    }

    @Test
    void failedEventUpdatesUploadedDocumentAndWritesD54AuditDetails() {
        when(documentRepository.markIndexingFailed(
                DOCUMENT_ID,
                "PARSING",
                ErrorCodes.INVALID_FILE_FORMAT.code(),
                "No extractable text",
                false,
                0)).thenReturn(true);

        service.handleFailed(failedEvent());

        @SuppressWarnings("rawtypes")
        ArgumentCaptor<Map> details = ArgumentCaptor.forClass(Map.class);
        verify(auditEventWriter).writeEvent(
                eq("DOCUMENT"),
                eq("DOCUMENT_INDEXING_FAILED"),
                eq(AuditOutcome.SUCCESS),
                eq(null),
                eq(null),
                eq("DOCUMENT"),
                eq(DOCUMENT_ID),
                eq(null),
                eq(null),
                details.capture());
        assertThat(details.getValue())
                .containsEntry("stage", "PARSING")
                .containsEntry("errorCode", ErrorCodes.INVALID_FILE_FORMAT.code())
                .containsEntry("errorMessage", "No extractable text")
                .containsEntry("retryable", false)
                .containsEntry("retryCount", 0)
                .containsEntry("failedAt", FAILED_AT.toString())
                .containsEntry("statusUpdated", true);
    }

    @Test
    void skippedStatusUpdateStillAuditsFirstProcessedLateEvent() {
        when(documentRepository.markIndexed(DOCUMENT_ID, INDEXED_AT, 42, "documents_chunks", 18, 87520L))
                .thenReturn(false);

        service.handleIndexed(indexedEvent());

        @SuppressWarnings("rawtypes")
        ArgumentCaptor<Map> details = ArgumentCaptor.forClass(Map.class);
        verify(auditEventWriter).writeEvent(
                eq("DOCUMENT"),
                eq("DOCUMENT_INDEXED"),
                eq(AuditOutcome.SUCCESS),
                eq(null),
                eq(null),
                eq("DOCUMENT"),
                eq(DOCUMENT_ID),
                eq(null),
                eq(null),
                details.capture());
        assertThat(details.getValue()).containsEntry("statusUpdated", false);
    }

    private static DocumentIndexedEvent indexedEvent() {
        return new DocumentIndexedEvent(
                EVENT_ID,
                CORRELATION_ID,
                DOCUMENT_ID,
                42,
                INDEXED_AT,
                "documents_chunks",
                18,
                87520L);
    }

    private static DocumentIndexingFailedEvent failedEvent() {
        return new DocumentIndexingFailedEvent(
                EVENT_ID,
                CORRELATION_ID,
                DOCUMENT_ID,
                "PARSING",
                ErrorCodes.INVALID_FILE_FORMAT.code(),
                "No extractable text",
                FAILED_AT,
                false,
                0);
    }
}
