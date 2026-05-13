package com.corprag.service.document;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.constants.ErrorCodes;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class DocumentUploadPreparerTest {

    private static final UUID DOCUMENT_ID = UUID.fromString("d8f3a1c2-e89b-42d3-a456-426614174000");
    private static final Instant UPLOADED_AT = Instant.parse("2026-05-13T12:34:56Z");

    private final DocumentUploadPreparer preparer = new DocumentUploadPreparer();

    @Test
    void mimeAllowlistCoversOnlySupportedDocumentTypes() {
        assertThat(AllowedDocumentMimeType.find("application/pdf")).hasValue(AllowedDocumentMimeType.PDF);
        assertThat(AllowedDocumentMimeType.find("application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
                .hasValue(AllowedDocumentMimeType.DOCX);
        assertThat(AllowedDocumentMimeType.find("text/html; charset=UTF-8")).hasValue(AllowedDocumentMimeType.HTML);
        assertThat(AllowedDocumentMimeType.find("text/markdown")).hasValue(AllowedDocumentMimeType.MARKDOWN);
        assertThat(AllowedDocumentMimeType.find("text/plain")).hasValue(AllowedDocumentMimeType.TEXT);
        assertThat(AllowedDocumentMimeType.find("image/png")).isEmpty();
    }

    @Test
    void preparesUploadWithSha256SniffedMimeAndGeneratedObjectKey() {
        byte[] content = "plain text document".getBytes(StandardCharsets.UTF_8);

        PreparedDocumentUpload upload = preparer.prepare(
                new ByteArrayInputStream(content),
                "original-name.txt",
                "application/pdf",
                content.length,
                DOCUMENT_ID,
                UPLOADED_AT);

        assertThat(upload.content()).isEqualTo(content);
        assertThat(upload.contentSha256()).hasSize(64).matches("[a-f0-9]{64}");
        assertThat(upload.sniffedMimeType()).isEqualTo("text/plain");
        assertThat(upload.declaredMimeType()).isEqualTo("application/pdf");
        assertThat(upload.mimeMismatch()).isTrue();
        assertThat(upload.objectKey()).isEqualTo("2026/05/" + DOCUMENT_ID + ".txt");
        assertThat(upload.objectKey()).doesNotContain("original-name");
    }

    @Test
    void rejectsUnsupportedSniffedMimeType() {
        byte[] png = new byte[] {
                (byte) 0x89, 'P', 'N', 'G', '\r', '\n', 0x1A, '\n', 0, 0, 0, '\r', 'I', 'H', 'D', 'R'
        };

        assertThatThrownBy(() -> preparer.prepare(
                        new ByteArrayInputStream(png),
                        "image.png",
                        "image/png",
                        png.length,
                        DOCUMENT_ID,
                        UPLOADED_AT))
                .isInstanceOf(ApiProblemException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCodes.UNSUPPORTED_FILE_TYPE);
    }
}
