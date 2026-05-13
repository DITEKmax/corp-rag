package com.corprag.service.document;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.constants.ErrorCodes;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.HexFormat;
import java.util.Locale;
import java.util.UUID;
import org.apache.tika.Tika;
import org.springframework.stereotype.Service;

@Service
public class DocumentUploadPreparer {

    static final long MAX_UPLOAD_BYTES = 50L * 1024L * 1024L;

    private static final DateTimeFormatter KEY_PREFIX_FORMATTER =
            DateTimeFormatter.ofPattern("yyyy/MM", Locale.ROOT).withZone(ZoneOffset.UTC);

    private final Tika tika;

    public DocumentUploadPreparer() {
        this(new Tika());
    }

    DocumentUploadPreparer(Tika tika) {
        this.tika = tika;
    }

    public PreparedDocumentUpload prepare(
            InputStream inputStream,
            String originalFilename,
            String declaredMimeType,
            long declaredSizeBytes,
            UUID documentId,
            Instant uploadedAt) {
        if (declaredSizeBytes > MAX_UPLOAD_BYTES) {
            throw new ApiProblemException(ErrorCodes.FILE_TOO_LARGE, "File exceeds 50 MB upload limit");
        }

        HashedContent hashedContent = readAndHash(inputStream);
        String sniffedMimeType = tika.detect(hashedContent.content());
        AllowedDocumentMimeType allowedMimeType = AllowedDocumentMimeType.requireAllowed(sniffedMimeType);
        String normalizedDeclared = normalizeMimeType(declaredMimeType);
        boolean mismatch = !normalizedDeclared.isBlank() && !normalizedDeclared.equals(allowedMimeType.mimeType());

        return new PreparedDocumentUpload(
                hashedContent.content(),
                sanitizeOriginalFilename(originalFilename),
                normalizedDeclared.isBlank() ? null : normalizedDeclared,
                allowedMimeType.mimeType(),
                mismatch,
                hashedContent.content().length,
                hashedContent.sha256(),
                objectKey(documentId, uploadedAt, allowedMimeType.extension()));
    }

    public ByteArrayInputStream contentStream(PreparedDocumentUpload upload) {
        return new ByteArrayInputStream(upload.content());
    }

    static String objectKey(UUID documentId, Instant uploadedAt, String extension) {
        return KEY_PREFIX_FORMATTER.format(uploadedAt) + "/" + documentId + "." + extension;
    }

    private static HashedContent readAndHash(InputStream inputStream) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            try (DigestInputStream digestInputStream = new DigestInputStream(inputStream, digest)) {
                byte[] buffer = new byte[8192];
                long total = 0;
                int read;
                while ((read = digestInputStream.read(buffer)) != -1) {
                    total += read;
                    if (total > MAX_UPLOAD_BYTES) {
                        throw new ApiProblemException(ErrorCodes.FILE_TOO_LARGE, "File exceeds 50 MB upload limit");
                    }
                    output.write(buffer, 0, read);
                }
            }
            return new HashedContent(output.toByteArray(), HexFormat.of().formatHex(digest.digest()));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 digest is unavailable", exception);
        } catch (IOException exception) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "Could not read uploaded file");
        }
    }

    private static String normalizeMimeType(String mimeType) {
        if (mimeType == null || mimeType.isBlank()) {
            return "";
        }
        return mimeType.split(";", 2)[0].trim().toLowerCase(Locale.ROOT);
    }

    private static String sanitizeOriginalFilename(String originalFilename) {
        if (originalFilename == null || originalFilename.isBlank()) {
            return "upload";
        }
        return originalFilename.length() <= 512 ? originalFilename : originalFilename.substring(0, 512);
    }

    private record HashedContent(byte[] content, String sha256) {
    }
}
