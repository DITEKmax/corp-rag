package com.corprag.domain;

import java.time.Instant;
import java.util.UUID;

public record OutboxEventRecord(
        UUID id,
        String aggregateType,
        UUID aggregateId,
        String eventType,
        String routingKey,
        String exchangeName,
        String payloadJson,
        String headersJson,
        UUID correlationId,
        Instant createdAt,
        Instant publishedAt,
        int publishAttempts,
        String lastError,
        Instant nextAttemptAt) {
}
