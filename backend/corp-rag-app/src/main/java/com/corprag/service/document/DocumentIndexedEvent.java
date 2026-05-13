package com.corprag.service.document;

import java.time.Instant;
import java.util.UUID;

public record DocumentIndexedEvent(
        UUID eventId,
        UUID correlationId,
        UUID documentId,
        int chunkCount,
        Instant indexedAt,
        String qdrantCollection,
        Integer neo4jEntityCount,
        Long durationMs) {
}
