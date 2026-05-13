package com.corprag.service.document;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.AccessLevel;
import com.corprag.domain.AuditOutcome;
import com.corprag.domain.DocType;
import com.corprag.domain.DocumentRecord;
import com.corprag.domain.DocumentStatus;
import com.corprag.domain.ResolvedAccessFilter;
import com.corprag.repository.DocumentRepository;
import com.corprag.service.access.AccessFilterResolver;
import com.corprag.service.audit.AuditEventWriter;
import com.corprag.service.outbox.OutboxService;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.InOrder;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.TransactionCallback;
import org.springframework.transaction.support.TransactionOperations;

class DocumentDeletionServiceTest {

    private static final UUID ACTOR_ID = UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final UUID DOCUMENT_ID = UUID.fromString("d8f3a1c2-e89b-42d3-a456-426614174000");
    private static final Instant NOW = Instant.parse("2026-05-13T12:00:00Z");
    private static final ResolvedAccessFilter FILTER = new ResolvedAccessFilter(
            Arrays.asList(AccessLevel.values()),
            List.of(),
            Arrays.asList(DocType.values()));

    private final DocumentRepository documentRepository = mock(DocumentRepository.class);
    private final AccessFilterResolver accessFilterResolver = mock(AccessFilterResolver.class);
    private final OutboxService outboxService = mock(OutboxService.class);
    private final AuditEventWriter auditEventWriter = mock(AuditEventWriter.class);
    private final TransactionOperations transactionOperations = new TransactionOperations() {
        @Override
        public <T> T execute(TransactionCallback<T> action) {
            return action.doInTransaction(mock(TransactionStatus.class));
        }
    };
    private final DocumentDeletionService service = new DocumentDeletionService(
            documentRepository,
            accessFilterResolver,
            outboxService,
            auditEventWriter,
            transactionOperations,
            Clock.fixed(NOW, ZoneOffset.UTC));

    @Test
    void deleteVisibleUploadedDocumentSoftDeletesOutboxesAndAuditsInOneFlow() {
        DocumentRecord document = document(DocumentStatus.UPLOADED, null);
        when(accessFilterResolver.resolve(ACTOR_ID)).thenReturn(FILTER);
        when(documentRepository.findVisibleById(DOCUMENT_ID, FILTER)).thenReturn(Optional.of(document));
        when(documentRepository.softDeleteVisible(DOCUMENT_ID, FILTER, ACTOR_ID, NOW)).thenReturn(true);

        service.deleteVisible(ACTOR_ID, DOCUMENT_ID, "127.0.0.1", "JUnit");

        InOrder inOrder = inOrder(documentRepository, outboxService, auditEventWriter);
        inOrder.verify(documentRepository).findVisibleById(DOCUMENT_ID, FILTER);
        inOrder.verify(documentRepository).softDeleteVisible(DOCUMENT_ID, FILTER, ACTOR_ID, NOW);
        inOrder.verify(outboxService).createDocumentDeleted(eq(document), eq(ACTOR_ID), any(UUID.class), eq(NOW));

        ArgumentCaptor<Map> detailsCaptor = ArgumentCaptor.forClass(Map.class);
        inOrder.verify(auditEventWriter).writeEvent(
                eq("DOCUMENT"),
                eq("DOCUMENT_DELETED"),
                eq(AuditOutcome.SUCCESS),
                eq(ACTOR_ID),
                org.mockito.ArgumentMatchers.isNull(),
                eq("DOCUMENT"),
                eq(DOCUMENT_ID),
                eq("127.0.0.1"),
                eq("JUnit"),
                detailsCaptor.capture());
        org.assertj.core.api.Assertions.assertThat(detailsCaptor.getValue())
                .containsEntry("title", "Policy")
                .containsEntry("accessLevel", "INTERNAL")
                .containsEntry("department", "HR")
                .containsEntry("docType", "POLICY")
                .containsEntry("previousStatus", "UPLOADED")
                .containsEntry("indexedChunksKnown", false);
    }

    @Test
    void deleteDoesNotRejectIndexedOrFailedDocumentsByStatus() {
        for (DocumentStatus status : List.of(DocumentStatus.INDEXED, DocumentStatus.INDEXING_FAILED)) {
            DocumentRecord document = document(status, status == DocumentStatus.INDEXED ? 3 : null);
            when(accessFilterResolver.resolve(ACTOR_ID)).thenReturn(FILTER);
            when(documentRepository.findVisibleById(DOCUMENT_ID, FILTER)).thenReturn(Optional.of(document));
            when(documentRepository.softDeleteVisible(DOCUMENT_ID, FILTER, ACTOR_ID, NOW)).thenReturn(true);

            service.deleteVisible(ACTOR_ID, DOCUMENT_ID, "127.0.0.1", "JUnit");

            verify(outboxService).createDocumentDeleted(eq(document), eq(ACTOR_ID), any(UUID.class), eq(NOW));
        }
    }

    @Test
    void invisibleDocumentReturnsDocumentNotFoundWithoutOutboxOrAudit() {
        when(accessFilterResolver.resolve(ACTOR_ID)).thenReturn(FILTER);
        when(documentRepository.findVisibleById(DOCUMENT_ID, FILTER)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.deleteVisible(ACTOR_ID, DOCUMENT_ID, "127.0.0.1", "JUnit"))
                .isInstanceOf(ApiProblemException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCodes.DOCUMENT_NOT_FOUND);

        verify(documentRepository, never()).softDeleteVisible(any(), any(), any(), any());
        verify(outboxService, never()).createDocumentDeleted(any(), any(), any(), any());
        verify(auditEventWriter, never()).writeEvent(any(), any(), any(), any(), any(), any(), any(), any(), any(), any());
    }

    private static DocumentRecord document(DocumentStatus status, Integer chunkCount) {
        return new DocumentRecord(
                DOCUMENT_ID,
                "Policy",
                null,
                "policy.txt",
                "text/plain",
                10,
                AccessLevel.INTERNAL,
                "HR",
                DocType.POLICY,
                "en",
                status,
                ACTOR_ID,
                "corp-rag-documents",
                "2026/05/" + DOCUMENT_ID + ".txt",
                "0".repeat(64),
                NOW.minusSeconds(60),
                null,
                chunkCount,
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
