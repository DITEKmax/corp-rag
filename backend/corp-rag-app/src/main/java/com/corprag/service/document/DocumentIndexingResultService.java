package com.corprag.service.document;

import com.corprag.domain.AuditOutcome;
import com.corprag.repository.DocumentRepository;
import com.corprag.service.audit.AuditEventWriter;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.stereotype.Service;

@Service
public class DocumentIndexingResultService {

    private final DocumentRepository documentRepository;
    private final AuditEventWriter auditEventWriter;

    public DocumentIndexingResultService(DocumentRepository documentRepository, AuditEventWriter auditEventWriter) {
        this.documentRepository = documentRepository;
        this.auditEventWriter = auditEventWriter;
    }

    public void handleIndexed(DocumentIndexedEvent event) {
        boolean updated = documentRepository.markIndexed(
                event.documentId(),
                event.indexedAt(),
                event.chunkCount(),
                event.qdrantCollection(),
                event.neo4jEntityCount(),
                event.durationMs());
        auditEventWriter.writeEvent(
                "DOCUMENT",
                "DOCUMENT_INDEXED",
                AuditOutcome.SUCCESS,
                null,
                null,
                "DOCUMENT",
                event.documentId(),
                null,
                null,
                indexedDetails(event, updated));
    }

    public void handleFailed(DocumentIndexingFailedEvent event) {
        boolean updated = documentRepository.markIndexingFailed(
                event.documentId(),
                event.stage(),
                event.errorCode(),
                event.errorMessage(),
                event.retryable(),
                event.retryCount());
        auditEventWriter.writeEvent(
                "DOCUMENT",
                "DOCUMENT_INDEXING_FAILED",
                AuditOutcome.SUCCESS,
                null,
                null,
                "DOCUMENT",
                event.documentId(),
                null,
                null,
                failedDetails(event, updated));
    }

    private static Map<String, Object> indexedDetails(DocumentIndexedEvent event, boolean statusUpdated) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("chunkCount", event.chunkCount());
        details.put("durationMs", event.durationMs());
        details.put("qdrantCollection", event.qdrantCollection());
        details.put("neo4jEntityCount", event.neo4jEntityCount());
        details.put("statusUpdated", statusUpdated);
        return details;
    }

    private static Map<String, Object> failedDetails(DocumentIndexingFailedEvent event, boolean statusUpdated) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("stage", event.stage());
        details.put("errorCode", event.errorCode());
        details.put("errorMessage", event.errorMessage());
        details.put("retryable", event.retryable());
        details.put("retryCount", event.retryCount());
        details.put("failedAt", event.failedAt().toString());
        details.put("statusUpdated", statusUpdated);
        return details;
    }
}
