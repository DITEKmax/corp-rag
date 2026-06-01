package com.corprag.service.document;

import com.corprag.adapter.storage.DocumentStorageClient;
import com.corprag.config.DocumentStorageProperties;
import com.corprag.domain.AuditOutcome;
import com.corprag.domain.DocumentRecord;
import com.corprag.service.audit.AuditEventWriter;
import java.net.URI;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class DocumentRawUrlService {

    private static final String TEXT_MARKDOWN_UTF_8 = "text/markdown; charset=utf-8";
    private static final String TEXT_PLAIN_UTF_8 = "text/plain; charset=utf-8";

    private final DocumentQueryService queryService;
    private final DocumentStorageClient storageClient;
    private final DocumentStorageProperties storageProperties;
    private final AuditEventWriter auditEventWriter;
    private final Clock clock;

    @Autowired
    public DocumentRawUrlService(
            DocumentQueryService queryService,
            DocumentStorageClient storageClient,
            DocumentStorageProperties storageProperties,
            AuditEventWriter auditEventWriter) {
        this(queryService, storageClient, storageProperties, auditEventWriter, Clock.systemUTC());
    }

    DocumentRawUrlService(
            DocumentQueryService queryService,
            DocumentStorageClient storageClient,
            DocumentStorageProperties storageProperties,
            AuditEventWriter auditEventWriter,
            Clock clock) {
        this.queryService = queryService;
        this.storageClient = storageClient;
        this.storageProperties = storageProperties;
        this.auditEventWriter = auditEventWriter;
        this.clock = clock;
    }

    public DocumentRawUrl issueRawUrl(UUID actorUserId, UUID documentId, String ipAddress, String userAgent) {
        DocumentRecord document = queryService.getVisible(actorUserId, documentId);
        Duration ttl = storageProperties.getRawUrlTtl();
        Instant issuedAt = clock.instant();
        DocumentRawUrl rawUrl = new DocumentRawUrl(presignedRawUrl(document, ttl), issuedAt.plus(ttl));
        auditEventWriter.writeEvent(
                "DOCUMENT",
                "DOCUMENT_RAW_URL_ISSUED",
                AuditOutcome.SUCCESS,
                actorUserId,
                null,
                "DOCUMENT",
                document.id(),
                ipAddress,
                userAgent,
                Map.of(
                        "accessLevel", document.accessLevel().name(),
                        "department", document.department()));
        return rawUrl;
    }

    private URI presignedRawUrl(DocumentRecord document, Duration ttl) {
        String responseContentType = rawViewResponseContentType(document);
        if (responseContentType == null) {
            return storageClient.presignedGetUrl(document.storageKey(), ttl);
        }
        return storageClient.presignedGetUrl(document.storageKey(), ttl, responseContentType);
    }

    private static String rawViewResponseContentType(DocumentRecord document) {
        String contentType = normalize(document.mimeType());
        if (contentType.startsWith("text/plain")) {
            return TEXT_PLAIN_UTF_8;
        }
        if (contentType.startsWith("text/markdown")) {
            return TEXT_MARKDOWN_UTF_8;
        }

        String filename = normalize(document.originalFilename());
        if (filename.endsWith(".txt")) {
            return TEXT_PLAIN_UTF_8;
        }
        if (filename.endsWith(".md") || filename.endsWith(".markdown")) {
            return TEXT_MARKDOWN_UTF_8;
        }
        return null;
    }

    private static String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }
}
