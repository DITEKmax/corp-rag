package com.corprag.repository;

import com.corprag.domain.RefreshTokenSession;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
public class RefreshTokenRepository {

    private static final RowMapper<RefreshTokenSession> TOKEN_MAPPER = (rs, rowNum) -> new RefreshTokenSession(
            rs.getObject("id", UUID.class),
            rs.getObject("user_id", UUID.class),
            rs.getString("token_hash"),
            rs.getObject("family_id", UUID.class),
            JdbcRowSupport.instant(rs, "issued_at"),
            JdbcRowSupport.instant(rs, "expires_at"),
            JdbcRowSupport.instant(rs, "last_used_at"),
            JdbcRowSupport.instant(rs, "revoked_at"),
            rs.getObject("rotated_to_token_id", UUID.class),
            rs.getString("ip_address"),
            rs.getString("user_agent"));

    private final JdbcClient jdbc;

    public RefreshTokenRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<RefreshTokenSession> findByTokenHash(String tokenHash) {
        return jdbc.sql("SELECT * FROM refresh_tokens WHERE token_hash = :tokenHash")
                .param("tokenHash", tokenHash)
                .query(TOKEN_MAPPER)
                .optional();
    }

    public List<RefreshTokenSession> findActiveTerminalTokensForUser(UUID userId, Instant now) {
        return jdbc.sql(
                        """
                        SELECT *
                        FROM refresh_tokens
                        WHERE user_id = :userId
                          AND revoked_at IS NULL
                          AND rotated_to_token_id IS NULL
                          AND expires_at > :now
                        ORDER BY COALESCE(last_used_at, issued_at), issued_at
                        """)
                .param("userId", userId)
                .param("now", JdbcRowSupport.timestamp(now))
                .query(TOKEN_MAPPER)
                .list();
    }

    public void save(RefreshTokenSession token) {
        jdbc.sql(
                        """
                        INSERT INTO refresh_tokens (
                            id, user_id, token_hash, family_id, issued_at, expires_at,
                            last_used_at, revoked_at, rotated_to_token_id, ip_address, user_agent
                        )
                        VALUES (
                            :id, :userId, :tokenHash, :familyId, :issuedAt, :expiresAt,
                            :lastUsedAt, :revokedAt, :rotatedToTokenId, :ipAddress, :userAgent
                        )
                        """)
                .param("id", token.id())
                .param("userId", token.userId())
                .param("tokenHash", token.tokenHash())
                .param("familyId", token.familyId())
                .param("issuedAt", JdbcRowSupport.timestamp(token.issuedAt()))
                .param("expiresAt", JdbcRowSupport.timestamp(token.expiresAt()))
                .param("lastUsedAt", JdbcRowSupport.timestamp(token.lastUsedAt()))
                .param("revokedAt", JdbcRowSupport.timestamp(token.revokedAt()))
                .param("rotatedToTokenId", token.rotatedToTokenId())
                .param("ipAddress", token.ipAddress())
                .param("userAgent", token.userAgent())
                .update();
    }

    public int revokeFamily(UUID familyId, Instant revokedAt) {
        return jdbc.sql(
                        """
                        UPDATE refresh_tokens
                        SET revoked_at = COALESCE(revoked_at, :revokedAt)
                        WHERE family_id = :familyId
                        """)
                .param("familyId", familyId)
                .param("revokedAt", JdbcRowSupport.timestamp(revokedAt))
                .update();
    }

    public int revokeAllForUser(UUID userId, Instant revokedAt) {
        return jdbc.sql(
                        """
                        UPDATE refresh_tokens
                        SET revoked_at = COALESCE(revoked_at, :revokedAt)
                        WHERE user_id = :userId
                          AND revoked_at IS NULL
                        """)
                .param("userId", userId)
                .param("revokedAt", JdbcRowSupport.timestamp(revokedAt))
                .update();
    }

    public boolean markRotated(UUID tokenId, UUID rotatedToTokenId, Instant lastUsedAt) {
        int updated = jdbc.sql(
                        """
                        UPDATE refresh_tokens
                        SET rotated_to_token_id = :rotatedToTokenId,
                            last_used_at = :lastUsedAt
                        WHERE id = :tokenId AND rotated_to_token_id IS NULL
                        """)
                .param("tokenId", tokenId)
                .param("rotatedToTokenId", rotatedToTokenId)
                .param("lastUsedAt", JdbcRowSupport.timestamp(lastUsedAt))
                .update();
        return updated == 1;
    }
}
