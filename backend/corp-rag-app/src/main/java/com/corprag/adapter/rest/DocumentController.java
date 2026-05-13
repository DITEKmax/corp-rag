package com.corprag.adapter.rest;

import com.corprag.contracts.api.v1.model.Document;
import com.corprag.contracts.api.v1.model.GetDocumentRaw200Response;
import com.corprag.contracts.api.v1.model.PagedDocuments;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.AccessLevel;
import com.corprag.domain.DocType;
import com.corprag.domain.DocumentPage;
import com.corprag.domain.DocumentRecord;
import com.corprag.domain.DocumentSearchCriteria;
import com.corprag.domain.DocumentStatus;
import com.corprag.security.Permission;
import com.corprag.service.document.DocumentQueryService;
import com.corprag.service.document.DocumentDeletionService;
import com.corprag.service.document.DocumentRawUrl;
import com.corprag.service.document.DocumentRawUrlService;
import com.corprag.service.document.DocumentUploadCommand;
import com.corprag.service.document.DocumentUploadService;
import jakarta.servlet.http.HttpServletRequest;
import java.net.URI;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.UUID;
import java.util.regex.Pattern;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/v1/documents")
public class DocumentController {

    private static final Pattern DEPARTMENT_PATTERN = Pattern.compile("^[A-Z][A-Z0-9_]{0,63}$");

    private final DocumentUploadService uploadService;
    private final DocumentQueryService queryService;
    private final DocumentRawUrlService rawUrlService;
    private final DocumentDeletionService deletionService;
    private final DocumentAssembler documentAssembler;

    public DocumentController(
            DocumentUploadService uploadService,
            DocumentQueryService queryService,
            DocumentRawUrlService rawUrlService,
            DocumentDeletionService deletionService,
            DocumentAssembler documentAssembler) {
        this.uploadService = uploadService;
        this.queryService = queryService;
        this.rawUrlService = rawUrlService;
        this.deletionService = deletionService;
        this.documentAssembler = documentAssembler;
    }

    @GetMapping
    ResponseEntity<PagedDocuments> listDocuments(
            @AuthenticationPrincipal Jwt jwt,
            @RequestParam(value = "status", required = false) String status,
            @RequestParam(value = "department", required = false) String department,
            @RequestParam(value = "docType", required = false) String docType,
            @RequestParam(value = "language", required = false) String language,
            @RequestParam(value = "search", required = false) String search,
            @RequestParam(value = "page", defaultValue = "0") int page,
            @RequestParam(value = "size", defaultValue = "20") int size) {
        JwtAuthorization.requirePermission(jwt, Permission.DOCUMENTS_READ.value());
        int validatedPage = validatePage(page);
        int validatedSize = validateSize(size);
        DocumentSearchCriteria criteria = new DocumentSearchCriteria(
                parseOptionalStatus(status),
                department == null ? null : validateDepartment(department),
                parseOptionalDocType(docType),
                parseOptionalLanguage(language),
                validateSearch(search));
        boolean canDelete = JwtAuthorization.hasPermission(jwt, Permission.DOCUMENTS_DELETE.value());
        DocumentPage documentPage = queryService.listVisible(
                JwtAuthorization.userId(jwt),
                criteria,
                validatedPage,
                validatedSize);
        return ResponseEntity.ok(documentAssembler.toPaged(documentPage, validatedPage, validatedSize, true, canDelete));
    }

    @GetMapping("/{documentId}")
    ResponseEntity<Document> getDocument(
            @AuthenticationPrincipal Jwt jwt,
            @PathVariable("documentId") UUID documentId) {
        JwtAuthorization.requirePermission(jwt, Permission.DOCUMENTS_READ.value());
        DocumentRecord document = queryService.getVisible(JwtAuthorization.userId(jwt), documentId);
        boolean canDelete = JwtAuthorization.hasPermission(jwt, Permission.DOCUMENTS_DELETE.value());
        return ResponseEntity.ok(documentAssembler.toContract(document, true, canDelete));
    }

