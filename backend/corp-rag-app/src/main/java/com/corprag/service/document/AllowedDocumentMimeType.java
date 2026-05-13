package com.corprag.service.document;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.constants.ErrorCodes;
import java.util.Arrays;
import java.util.Optional;

public enum AllowedDocumentMimeType {
    PDF("application/pdf", "pdf"),
    DOCX("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    HTML("text/html", "html"),
    MARKDOWN("text/markdown", "md"),
    TEXT("text/plain", "txt");

    private final String mimeType;
    private final String extension;

    AllowedDocumentMimeType(String mimeType, String extension) {
        this.mimeType = mimeType;
        this.extension = extension;
    }

    public String mimeType() {
        return mimeType;
    }

    public String extension() {
        return extension;
    }

    static AllowedDocumentMimeType requireAllowed(String sniffedMimeType) {
        return find(sniffedMimeType)
                .orElseThrow(() -> new ApiProblemException(
                        ErrorCodes.UNSUPPORTED_FILE_TYPE,
                        "Unsupported document MIME type: " + sniffedMimeType));
    }

    static Optional<AllowedDocumentMimeType> find(String sniffedMimeType) {
        String normalized = normalize(sniffedMimeType);
        return Arrays.stream(values())
                .filter(candidate -> candidate.mimeType.equals(normalized))
                .findFirst();
    }

    private static String normalize(String sniffedMimeType) {
        if (sniffedMimeType == null || sniffedMimeType.isBlank()) {
            return "";
        }
        return sniffedMimeType.split(";", 2)[0].trim().toLowerCase();
    }
}
