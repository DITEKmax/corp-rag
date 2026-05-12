package com.corprag.service.auth;

import java.time.Instant;

public record AuthSession(
        AuthenticatedUser user,
        String accessToken,
        Instant accessTokenExpiresAt,
        String refreshToken) {
}
