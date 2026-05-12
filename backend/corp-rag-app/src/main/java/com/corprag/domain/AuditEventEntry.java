package com.corprag.domain;

import java.time.Instant;
import java.util.UUID;

public record AuditEventEntry(
        UUID id,
        Instant occurredAt,
        String eventCategory,
        String eventType,
        AuditOutcome outcome,
        UUID actorUserId,
        UUID targetUserId,
        String entityType,
        UUID entityId,
        String ipAddress,
        String userAgent,
        String detailsJson,
        UUID correlationId) {
}