    @GetMapping("/{documentId}/raw")
    ResponseEntity<GetDocumentRaw200Response> getDocumentRaw(
            @AuthenticationPrincipal Jwt jwt,
            @PathVariable("documentId") UUID documentId,
            HttpServletRequest request) {
        JwtAuthorization.requirePermission(jwt, Permission.DOCUMENTS_READ.value());
        DocumentRawUrl rawUrl = rawUrlService.issueRawUrl(
                JwtAuthorization.userId(jwt),
                documentId,
                request.getRemoteAddr(),
                request.getHeader("User-Agent"));
        return ResponseEntity.ok(new GetDocumentRaw200Response()
                .url(rawUrl.url())
                .expiresAt(OffsetDateTime.ofInstant(rawUrl.expiresAt(), ZoneOffset.UTC)));
    }

    @DeleteMapping("/{documentId}")
    ResponseEntity<Void> deleteDocument(
            @AuthenticationPrincipal Jwt jwt,
            @PathVariable("documentId") UUID documentId,
            HttpServletRequest request) {
        JwtAuthorization.requirePermission(jwt, Permission.DOCUMENTS_DELETE.value());
        deletionService.deleteVisible(
                JwtAuthorization.userId(jwt),
                documentId,
                request.getRemoteAddr(),
                request.getHeader("User-Agent"));
        return ResponseEntity.noContent().build();
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    ResponseEntity<Document> uploadDocument(
            @AuthenticationPrincipal Jwt jwt,
            @RequestParam("file") MultipartFile file,
            @RequestParam("title") String title,
            @RequestParam("accessLevel") String accessLevel,
            @RequestParam("department") String department,
            @RequestParam("docType") String docType,
            @RequestParam("language") String language,
            @RequestParam(value = "description", required = false) String description,
            HttpServletRequest request) {
        JwtAuthorization.requirePermission(jwt, Permission.DOCUMENTS_UPLOAD.value());
        DocumentUploadCommand command = new DocumentUploadCommand(
                JwtAuthorization.userId(jwt),
                validateTitle(title),
                validateDescription(description),
                parseAccessLevel(accessLevel),
                validateDepartment(department),
                parseDocType(docType),
                parseLanguage(language),
                file,
                request.getRemoteAddr(),
                request.getHeader("User-Agent"));
        Document document = documentAssembler.toContract(
                uploadService.upload(command),
                JwtAuthorization.hasPermission(jwt, Permission.DOCUMENTS_READ.value()),
                JwtAuthorization.hasPermission(jwt, Permission.DOCUMENTS_DELETE.value()));
        return ResponseEntity.created(URI.create("/api/v1/documents/" + document.getId())).body(document);
    }

    private static String validateTitle(String title) {
        if (title == null || title.isBlank() || title.length() > 512) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "Document title is invalid");
        }
        return title;
    }

    private static String validateDescription(String description) {
        if (description != null && description.length() > 1000) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "Document description is invalid");
        }
        return description;
    }

    private static String validateDepartment(String department) {
        if (department == null || !DEPARTMENT_PATTERN.matcher(department).matches()) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "Department code is invalid");
        }
        return department;
    }

    private static AccessLevel parseAccessLevel(String value) {
        try {
            return AccessLevel.valueOf(value);
        } catch (RuntimeException exception) {
            throw new ApiProblemException(ErrorCodes.INVALID_ACCESS_LEVEL, "Access level is invalid");
        }
    }

    private static DocType parseDocType(String value) {
        try {
            return DocType.valueOf(value);
        } catch (RuntimeException exception) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "Document type is invalid");
        }
    }

    private static DocumentStatus parseOptionalStatus(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return DocumentStatus.valueOf(value);
        } catch (RuntimeException exception) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "Document status is invalid");
        }
    }

    private static DocType parseOptionalDocType(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return parseDocType(value);
    }

    private static String parseLanguage(String value) {
        if ("ru".equals(value) || "en".equals(value)) {
            return value;
        }
        throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "Document language is invalid");
    }

    private static String parseOptionalLanguage(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return parseLanguage(value);
    }

    private static String validateSearch(String search) {
        if (search == null || search.isBlank()) {
            return null;
        }
        if (search.length() > 200) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "Document search query is invalid");
        }
        return search;
    }

    private static int validatePage(int page) {
        if (page < 0) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "Page must be non-negative");
        }
        return page;
    }

    private static int validateSize(int size) {
        if (size < 1 || size > 100) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "Size must be between 1 and 100");
        }
        return size;
    }
}
