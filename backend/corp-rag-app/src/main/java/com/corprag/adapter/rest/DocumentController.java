package com.corprag.adapter.rest;

import com.corprag.contracts.api.v1.model.Document;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.AccessLevel;
import com.corprag.domain.DocType;
import com.corprag.security.Permission;
import com.corprag.service.document.DocumentUploadCommand;
import com.corprag.service.document.DocumentUploadService;
import jakarta.servlet.http.HttpServletRequest;
import java.net.URI;
import java.util.UUID;
import java.util.regex.Pattern;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
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
    private final DocumentAssembler documentAssembler;

    public DocumentController(DocumentUploadService uploadService, DocumentAssembler documentAssembler) {
        this.uploadService = uploadService;
        this.documentAssembler = documentAssembler;
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
        Document document = documentAssembler.toContract(uploadService.upload(command));
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

    private static String parseLanguage(String value) {
        if ("ru".equals(value) || "en".equals(value)) {
            return value;
        }
        throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "Document language is invalid");
    }
}
