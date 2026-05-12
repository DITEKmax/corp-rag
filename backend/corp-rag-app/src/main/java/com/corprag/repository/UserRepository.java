package com.corprag.repository;

import com.corprag.domain.UserAccount;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

@Repository
public class UserRepository {

    private static final RowMapper<UserAccount> USER_MAPPER = (rs, rowNum) -> new UserAccount(
            rs.getObject("id", UUID.class),
            rs.getString("username"),
            rs.getString("email"),
            rs.getString("full_name"),
            rs.getString("department"),
            rs.getString("password_hash"),
            rs.getBoolean("active"),
            rs.getBoolean("must_change_password"),
            JdbcRowSupport.instant(rs, "created_at"),
            JdbcRowSupport.instant(rs, "updated_at"),
            JdbcRowSupport.instant(rs, "deleted_at"),
            rs.getLong("version"));

    private final JdbcClient jdbc;

    public UserRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<UserAccount> findById(UUID id) {
        return jdbc.sql("SELECT * FROM users WHERE id = :id AND deleted_at IS NULL")
                .param("id", id)
                .query(USER_MAPPER)
                .optional();
    }

    public Optional<UserAccount> findByEmail(String email) {
        return jdbc.sql("SELECT * FROM users WHERE lower(email) = lower(:email) AND deleted_at IS NULL")
                .param("email", email)
                .query(USER_MAPPER)
                .optional();
    }

    public Optional<UserAccount> findByUsername(String username) {
        return jdbc.sql("SELECT * FROM users WHERE username = :username AND deleted_at IS NULL")
                .param("username", username)
                .query(USER_MAPPER)
                .optional();
    }

    public List<UserAccount> list(int limit, int offset) {
        return jdbc.sql("SELECT * FROM users WHERE deleted_at IS NULL ORDER BY username LIMIT :limit OFFSET :offset")
                .param("limit", limit)
                .param("offset", offset)
                .query(USER_MAPPER)
                .list();
    }

    public long count() {
        return jdbc.sql("SELECT COUNT(*) FROM users WHERE deleted_at IS NULL")
                .query(Long.class)
                .single();
    }

    public void create(UserAccount user) {
        jdbc.sql(
                        """
                        INSERT INTO users (
                            id, username, email, full_name, department, password_hash,
                            active, must_change_password, created_at, updated_at, deleted_at, version
                        )
                        VALUES (
                            :id, :username, :email, :fullName, :department, :passwordHash,
                            :active, :mustChangePassword, :createdAt, :updatedAt, :deletedAt, :version
                        )
                        """)
                .param("id", user.id())
                .param("username", user.username())
                .param("email", user.email())
                .param("fullName", user.fullName())
                .param("department", user.department())
                .param("passwordHash", user.passwordHash())
                .param("active", user.active())
                .param("mustChangePassword", user.mustChangePassword())
                .param("createdAt", JdbcRowSupport.timestamp(user.createdAt()))
                .param("updatedAt", JdbcRowSupport.timestamp(user.updatedAt()))
                .param("deletedAt", JdbcRowSupport.timestamp(user.deletedAt()))
                .param("version", user.version())
                .update();
    }

    public boolean update(UserAccount user, long expectedVersion) {
        int updated = jdbc.sql(
                        """
                        UPDATE users
                        SET email = :email,
                            full_name = :fullName,
                            department = :department,
                            password_hash = :passwordHash,
                            active = :active,
                            must_change_password = :mustChangePassword,
                            updated_at = now(),
                            version = version + 1
                        WHERE id = :id AND version = :expectedVersion AND deleted_at IS NULL
                        """)
                .param("id", user.id())
                .param("email", user.email())
                .param("fullName", user.fullName())
                .param("department", user.department())
                .param("passwordHash", user.passwordHash())
                .param("active", user.active())
                .param("mustChangePassword", user.mustChangePassword())
                .param("expectedVersion", expectedVersion)
                .update();
        return updated == 1;
    }

    public boolean softDelete(UUID userId, long expectedVersion) {
        int updated = jdbc.sql(
                        """
                        UPDATE users
                        SET active = FALSE,
                            deleted_at = now(),
                            updated_at = now(),
                            version = version + 1
                        WHERE id = :userId AND version = :expectedVersion AND deleted_at IS NULL
                        """)
                .param("userId", userId)
                .param("expectedVersion", expectedVersion)
                .update();
        return updated == 1;
    }
}
