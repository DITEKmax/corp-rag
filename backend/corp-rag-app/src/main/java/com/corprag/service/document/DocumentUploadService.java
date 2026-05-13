package com.corprag.service.document;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.adapter.storage.DocumentStorageClient;
import com.corprag.config.DocumentStorageProperties;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.AccessLevel;
import com.corprag.domain.AuditOutcome;
import com.corprag.domain.DocumentRecord;
import com.corprag.domain.DocumentStatus;
import com.corprag.domain.ResolvedAccessFilter;
import com.corprag.repository.DocumentRepository;
import com.corprag.security.CorrelationIdFilter;
import com.corprag.service.access.AccessFilterResolver;
import com.corprag.service.audit.AuditEventWriter;
import com.corprag.service.outbox.OutboxService;
import java.io.IOException;
import java.time.Clock;
import java.time.Instant;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionOperations;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class DocumentUploadService {

    private final DocumentUploadPreparer uploadPreparer;
    private final DocumentStorageClient storageClient;
    private final DocumentRepository documentRepository;
    private final AccessFilterResolver accessFilterResolver;
    private final OutboxService outboxService;
    private final AuditEventWriter auditEventWriter;
    private final DocumentStorageProperties storageProperties;
    private final TransactionOperations transactionOperations;
    private final Clock clock;

    @Autowired
    public DocumentUploadService(
            DocumentUploadPreparer uploadPreparer,
            DocumentStorageClient storageClient,
            DocumentRepository documentRepository,
            AccessFilterResolver accessFilterResolver,
            OutboxService outboxService,
            AuditEventWriter auditEventWriter,
            DocumentStorageProperties storageProperties,
            PlatformTransactionManager transactionManager) {
        this(
                uploadPreparer,
                storageClient,
                documentRepository,
                accessFilterResolver,
                outboxService,
                auditEventWriter,
                storageProperties,
                new TransactionTemplate(transactionManager),
                Clock.systemUTC());
    }

    DocumentUploadService(
            DocumentUploadPreparer uploadPreparer,
            DocumentStorageClient storageClient,
            DocumentRepository documentRepository,
            AccessFilterResolver accessFilterResolver,
            OutboxService outboxService,
            AuditEventWriter auditEventWriter,
            DocumentStorageProperties storageProperties,
            TransactionOperations transactionOperations,
            Clock clock) {
        this.uploadPreparer = uploadPreparer;
        this.storageClient = storageClient;
        this.documentRepository = documentRepository;
        this.accessFilterResolver = accessFilterResolver;
        this.outboxService = outboxService;
        this.auditEventWriter = auditEventWriter;
        this.storageProperties = storageProperties;
        this.transactionOperations = transactionOperations;
        this.clock = clock;
    }

    public DocumentRecord upload(DocumentUploadCommand command) {
        assertAccessLevelAllowed(command);

        UUID documentId = UUID.randomUUID();
        Instant uploadedAt = clock.instant();
        PreparedDocumentUpload upload = prepare(command, documentId, uploadedAt);
        Optional<DocumentRecord> duplicate = documentRepository.findActiveDuplicate(upload.contentSha256(), command.department());
        if (duplicate.isPresent()) {
            auditFailure(command, upload, "duplicate", Map.of("existingDocumentId", duplicate.get().id().toString()));
            throw duplicateProblem(duplicate.get().id());
        }

        storageClient.putObject(
                upload.objectKey(),
                upload.sniffedMimeType(),
                upload.sizeBytes(),
                uploadPreparer.contentStream(upload));

        UUID correlationId = ensureCorrelationId();
        DocumentRecord document = document(command, documentId, upload, uploadedAt);
        try {
            return Objects.requireNonNull(transactionOperations.execute(status -> {
                documentRepository.insert(document);
                outboxService.createDocumentUploaded(document, correlationId, uploadedAt);
                auditSuccess(command, document, upload);
                return document;
            }));
        } catch (DataIntegrityViolationException exception) {
            UUID existingDocumentId = documentRepository
                    .findActiveDuplicate(upload.contentSha256(), command.department())
                    .map(DocumentRecord::id)
                    .orElse(null);
            if (existingDocumentId != null) {
                auditFailure(command, upload, "duplicate-constraint", Map.of("existingDocumentId", existingDocumentId.toString()));
                throw duplicateProblem(existingDocumentId);
            }
            throw exception;
        }
    }

    private PreparedDocumentUpload prepare(DocumentUploadCommand command, UUID documentId, Instant uploadedAt) {
        try {
            return uploadPreparer.prepare(
                    command.file().getInputStream(),
                    command.file().getOriginalFilename(),
                    command.file().getContentType(),
                    command.file().getSize(),
                    documentId,
                    uploadedAt);
        } catch (IOException exception) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "Could not read uploaded file");
        } catch (ApiProblemException exception) {
            auditFailure(command, null, exception.errorCode().code(), Map.of());
            throw exception;
        }
    }

    private void assertAccessLevelAllowed(DocumentUploadCommand command) {
        ResolvedAccessFilter filter = accessFilterResolver.resolve(command.actorUserId());
        int maxRank = filter.accessLevels().stream()
                .max(Comparator.comparingInt(AccessLevel::rank))
                .map(AccessLevel::rank)
                .orElse(AccessLevel.PUBLIC.rank());
        if (command.accessLevel().rank() > maxRank) {
            auditFailure(command, null, "access-level-cap", Map.of("requestedAccessLevel", command.accessLevel().name()));
            throw new ApiProblemException(
                    ErrorCodes.INSUFFICIENT_ACCESS_LEVEL,
                    "Requested document access level exceeds caller access cap");
        }
    }

    private DocumentRecord document(
            DocumentUploadCommand command,
            UUID documentId,
            PreparedDocumentUpload upload,
            Instant uploadedAt) {
        return new DocumentRecord(
                documentId,
                command.title(),
                command.description(),
                upload.originalFilename(),
                upload.sniffedMimeType(),
                upload.sizeBytes(),
                command.accessLevel(),
                command.department(),
                command.docType(),
                command.language(),
                DocumentStatus.UPLOADED,
                command.actorUserId(),
                storageProperties.getBucket(),
                upload.objectKey(),
                upload.contentSha256(),
                uploadedAt,
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

    private void auditSuccess(DocumentUploadCommand command, DocumentRecord document, PreparedDocumentUpload upload) {
        auditEventWriter.writeEvent(
                "DOCUMENT",
                "DOCUMENT_UPLOADED",
                AuditOutcome.SUCCESS,
                command.actorUserId(),
                null,
                "DOCUMENT",
                document.id(),
                command.ipAddress(),
                command.userAgent(),
                auditDetails(command, upload, Map.of()));
    }

    private void auditFailure(
            DocumentUploadCommand command,
            PreparedDocumentUpload upload,
            String reason,
            Map<String, ?> extraDetails) {
        Map<String, Object> details = new LinkedHashMap<>(auditDetails(command, upload, extraDetails));
        details.put("failureReason", reason);
        auditEventWriter.writeEvent(
                "DOCUMENT",
                "DOCUMENT_UPLOADED",
                AuditOutcome.FAILURE,
                command.actorUserId(),
                null,
                "DOCUMENT",
                null,
                command.ipAddress(),
                command.userAgent(),
                details);
    }

    private Map<String, Object> auditDetails(
            DocumentUploadCommand command,
            PreparedDocumentUpload upload,
            Map<String, ?> extraDetails) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("title", command.title());
        details.put("originalFilename", upload == null ? command.file().getOriginalFilename() : upload.originalFilename());
        details.put("sizeBytes", upload == null ? command.file().getSize() : upload.sizeBytes());
        details.put("sniffedMimeType", upload == null ? null : upload.sniffedMimeType());
        details.put("declaredMimeType", upload == null ? command.file().getContentType() : upload.declaredMimeType());
        details.put("mimeMismatch", upload != null && upload.mimeMismatch());
        details.put("accessLevel", command.accessLevel().name());
        details.put("department", command.department());
        details.put("docType", command.docType().name());
        details.put("language", command.language());
        details.put("contentSha256", upload == null ? null : upload.contentSha256());
        details.putAll(extraDetails);
        return details;
    }

    private static ApiProblemException duplicateProblem(UUID existingDocumentId) {
        return new ApiProblemException(
                ErrorCodes.DUPLICATE_DOCUMENT,
                "Active duplicate document exists in the same department",
                Map.of("existingDocumentId", existingDocumentId.toString()));
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
