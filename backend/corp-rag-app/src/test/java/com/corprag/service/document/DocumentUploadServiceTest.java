package com.corprag.service.document;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.adapter.storage.DocumentStorageClient;
import com.corprag.config.DocumentStorageProperties;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.AccessLevel;
import com.corprag.domain.AuditOutcome;
import com.corprag.domain.DocType;
import com.corprag.domain.DocumentRecord;
import com.corprag.domain.ResolvedAccessFilter;
import com.corprag.repository.DocumentRepository;
import com.corprag.service.access.AccessFilterResolver;
import com.corprag.service.audit.AuditEventWriter;
import com.corprag.service.outbox.OutboxService;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.InOrder;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.transaction.support.TransactionCallback;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.TransactionOperations;

class DocumentUploadServiceTest {

    private static final UUID ACTOR_ID = UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final Instant NOW = Instant.parse("2026-05-13T12:00:00Z");

    private final DocumentStorageClient storageClient = mock(DocumentStorageClient.class);
    private final DocumentRepository documentRepository = mock(DocumentRepository.class);
    private final AccessFilterResolver accessFilterResolver = mock(AccessFilterResolver.class);
    private final OutboxService outboxService = mock(OutboxService.class);
    private final AuditEventWriter auditEventWriter = mock(AuditEventWriter.class);
    private final DocumentStorageProperties storageProperties = new DocumentStorageProperties();
    private final TransactionOperations transactionOperations = new TransactionOperations() {
        @Override
        public <T> T execute(TransactionCallback<T> action) {
            return action.doInTransaction(mock(TransactionStatus.class));
        }
    };
    private final DocumentUploadService service = new DocumentUploadService(
            new DocumentUploadPreparer(),
            storageClient,
            documentRepository,
            accessFilterResolver,
            outboxService,
            auditEventWriter,
            storageProperties,
            transactionOperations,
            Clock.fixed(NOW, ZoneOffset.UTC));

    @Test
    void uploadStoresObjectBeforeDatabaseOutboxAndAuditTransaction() {
        when(accessFilterResolver.resolve(ACTOR_ID)).thenReturn(new ResolvedAccessFilter(
                List.of(AccessLevel.PUBLIC, AccessLevel.INTERNAL),
                List.of(),
                List.of(DocType.POLICY)));
        when(documentRepository.findActiveDuplicate(any(), any())).thenReturn(Optional.empty());

        DocumentRecord document = service.upload(command(AccessLevel.INTERNAL, "plain text".getBytes(StandardCharsets.UTF_8)));

        assertThat(document.status().name()).isEqualTo("UPLOADED");
        assertThat(document.storageBucket()).isEqualTo("corp-rag-documents");
        assertThat(document.storageKey()).matches("2026/05/[0-9a-f\\-]{36}\\.txt");
        assertThat(document.contentSha256()).hasSize(64);

        InOrder inOrder = inOrder(storageClient, documentRepository, outboxService, auditEventWriter);
        inOrder.verify(storageClient).putObject(any(), any(), anyLong(), any());
        inOrder.verify(documentRepository).insert(any(DocumentRecord.class));
        inOrder.verify(outboxService).createDocumentUploaded(any(DocumentRecord.class), any(UUID.class), any(Instant.class));
        inOrder.verify(auditEventWriter).writeEvent(
                org.mockito.ArgumentMatchers.eq("DOCUMENT"),
                org.mockito.ArgumentMatchers.eq("DOCUMENT_UPLOADED"),
                org.mockito.ArgumentMatchers.eq(AuditOutcome.SUCCESS),
                org.mockito.ArgumentMatchers.eq(ACTOR_ID),
                org.mockito.ArgumentMatchers.isNull(),
                org.mockito.ArgumentMatchers.eq("DOCUMENT"),
                org.mockito.ArgumentMatchers.eq(document.id()),
                org.mockito.ArgumentMatchers.eq("127.0.0.1"),
                org.mockito.ArgumentMatchers.eq("JUnit"),
                any(Map.class));
    }

