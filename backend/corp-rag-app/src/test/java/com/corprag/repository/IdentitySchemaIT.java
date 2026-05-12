package com.corprag.repository;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.corprag.domain.AccessLevel;
import com.corprag.domain.AccessPolicyDefinition;
import com.corprag.domain.AuditEventEntry;
import com.corprag.domain.AuditOutcome;
import com.corprag.domain.DocType;
import com.corprag.domain.RefreshTokenSession;
import com.corprag.domain.ResolvedAccessFilter;
import com.corprag.domain.RoleDefinition;
import com.corprag.domain.UserAccount;
import com.corprag.domain.UserRoleAssignment;
import com.corprag.security.Permission;
import com.corprag.testsupport.AuthTestFixtures;
import com.corprag.testsupport.PostgresIntegrationTestSupport;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest
@Testcontainers(disabledWithoutDocker = true)
class IdentitySchemaIT extends PostgresIntegrationTestSupport {

    private static final UUID ADMIN_ROLE_ID = UUID.fromString("00000000-0000-4000-8000-000000000001");
    private static final UUID EMPLOYEE_ROLE_ID = UUID.fromString("00000000-0000-4000-8000-000000000002");
    private static final UUID VIEWER_ROLE_ID = UUID.fromString("00000000-0000-4000-8000-000000000003");

    @Autowired
    private JdbcClient jdbc;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private RefreshTokenRepository refreshTokenRepository;

    @Autowired
    private AuditEventRepository auditEventRepository;

    @Autowired
    private RoleRepository roleRepository;

    @Autowired
    private UserRoleRepository userRoleRepository;

    @Autowired
    private AccessPolicyRepository accessPolicyRepository;

