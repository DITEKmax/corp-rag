package com.corprag.repository;

import com.corprag.domain.RoleDefinition;
import com.corprag.security.Permission;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

@Repository
public class RoleRepository {

    private static final RowMapper<RoleDefinition> ROLE_MAPPER = (rs, rowNum) -> new RoleDefinition(
            rs.getObject("id", UUID.class),
            rs.getString("code"),
            rs.getString("description"),
            rs.getBoolean("is_system"),
            JdbcRowSupport.instant(rs, "created_at"),
            JdbcRowSupport.instant(rs, "updated_at"),
            JdbcRowSupport.instant(rs, "deleted_at"),
            rs.getLong("version"));

    private final JdbcClient jdbc;

    public RoleRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public List<Permission> listPermissions() {
        return jdbc.sql("SELECT code FROM permissions ORDER BY code")
                .query((rs, rowNum) -> Permission.fromValue(rs.getString("code")))
                .list();
    }

    public List<RoleDefinition> listActive() {
        return jdbc.sql("SELECT * FROM roles WHERE deleted_at IS NULL ORDER BY code")
                .query(ROLE_MAPPER)
                .list();
    }

    public Optional<RoleDefinition> findById(UUID id) {
        return jdbc.sql("SELECT * FROM roles WHERE id = :id AND deleted_at IS NULL")
                .param("id", id)
                .query(ROLE_MAPPER)
                .optional();
    }

    public Optional<RoleDefinition> findByCode(String code) {
        return jdbc.sql("SELECT * FROM roles WHERE code = :code AND deleted_at IS NULL")
                .param("code", code)
                .query(ROLE_MAPPER)
                .optional();
    }

    public void create(RoleDefinition role) {
        jdbc.sql(
                        """
                        INSERT INTO roles (id, code, description, is_system, created_at, updated_at, deleted_at, version)
                        VALUES (:id, :code, :description, :system, :createdAt, :updatedAt, :deletedAt, :version)
                        """)
                .param("id", role.id())
                .param("code", role.code())
                .param("description", role.description())
                .param("system", role.system())
                .param("createdAt", JdbcRowSupport.timestamp(role.createdAt()))
                .param("updatedAt", JdbcRowSupport.timestamp(role.updatedAt()))
                .param("deletedAt", JdbcRowSupport.timestamp(role.deletedAt()))
                .param("version", role.version())
                .update();
    }

    public boolean update(RoleDefinition role, long expectedVersion) {
        int updated = jdbc.sql(
                        """
                        UPDATE roles
                        SET code = :code,
                            description = :description,
                            updated_at = now(),
                            version = version + 1
                        WHERE id = :id
                          AND version = :expectedVersion
                          AND is_system = FALSE
                          AND deleted_at IS NULL
                        """)
                .param("id", role.id())
                .param("code", role.code())
                .param("description", role.description())
                .param("expectedVersion", expectedVersion)
                .update();
        return updated == 1;
    }

    public List<Permission> findPermissions(UUID roleId) {
        return jdbc.sql(
                        """
                        SELECT permission_code
                        FROM role_permissions
                        WHERE role_id = :roleId
                        ORDER BY permission_code
                        """)
                .param("roleId", roleId)
                .query((rs, rowNum) -> Permission.fromValue(rs.getString("permission_code")))
                .list();
    }

    public List<RoleDefinition> findRolesForUser(UUID userId) {
        return jdbc.sql(
                        """
                        SELECT r.*
                        FROM roles r
                        JOIN user_roles ur ON ur.role_id = r.id
                        WHERE ur.user_id = :userId
                          AND r.deleted_at IS NULL
                        ORDER BY r.code
                        """)
                .param("userId", userId)
                .query(ROLE_MAPPER)
                .list();
    }

    public List<Permission> findPermissionsForUser(UUID userId) {
        return jdbc.sql(
                        """
                        SELECT DISTINCT rp.permission_code
                        FROM user_roles ur
                        JOIN roles r ON r.id = ur.role_id
                        JOIN role_permissions rp ON rp.role_id = r.id
                        WHERE ur.user_id = :userId
                          AND r.deleted_at IS NULL
                        ORDER BY rp.permission_code
                        """)
                .param("userId", userId)
                .query((rs, rowNum) -> Permission.fromValue(rs.getString("permission_code")))
                .list();
    }

    public long countActiveUsersWithPermissionExcludingRole(UUID excludedRoleId, Permission permission) {
        return jdbc.sql(
                        """
                        SELECT COUNT(DISTINCT ur.user_id)
                        FROM user_roles ur
                        JOIN users u ON u.id = ur.user_id
                        JOIN roles r ON r.id = ur.role_id
                        JOIN role_permissions rp ON rp.role_id = r.id
                        WHERE ur.role_id <> :excludedRoleId
                          AND rp.permission_code = :permissionCode
                          AND u.active = TRUE
                          AND u.deleted_at IS NULL
                          AND r.deleted_at IS NULL
                        """)
                .param("excludedRoleId", excludedRoleId)
                .param("permissionCode", permission.value())
                .query(Long.class)
                .single();
    }

    @Transactional
    public void replacePermissions(UUID roleId, Collection<Permission> permissions) {
        jdbc.sql("DELETE FROM role_permissions WHERE role_id = :roleId")
                .param("roleId", roleId)
                .update();
        for (Permission permission : permissions) {
            jdbc.sql(
                            """
                            INSERT INTO role_permissions (role_id, permission_code)
                            VALUES (:roleId, :permissionCode)
                            """)
                    .param("roleId", roleId)
                    .param("permissionCode", permission.value())
                    .update();
        }
    }

    public boolean softDelete(UUID roleId, long expectedVersion) {
        int updated = jdbc.sql(
                        """
                        UPDATE roles
                        SET deleted_at = now(),
                            updated_at = now(),
                            version = version + 1
                        WHERE id = :roleId
                          AND version = :expectedVersion
                          AND is_system = FALSE
                          AND deleted_at IS NULL
                        """)
                .param("roleId", roleId)
                .param("expectedVersion", expectedVersion)
                .update();
        return updated == 1;
    }
}