    @Test
    void uploadAboveCallerAccessCapIsRejectedBeforeReadingOrStorage() {
        when(accessFilterResolver.resolve(ACTOR_ID)).thenReturn(new ResolvedAccessFilter(
                List.of(AccessLevel.PUBLIC),
                List.of(),
                List.of(DocType.POLICY)));

        assertThatThrownBy(() -> service.upload(command(AccessLevel.INTERNAL, "plain text".getBytes(StandardCharsets.UTF_8))))
                .isInstanceOf(ApiProblemException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCodes.INSUFFICIENT_ACCESS_LEVEL);

        verify(storageClient, never()).putObject(any(), any(), anyLong(), any());
        verify(documentRepository, never()).insert(any());
    }

    @Test
    void activeDuplicateIsRejectedBeforeMinioWrite() {
        when(accessFilterResolver.resolve(ACTOR_ID)).thenReturn(new ResolvedAccessFilter(
                List.of(AccessLevel.PUBLIC, AccessLevel.INTERNAL),
                List.of(),
                List.of(DocType.POLICY)));
        UUID existingId = UUID.fromString("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");
        when(documentRepository.findActiveDuplicate(any(), any()))
                .thenReturn(Optional.of(existingDocument(existingId)));

        assertThatThrownBy(() -> service.upload(command(AccessLevel.INTERNAL, "plain text".getBytes(StandardCharsets.UTF_8))))
                .isInstanceOf(ApiProblemException.class)
                .extracting("details")
                .asInstanceOf(org.assertj.core.api.InstanceOfAssertFactories.map(String.class, Object.class))
                .containsEntry("existingDocumentId", existingId.toString());

        verify(storageClient, never()).putObject(any(), any(), anyLong(), any());
        verify(documentRepository, never()).insert(any());
    }

    @Test
    void successfulUploadAuditIncludesMimeMismatchAndSha256() {
        when(accessFilterResolver.resolve(ACTOR_ID)).thenReturn(new ResolvedAccessFilter(
                List.of(AccessLevel.PUBLIC, AccessLevel.INTERNAL),
                List.of(),
                List.of(DocType.POLICY)));
        when(documentRepository.findActiveDuplicate(any(), any())).thenReturn(Optional.empty());

        service.upload(command(AccessLevel.INTERNAL, "plain text".getBytes(StandardCharsets.UTF_8)));

        ArgumentCaptor<Map> detailsCaptor = ArgumentCaptor.forClass(Map.class);
        verify(auditEventWriter).writeEvent(
                org.mockito.ArgumentMatchers.eq("DOCUMENT"),
                org.mockito.ArgumentMatchers.eq("DOCUMENT_UPLOADED"),
                org.mockito.ArgumentMatchers.eq(AuditOutcome.SUCCESS),
                org.mockito.ArgumentMatchers.eq(ACTOR_ID),
                org.mockito.ArgumentMatchers.isNull(),
                org.mockito.ArgumentMatchers.eq("DOCUMENT"),
                any(UUID.class),
                org.mockito.ArgumentMatchers.eq("127.0.0.1"),
                org.mockito.ArgumentMatchers.eq("JUnit"),
                detailsCaptor.capture());

        @SuppressWarnings("unchecked")
        Map<String, Object> details = detailsCaptor.getValue();
        assertThat(details)
                .containsEntry("title", "Policy")
                .containsEntry("declaredMimeType", "application/pdf")
                .containsEntry("sniffedMimeType", "text/plain")
                .containsEntry("mimeMismatch", true)
                .containsKey("contentSha256");
    }

    private static DocumentUploadCommand command(AccessLevel accessLevel, byte[] content) {
        return new DocumentUploadCommand(
                ACTOR_ID,
                "Policy",
                "Upload test",
                accessLevel,
                "HR",
                DocType.POLICY,
                "en",
                new MockMultipartFile("file", "policy.pdf", "application/pdf", content),
                "127.0.0.1",
                "JUnit");
    }

    private static DocumentRecord existingDocument(UUID id) {
        return new DocumentRecord(
                id,
                "Existing",
                null,
                "existing.txt",
                "text/plain",
                10,
                AccessLevel.INTERNAL,
                "HR",
                DocType.POLICY,
                "en",
                com.corprag.domain.DocumentStatus.UPLOADED,
                ACTOR_ID,
                "corp-rag-documents",
                "2026/05/" + id + ".txt",
                "0".repeat(64),
                NOW,
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
