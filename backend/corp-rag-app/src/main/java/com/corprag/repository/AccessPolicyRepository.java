package com.corprag.repository;

import com.corprag.domain.AccessLevel;
import com.corprag.domain.AccessPolicyDefinition;
import com.corprag.domain.DocType;
import com.corprag.domain.ResolvedAccessFilter;
import java.sql.PreparedStatement;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class AccessPolicyRepository {

    private static final RowMapper<AccessPolicyDefinition> POLICY_MAPPER = (rs, rowNum) -> new AccessPolicyDefinition(
            rs.getObject("id", UUID.class),
            rs.getObject("role_id", UUID.class),
            JdbcRowSupport.stringArray(rs, "access_levels").stream()
                    .map(AccessLevel::valueOf)
                    .toList(),
            JdbcRowSupport.stringArray(rs, "departments"),
            JdbcRowSupport.stringArray(rs, "doc_types").stream()
                    .map(DocType::valueOf)
                    .toList(),
            JdbcRowSupport.instant(rs, "created_at"),
            JdbcRowSupport.instant(rs, "updated_at"),
            rs.getLong("version"));

    private final JdbcClient jdbc;
    private final JdbcTemplate jdbcTemplate;

    public AccessPolicyRepository(JdbcClient jdbc, JdbcTemplate jdbcTemplate) {
        this.jdbc = jdbc;
        this.jdbcTemplate = jdbcTemplate;
    }

    public Optional<AccessPolicyDefinition> findById(UUID id) {
        return jdbc.sql("SELECT * FROM access_policies WHERE id = :id")
                .param("id", id)
                .query(POLICY_MAPPER)
                .optional();
    }

    public List<AccessPolicyDefinition> list() {
        return jdbc.sql(
                        """
                        SELECT ap.*
                        FROM access_policies ap
                        JOIN roles r ON r.id = ap.role_id
                        WHERE r.deleted_at IS NULL
                        ORDER BY r.code
                        """)
                .query(POLICY_MAPPER)
                .list();
    }

    public Optional<AccessPolicyDefinition> findByRoleId(UUID roleId) {
        return jdbc.sql("SELECT * FROM access_policies WHERE role_id = :roleId")
                .param("roleId", roleId)
                .query(POLICY_MAPPER)
                .optional();
    }

    public List<AccessPolicyDefinition> findPoliciesForUser(UUID userId) {
        return jdbc.sql(
                        """
                        SELECT ap.*
                        FROM access_policies ap
                        JOIN user_roles ur ON ur.role_id = ap.role_id
                        JOIN roles r ON r.id = ap.role_id
                        WHERE ur.user_id = :userId
                          AND r.deleted_at IS NULL
                        ORDER BY r.code
                        """)
                .param("userId", userId)
                .query(POLICY_MAPPER)
                .list();
    }

    public ResolvedAccessFilter resolveForUser(UUID userId) {
        List<AccessPolicyDefinition> policies = findPoliciesForUser(userId);
        List<AccessLevel> accessLevels = policies.stream()
                .flatMap(policy -> policy.accessLevels().stream())
                .distinct()
                .sorted((left, right) -> Integer.compare(left.rank(), right.rank()))
                .toList();
        List<String> departments = policies.stream()
                .flatMap(policy -> policy.departments().stream())
                .distinct()
                .sorted()
                .toList();
        List<DocType> docTypes = policies.stream()
                .flatMap(policy -> policy.docTypes().stream())
                .distinct()
                .sorted()
                .toList();
        return new ResolvedAccessFilter(accessLevels, departments, docTypes);
    }

    public void create(AccessPolicyDefinition policy) {
        jdbcTemplate.update(connection -> {
            PreparedStatement statement = connection.prepareStatement(
                    """
                    INSERT INTO access_policies (
                        id, role_id, access_levels, departments, doc_types, created_at, updated_at, version
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """);
            statement.setObject(1, policy.id());
            statement.setObject(2, policy.roleId());
            statement.setArray(3, connection.createArrayOf("text", accessLevelNames(policy.accessLevels())));
            statement.setArray(4, connection.createArrayOf("text", policy.departments().toArray(String[]::new)));
            statement.setArray(5, connection.createArrayOf("text", docTypeNames(policy.docTypes())));
            statement.setTimestamp(6, timestamp(policy.createdAt()));
            statement.setTimestamp(7, timestamp(policy.updatedAt()));
            statement.setLong(8, policy.version());
            return statement;
        });
    }

    public boolean update(AccessPolicyDefinition policy, long expectedVersion) {
        int updated = jdbcTemplate.update(connection -> {
            PreparedStatement statement = connection.prepareStatement(
                    """
                    UPDATE access_policies
                    SET access_levels = ?,
                        departments = ?,
                        doc_types = ?,
                        updated_at = now(),
                        version = version + 1
                    WHERE id = ?
                      AND version = ?
                    """);
            statement.setArray(1, connection.createArrayOf("text", accessLevelNames(policy.accessLevels())));
            statement.setArray(2, connection.createArrayOf("text", policy.departments().toArray(String[]::new)));
            statement.setArray(3, connection.createArrayOf("text", docTypeNames(policy.docTypes())));
            statement.setObject(4, policy.id());
            statement.setLong(5, expectedVersion);
            return statement;
        });
        return updated == 1;
    }

    public boolean deleteByRoleId(UUID roleId) {
        int updated = jdbc.sql("DELETE FROM access_policies WHERE role_id = :roleId")
                .param("roleId", roleId)
                .update();
        return updated == 1;
    }

    public boolean deleteById(UUID id) {
        int updated = jdbc.sql("DELETE FROM access_policies WHERE id = :id")
                .param("id", id)
                .update();
        return updated == 1;
    }

    public long countActiveUsersWithRole(UUID roleId) {
        return jdbc.sql(
                        """
                        SELECT COUNT(DISTINCT ur.user_id)
                        FROM user_roles ur
                        JOIN users u ON u.id = ur.user_id
                        JOIN roles r ON r.id = ur.role_id
                        WHERE ur.role_id = :roleId
                          AND u.active = TRUE
                          AND u.deleted_at IS NULL
                          AND r.deleted_at IS NULL
                        """)
                .param("roleId", roleId)
                .query(Long.class)
                .single();
    }

    public long countActiveUsersWithFullVisibilityExcludingRole(UUID excludedRoleId) {
        return jdbc.sql(
                        """
                        SELECT COUNT(DISTINCT ur.user_id)
                        FROM user_roles ur
                        JOIN users u ON u.id = ur.user_id
                        JOIN roles r ON r.id = ur.role_id
                        JOIN access_policies ap ON ap.role_id = r.id
                        WHERE ur.role_id <> :excludedRoleId
                          AND u.active = TRUE
                          AND u.deleted_at IS NULL
                          AND r.deleted_at IS NULL
                          AND 'RESTRICTED' = ANY(ap.access_levels)
                          AND cardinality(ap.departments) = 0
                          AND ap.doc_types @> ARRAY['POLICY', 'REGULATION', 'GUIDE', 'REPORT', 'MANUAL', 'OTHER']::TEXT[]
                        """)
                .param("excludedRoleId", excludedRoleId)
                .query(Long.class)
                .single();
    }

    private static String[] accessLevelNames(Collection<AccessLevel> accessLevels) {
        return accessLevels.stream()
                .map(AccessLevel::name)
                .toArray(String[]::new);
    }

    private static String[] docTypeNames(Collection<DocType> docTypes) {
        return docTypes.stream()
                .map(DocType::name)
                .toArray(String[]::new);
    }

    private static Timestamp timestamp(Instant value) {
        return value == null ? null : Timestamp.from(value);
    }
}
