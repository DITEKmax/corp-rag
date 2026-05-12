package com.corprag.domain;

import java.time.Instant;
import java.util.UUID;

public record RefreshTokenSession(
        UUID id,
        UUID userId,
        String tokenHash,
        UUID familyId,
        Instant issuedAt,
        Instant expiresAt,
        Instant lastUsedAt,
        Instant revokedAt,
        UUID rotatedToTokenId,
        String ipAddress,
        String userAgent) {
}