    @Test
    void migratedIdentityTablesAndSeedsMatchPhaseTwoDecisions() {
        List<String> tableNames = jdbc.sql(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                        """)
                .query(String.class)
                .list();

        assertThat(tableNames)
                .contains(
                        "users",
                        "refresh_tokens",
                        "audit_events",
                        "permissions",
                        "roles",
                        "role_permissions",
                        "user_roles",
                        "access_policies");

        List<String> permissionCodes = jdbc.sql("SELECT code FROM permissions")
                .query(String.class)
                .list();
        assertThat(permissionCodes).containsExactlyInAnyOrderElementsOf(AuthTestFixtures.ALL_PERMISSIONS);
        assertThat(permissionCodes).doesNotContain("documents.update");
        assertThat(roleRepository.listPermissions())
                .extracting(Permission::value)
                .containsExactlyInAnyOrderElementsOf(AuthTestFixtures.ALL_PERMISSIONS);

        assertRolePermissions(ADMIN_ROLE_ID, AuthTestFixtures.ADMIN_PERMISSIONS.stream().toList());
        assertRolePermissions(EMPLOYEE_ROLE_ID, AuthTestFixtures.EMPLOYEE_PERMISSIONS.stream().toList());
        assertRolePermissions(VIEWER_ROLE_ID, AuthTestFixtures.VIEWER_PERMISSIONS.stream().toList());

        assertDefaultPolicy(ADMIN_ROLE_ID, 4, 0, 6);
        assertDefaultPolicy(EMPLOYEE_ROLE_ID, 2, 0, 6);
        assertDefaultPolicy(VIEWER_ROLE_ID, 1, 0, 5);
        assertThat(accessPolicyRepository.findByRoleId(VIEWER_ROLE_ID))
                .hasValueSatisfying(policy -> assertThat(policy.docTypes()).doesNotContain(DocType.REPORT));
    }

    @Test
    void constraintsRejectDuplicatePermissionsAndEmptyDocTypes() {
        assertThatThrownBy(() -> jdbc.sql(
                                """
                                INSERT INTO permissions (code, description)
                                VALUES (:code, :description)
                                """)
                        .param("code", AuthTestFixtures.PERMISSION_CHAT_QUERY)
                        .param("description", "Duplicate chat query")
                        .update())
                .isInstanceOf(DataAccessException.class);

        RoleDefinition role = newRole("EMPTY_DOC_TYPES");
        roleRepository.create(role);

        AccessPolicyDefinition invalidPolicy = new AccessPolicyDefinition(
                UUID.randomUUID(),
                role.id(),
                List.of(AccessLevel.PUBLIC),
                List.of(AuthTestFixtures.DEPARTMENT_IT),
                List.of(),
                Instant.now(),
                Instant.now(),
                0);

        assertThatThrownBy(() -> accessPolicyRepository.create(invalidPolicy))
                .isInstanceOf(DataAccessException.class);
    }

    @Test
    void repositoriesRoundTripIdentityDataAndPreserveVersionChecks() {
        Instant now = Instant.parse("2026-01-02T03:04:05Z");
        UserAccount user = new UserAccount(
                UUID.randomUUID(),
                "identity." + shortId(),
                "identity." + shortId() + "@example.com",
                "Identity User",
                AuthTestFixtures.DEPARTMENT_HR,
                "test-only-password-hash",
                true,
                true,
                now,
                now,
                null,
                0);

        userRepository.create(user);

        assertThat(userRepository.findById(user.id())).contains(user);
        assertThat(userRepository.findByEmail(user.email().toUpperCase(Locale.ROOT))).contains(user);
        assertThat(userRepository.findByUsername(user.username())).contains(user);

        UserAccount updatedUser = new UserAccount(
                user.id(),
                user.username(),
                "updated." + user.email(),
                "Updated Identity User",
                AuthTestFixtures.DEPARTMENT_FINANCE,
                "updated-test-only-password-hash",
                true,
                false,
                user.createdAt(),
                user.updatedAt(),
                null,
                user.version());

        assertThat(userRepository.update(updatedUser, 0)).isTrue();
        assertThat(userRepository.update(updatedUser, 0)).isFalse();
        assertThat(userRepository.findById(user.id()))
                .hasValueSatisfying(found -> {
                    assertThat(found.email()).isEqualTo(updatedUser.email());
                    assertThat(found.version()).isEqualTo(1);
                    assertThat(found.mustChangePassword()).isFalse();
                });

        UUID familyId = UUID.randomUUID();
        RefreshTokenSession firstToken = new RefreshTokenSession(
                UUID.randomUUID(),
                user.id(),
                "token-hash-" + shortId(),
                familyId,
                now,
                now.plusSeconds(3600),
                null,
                null,
                null,
                "127.0.0.1",
                "IdentitySchemaIT");
        RefreshTokenSession secondToken = new RefreshTokenSession(
                UUID.randomUUID(),
                user.id(),
                "token-hash-" + shortId(),
                familyId,
                now.plusSeconds(60),
                now.plusSeconds(7200),
                null,
                null,
                null,
                "127.0.0.1",
                "IdentitySchemaIT");

        refreshTokenRepository.save(firstToken);
        refreshTokenRepository.save(secondToken);

        assertThat(refreshTokenRepository.findByTokenHash(firstToken.tokenHash())).contains(firstToken);
        assertThat(refreshTokenRepository.markRotated(firstToken.id(), secondToken.id(), now.plusSeconds(90))).isTrue();
        assertThat(refreshTokenRepository.markRotated(firstToken.id(), secondToken.id(), now.plusSeconds(120))).isFalse();
        assertThat(refreshTokenRepository.revokeFamily(familyId, now.plusSeconds(180))).isEqualTo(2);
        assertThat(refreshTokenRepository.findByTokenHash(firstToken.tokenHash()))
                .hasValueSatisfying(found -> {
                    assertThat(found.rotatedToTokenId()).isEqualTo(secondToken.id());
                    assertThat(found.revokedAt()).isNotNull();
                });

        for (AuditOutcome outcome : AuditOutcome.values()) {
            auditEventRepository.insert(new AuditEventEntry(
                    UUID.randomUUID(),
                    now,
                    "AUTH",
                    "TEST_" + outcome.name(),
                    outcome,
                    user.id(),
                    user.id(),
                    "USER",
                    user.id(),
                    "127.0.0.1",
                    "IdentitySchemaIT",
                    "{}",
                    UUID.randomUUID()));
        }
        Integer auditCount = jdbc.sql("SELECT COUNT(*) FROM audit_events WHERE actor_user_id = :userId")
                .param("userId", user.id())
                .query(Integer.class)
                .single();
        assertThat(auditCount).isEqualTo(3);

        RoleDefinition role = newRole("CUSTOM_" + shortId());
        roleRepository.create(role);
        roleRepository.replacePermissions(role.id(), List.of(Permission.CHAT_QUERY, Permission.DOCUMENTS_READ));
        assertThat(roleRepository.findPermissions(role.id()))
                .containsExactly(Permission.CHAT_QUERY, Permission.DOCUMENTS_READ);

        RoleDefinition renamedRole = new RoleDefinition(
                role.id(),
                role.code(),
                "Updated custom role",
                false,
                role.createdAt(),
                role.updatedAt(),
                null,
                role.version());
        assertThat(roleRepository.update(renamedRole, 0)).isTrue();
        assertThat(roleRepository.update(renamedRole, 0)).isFalse();
        assertThat(roleRepository.findByCode(role.code()))
                .hasValueSatisfying(found -> {
                    assertThat(found.description()).isEqualTo("Updated custom role");
                    assertThat(found.version()).isEqualTo(1);
                });

        userRoleRepository.replaceUserRoles(user.id(), List.of(role.id()), user.id(), now);
        assertThat(userRoleRepository.findByUserId(user.id()))
                .extracting(UserRoleAssignment::roleId)
                .containsExactly(role.id());

        AccessPolicyDefinition policy = new AccessPolicyDefinition(
                UUID.randomUUID(),
                role.id(),
                List.of(AccessLevel.PUBLIC, AccessLevel.INTERNAL),
                List.of(AuthTestFixtures.DEPARTMENT_HR),
                List.of(DocType.POLICY, DocType.GUIDE),
                now,
                now,
                0);
        accessPolicyRepository.create(policy);
        assertThat(accessPolicyRepository.findByRoleId(role.id())).contains(policy);

        AccessPolicyDefinition updatedPolicy = new AccessPolicyDefinition(
                policy.id(),
                policy.roleId(),
                List.of(AccessLevel.CONFIDENTIAL),
                List.of(AuthTestFixtures.DEPARTMENT_FINANCE, AuthTestFixtures.DEPARTMENT_IT),
                List.of(DocType.REPORT),
                policy.createdAt(),
                policy.updatedAt(),
                policy.version());
        assertThat(accessPolicyRepository.update(updatedPolicy, 0)).isTrue();
        assertThat(accessPolicyRepository.update(updatedPolicy, 0)).isFalse();
        assertThat(accessPolicyRepository.findById(policy.id()))
                .hasValueSatisfying(found -> {
                    assertThat(found.accessLevels()).containsExactly(AccessLevel.CONFIDENTIAL);
                    assertThat(found.departments())
                            .containsExactly(AuthTestFixtures.DEPARTMENT_FINANCE, AuthTestFixtures.DEPARTMENT_IT);
                    assertThat(found.docTypes()).containsExactly(DocType.REPORT);
                    assertThat(found.version()).isEqualTo(1);
                });

        ResolvedAccessFilter resolved = accessPolicyRepository.resolveForUser(user.id());
        assertThat(resolved.accessLevels()).containsExactly(AccessLevel.CONFIDENTIAL);
        assertThat(resolved.departments())
                .containsExactly(AuthTestFixtures.DEPARTMENT_FINANCE, AuthTestFixtures.DEPARTMENT_IT);
        assertThat(resolved.docTypes()).containsExactly(DocType.REPORT);
    }

    private void assertRolePermissions(UUID roleId, List<String> expectedPermissionCodes) {
        assertThat(roleRepository.findPermissions(roleId))
                .extracting(Permission::value)
                .containsExactlyInAnyOrderElementsOf(expectedPermissionCodes);
    }

    private void assertDefaultPolicy(UUID roleId, int accessLevelCount, int departmentCount, int docTypeCount) {
        assertThat(accessPolicyRepository.findByRoleId(roleId))
                .hasValueSatisfying(policy -> {
                    assertThat(policy.accessLevels()).hasSize(accessLevelCount);
                    assertThat(policy.departments()).hasSize(departmentCount);
                    assertThat(policy.docTypes()).hasSize(docTypeCount);
                    assertThat(policy.version()).isZero();
                });
    }

    private static RoleDefinition newRole(String code) {
        Instant now = Instant.now();
        return new RoleDefinition(UUID.randomUUID(), code, "Test role " + code, false, now, now, null, 0);
    }

    private static String shortId() {
        return UUID.randomUUID()
                .toString()
                .replace("-", "")
                .substring(0, 10)
                .toUpperCase(Locale.ROOT);
    }
}
