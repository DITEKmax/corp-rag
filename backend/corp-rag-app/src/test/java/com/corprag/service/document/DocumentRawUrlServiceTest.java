package com.corprag.service.document;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
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
import com.corprag.domain.DocumentStatus;
import com.corprag.service.audit.AuditEventWriter;
import java.net.URI;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class DocumentRawUrlServiceTest {

    private static final UUID ACTOR_ID = UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final UUID DOCUMENT_ID = UUID.fromString("d8f3a1c2-e89b-42d3-a456-426614174000");
    private static final Instant NOW = Instant.parse("2026-05-13T12:00:00Z");

    private final DocumentQueryService queryService = mock(DocumentQueryService.class);
    private final DocumentStorageClient storageClient = mock(DocumentStorageClient.class);
    private final DocumentStorageProperties storageProperties = new DocumentStorageProperties();
    private final AuditEventWriter auditEventWriter = mock(AuditEventWriter.class);
    private final DocumentRawUrlService service = new DocumentRawUrlService(
            queryService,
            storageClient,
            storageProperties,
            auditEventWriter,
            Clock.fixed(NOW, ZoneOffset.UTC));

    @Test
    void issueRawUrlChecksVisibilityPresignsForFiveMinutesAndAuditsSuccess() {
        URI url = URI.create("https://minio.local/corp-rag-documents/2026/05/file.txt?signature=test");
        when(queryService.getVisible(ACTOR_ID, DOCUMENT_ID)).thenReturn(document());
        when(storageClient.presignedGetUrl("2026/05/" + DOCUMENT_ID + ".txt", Duration.ofMinutes(5))).thenReturn(url);

        DocumentRawUrl rawUrl = service.issueRawUrl(ACTOR_ID, DOCUMENT_ID, "127.0.0.1", "JUnit");

        assertThat(rawUrl.url()).isEqualTo(url);
        assertThat(rawUrl.expiresAt()).isEqualTo(NOW.plus(Duration.ofMinutes(5)));
        verify(storageClient).presignedGetUrl("2026/05/" + DOCUMENT_ID + ".txt", Duration.ofMinutes(5));

        ArgumentCaptor<Map> detailsCaptor = ArgumentCaptor.forClass(Map.class);
        verify(auditEventWriter).writeEvent(
                eq("DOCUMENT"),
                eq("DOCUMENT_RAW_URL_ISSUED"),
                eq(AuditOutcome.SUCCESS),
                eq(ACTOR_ID),
                org.mockito.ArgumentMatchers.isNull(),
                eq("DOCUMENT"),
                eq(DOCUMENT_ID),
                eq("127.0.0.1"),
                eq("JUnit"),
                detailsCaptor.capture());
        assertThat(detailsCaptor.getValue())
                .containsEntry("accessLevel", "INTERNAL")
                .containsEntry("department", "HR");
    }

    @Test
    void invisibleDocumentDoesNotPresignOrAudit() {
        when(queryService.getVisible(ACTOR_ID, DOCUMENT_ID)).thenThrow(new ApiProblemException(
                ErrorCodes.DOCUMENT_NOT_FOUND,
                "Document not found"));

        assertThatThrownBy(() -> service.issueRawUrl(ACTOR_ID, DOCUMENT_ID, "127.0.0.1", "JUnit"))
                .isInstanceOf(ApiProblemException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCodes.DOCUMENT_NOT_FOUND);

        verify(storageClient, never()).presignedGetUrl(any(), any());
        verify(auditEventWriter, never()).writeEvent(any(), any(), any(), any(), any(), any(), any(), any(), any(), any());
    }

    private static DocumentRecord document() {
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
                DocumentStatus.UPLOADED,
                ACTOR_ID,
                "corp-rag-documents",
                "2026/05/" + DOCUMENT_ID + ".txt",
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
