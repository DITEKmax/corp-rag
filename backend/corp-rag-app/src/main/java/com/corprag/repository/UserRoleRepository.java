package com.corprag.repository;

import com.corprag.domain.UserRoleAssignment;
import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.UUID;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

@Repository
public class UserRoleRepository {

    private static final RowMapper<UserRoleAssignment> USER_ROLE_MAPPER = (rs, rowNum) -> new UserRoleAssignment(
            rs.getObject("user_id", UUID.class),
            rs.getObject("role_id", UUID.class),
            rs.getObject("assigned_by", UUID.class),
            JdbcRowSupport.instant(rs, "assigned_at"));

    private final JdbcClient jdbc;

    public UserRoleRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public List<UserRoleAssignment> findByUserId(UUID userId) {
        return jdbc.sql("SELECT * FROM user_roles WHERE user_id = :userId ORDER BY assigned_at, role_id")
                .param("userId", userId)
                .query(USER_ROLE_MAPPER)
                .list();
    }

    public List<UserRoleAssignment> findByRoleId(UUID roleId) {
        return jdbc.sql("SELECT * FROM user_roles WHERE role_id = :roleId ORDER BY assigned_at, user_id")
                .param("roleId", roleId)
                .query(USER_ROLE_MAPPER)
                .list();
    }

    @Transactional
    public void replaceUserRoles(UUID userId, Collection<UUID> roleIds, UUID assignedBy, Instant assignedAt) {
        jdbc.sql("DELETE FROM user_roles WHERE user_id = :userId")
                .param("userId", userId)
                .update();
        for (UUID roleId : roleIds) {
            jdbc.sql(
                            """
                            INSERT INTO user_roles (user_id, role_id, assigned_by, assigned_at)
                            VALUES (:userId, :roleId, :assignedBy, :assignedAt)
                            """)
                    .param("userId", userId)
                    .param("roleId", roleId)
                    .param("assignedBy", assignedBy)
                    .param("assignedAt", JdbcRowSupport.timestamp(assignedAt))
                    .update();
        }
    }
}
