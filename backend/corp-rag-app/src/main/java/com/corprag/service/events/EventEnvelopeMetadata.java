package com.corprag.service.events;

import java.time.Instant;
import java.util.UUID;

public record EventEnvelopeMetadata(
        UUID eventId,
        String eventType,
        String eventVersion,
        Instant occurredAt,
        UUID correlationId,
        String sourceService) {
}
