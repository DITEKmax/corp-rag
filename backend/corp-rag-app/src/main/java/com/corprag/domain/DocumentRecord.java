package com.corprag.domain;

import java.time.Instant;
import java.util.UUID;

public record DocumentRecord(
        UUID id,
        String title,
        String description,
        String originalFilename,
        String mimeType,
        long sizeBytes,
        AccessLevel accessLevel,
        String department,
        DocType docType,
        String language,
        DocumentStatus status,
        UUID ownerUserId,
        String storageBucket,
        String storageKey,
        String contentSha256,
        Instant uploadedAt,
        Instant indexedAt,
        Integer chunkCount,
        String failureStage,
        String failureErrorCode,
        String failureMessage,
        Boolean failureRetryable,
        Integer failureRetryCount,
        String qdrantCollection,
        Integer neo4jEntityCount,
        Long indexingDurationMs,
        Instant deletedAt,
        UUID deletedBy) {
}
