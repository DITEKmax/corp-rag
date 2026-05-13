package com.corprag.service.events;

import java.util.Objects;
import java.util.UUID;

public record InboundEventMetadata(UUID eventId, String eventType, UUID correlationId) {

    public InboundEventMetadata {
        Objects.requireNonNull(eventId, "eventId must not be null");
        Objects.requireNonNull(eventType, "eventType must not be null");
        if (eventType.isBlank()) {
            throw new IllegalArgumentException("eventType must not be blank");
        }
    }
}
