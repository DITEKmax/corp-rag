package com.corprag.service.auth;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.config.AppSecurityProperties;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.RefreshTokenSession;
import com.corprag.domain.UserAccount;
import com.corprag.repository.RefreshTokenRepository;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;
import java.util.HexFormat;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RefreshTokenService {

    private static final int TOKEN_BYTES = 32;

    private final RefreshTokenRepository refreshTokenRepository;
    private final AppSecurityProperties properties;
    private final SecureRandom secureRandom = new SecureRandom();

    public RefreshTokenService(RefreshTokenRepository refreshTokenRepository, AppSecurityProperties properties) {
        this.refreshTokenRepository = refreshTokenRepository;
        this.properties = properties;
    }

    @Transactional
    public IssuedRefreshToken issueNewFamily(UserAccount user, RequestMetadata metadata) {
        IssuedRefreshToken token = createToken(user.id(), UUID.randomUUID(), metadata);
        enforceSessionLimit(user.id());
        return token;
    }

    @Transactional(noRollbackFor = ApiProblemException.class)
    public Rotation rotate(String rawRefreshToken, RequestMetadata metadata) {
        if (rawRefreshToken == null || rawRefreshToken.isBlank()) {
            throw new ApiProblemException(ErrorCodes.REFRESH_TOKEN_INVALID, "Refresh token cookie is missing");
        }

        RefreshTokenSession existing = refreshTokenRepository.findByTokenHash(hash(rawRefreshToken))
                .orElseThrow(() -> new ApiProblemException(ErrorCodes.REFRESH_TOKEN_INVALID, "Refresh token is invalid"));
        Instant now = Instant.now();

        if (existing.rotatedToTokenId() != null) {
            refreshTokenRepository.revokeFamily(existing.familyId(), now);
            throw new ApiProblemException(ErrorCodes.REFRESH_TOKEN_REUSED, "Refresh token was already rotated");
        }
        if (existing.revokedAt() != null || !existing.expiresAt().isAfter(now)) {
            throw new ApiProblemException(ErrorCodes.REFRESH_TOKEN_INVALID, "Refresh token is expired or revoked");
        }

        IssuedRefreshToken replacement = createToken(existing.userId(), existing.familyId(), metadata);
        boolean rotated = refreshTokenRepository.markRotated(existing.id(), replacement.session().id(), now);
        if (!rotated) {
            refreshTokenRepository.revokeFamily(existing.familyId(), now);
            throw new ApiProblemException(ErrorCodes.REFRESH_TOKEN_REUSED, "Refresh token was already rotated");
        }
        return new Rotation(existing.userId(), replacement);
    }

    public int revokeAllForUser(UUID userId) {
        return refreshTokenRepository.revokeAllForUser(userId, Instant.now());
    }

    private IssuedRefreshToken createToken(UUID userId, UUID familyId, RequestMetadata metadata) {
        Instant now = Instant.now();
        Instant expiresAt = now.plusSeconds(properties.getSessions().getRefreshTokenDays() * 24L * 60L * 60L);
        String rawToken = randomToken();
        RefreshTokenSession session = new RefreshTokenSession(
                UUID.randomUUID(),
                userId,
                hash(rawToken),
                familyId,
                now,
                expiresAt,
                now,
                null,
                null,
                metadata.ipAddress(),
                metadata.userAgent());
        refreshTokenRepository.save(session);
        return new IssuedRefreshToken(rawToken, session);
    }

    private void enforceSessionLimit(UUID userId) {
        List<RefreshTokenSession> activeTokens =
                refreshTokenRepository.findActiveTerminalTokensForUser(userId, Instant.now());
        int excess = activeTokens.size() - properties.getSessions().getMaxActive();
        for (int index = 0; index < excess; index++) {
            refreshTokenRepository.revokeFamily(activeTokens.get(index).familyId(), Instant.now());
        }
    }

    private String randomToken() {
        byte[] bytes = new byte[TOKEN_BYTES];
        secureRandom.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    public static String hash(String token) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(token.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is not available", exception);
        }
    }

    public record IssuedRefreshToken(String rawToken, RefreshTokenSession session) {
    }

    public record Rotation(UUID userId, IssuedRefreshToken refreshToken) {
    }
}
