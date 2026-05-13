package com.corprag.service.document;

public record PreparedDocumentUpload(
        byte[] content,
        String originalFilename,
        String declaredMimeType,
        String sniffedMimeType,
        boolean mimeMismatch,
        long sizeBytes,
        String contentSha256,
        String objectKey) {
}
