package com.corprag.domain;

import java.time.Instant;
import java.util.UUID;

public record ProcessedEventRecord(
        UUID eventId,
        String eventType,
        UUID correlationId,
        Instant processedAt) {
}
