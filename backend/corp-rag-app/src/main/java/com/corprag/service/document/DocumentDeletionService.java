package com.corprag.service.document;

import com.corprag.domain.AuditOutcome;
import com.corprag.domain.DocumentRecord;
import com.corprag.domain.DocumentStatus;
import com.corprag.domain.ResolvedAccessFilter;
import com.corprag.repository.DocumentRepository;
import com.corprag.security.CorrelationIdFilter;
import com.corprag.service.access.AccessFilterResolver;
import com.corprag.service.audit.AuditEventWriter;
import com.corprag.service.outbox.OutboxService;
import java.time.Clock;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionOperations;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class DocumentDeletionService {

    private final DocumentRepository documentRepository;
    private final AccessFilterResolver accessFilterResolver;
    private final OutboxService outboxService;
    private final AuditEventWriter auditEventWriter;
    private final TransactionOperations transactionOperations;
    private final Clock clock;

    @Autowired
    public DocumentDeletionService(
            DocumentRepository documentRepository,
            AccessFilterResolver accessFilterResolver,
            OutboxService outboxService,
            AuditEventWriter auditEventWriter,
            PlatformTransactionManager transactionManager) {
        this(
                documentRepository,
                accessFilterResolver,
                outboxService,
                auditEventWriter,
                new TransactionTemplate(transactionManager),
                Clock.systemUTC());
    }

    DocumentDeletionService(
            DocumentRepository documentRepository,
            AccessFilterResolver accessFilterResolver,
            OutboxService outboxService,
            AuditEventWriter auditEventWriter,
            TransactionOperations transactionOperations,
            Clock clock) {
        this.documentRepository = documentRepository;
        this.accessFilterResolver = accessFilterResolver;
        this.outboxService = outboxService;
        this.auditEventWriter = auditEventWriter;
        this.transactionOperations = transactionOperations;
        this.clock = clock;
    }

    public void deleteVisible(UUID actorUserId, UUID documentId, String ipAddress, String userAgent) {
        ResolvedAccessFilter filter = accessFilterResolver.resolve(actorUserId);
        Instant deletedAt = clock.instant();
        UUID correlationId = ensureCorrelationId();
        Objects.requireNonNull(transactionOperations.execute(status -> {
            DocumentRecord document = documentRepository.findVisibleById(documentId, filter)
                    .orElseThrow(DocumentQueryService::notFound);
            if (!documentRepository.softDeleteVisible(documentId, filter, actorUserId, deletedAt)) {
                throw DocumentQueryService.notFound();
            }
            outboxService.createDocumentDeleted(document, actorUserId, correlationId, deletedAt);
            auditEventWriter.writeEvent(
                    "DOCUMENT",
                    "DOCUMENT_DELETED",
                    AuditOutcome.SUCCESS,
                    actorUserId,
                    null,
                    "DOCUMENT",
                    document.id(),
                    ipAddress,
                    userAgent,
                    auditDetails(document));
            return Boolean.TRUE;
        }));
    }

    private static Map<String, Object> auditDetails(DocumentRecord document) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("title", document.title());
        details.put("accessLevel", document.accessLevel().name());
        details.put("department", document.department());
        details.put("docType", document.docType().name());
        details.put("previousStatus", document.status().name());
        details.put("indexedChunksKnown", indexedChunksKnown(document));
        return details;
    }

    private static boolean indexedChunksKnown(DocumentRecord document) {
        return (document.chunkCount() != null && document.chunkCount() > 0)
                || document.status() == DocumentStatus.INDEXED;
    }

    private static UUID ensureCorrelationId() {
        String current = MDC.get(CorrelationIdFilter.MDC_KEY);
        if (current != null && !current.isBlank()) {
            try {
                return UUID.fromString(current);
            } catch (IllegalArgumentException ignored) {
                // Replace invalid MDC value below.
            }
        }
        UUID generated = UUID.randomUUID();
        MDC.put(CorrelationIdFilter.MDC_KEY, generated.toString());
        return generated;
    }
}
