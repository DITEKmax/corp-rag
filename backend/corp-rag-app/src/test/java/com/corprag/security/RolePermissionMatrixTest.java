package com.corprag.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.domain.RoleDefinition;
import com.corprag.domain.UserAccount;
import com.corprag.repository.RoleRepository;
import com.corprag.repository.UserRepository;
import com.corprag.repository.UserRoleRepository;
import com.corprag.testsupport.AuthTestFixtures;
import com.corprag.testsupport.PostgresIntegrationTestSupport;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest
@Testcontainers(disabledWithoutDocker = true)
class RolePermissionMatrixTest extends PostgresIntegrationTestSupport {

    @Autowired
    private RoleRepository roleRepository;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private UserRoleRepository userRoleRepository;

    @Autowired
    private PermissionEvaluator permissionEvaluator;

    @Test
    void permissionConstantsMatchPhaseTwoContract() {
        assertThat(Permission.codes())
                .containsExactlyElementsOf(AuthTestFixtures.ALL_PERMISSIONS)
                .doesNotContain("documents.update");
        assertThat(Permission.codeSet()).hasSize(16);
    }

    @Test
    void unknownPermissionCodesFailClosed() {
        assertThatThrownBy(() -> permissionEvaluator.requireKnown("documents.update"))
                .isInstanceOf(ApiProblemException.class)
                .extracting(exception -> ((ApiProblemException) exception).errorCode().code())
                .isEqualTo("INVALID_PERMISSION_CODE");
    }

    @Test
    void seededSystemRolesMatchPhaseTwoPermissionMatrix() {
        assertThat(rolePermissions("ADMIN")).containsExactlyInAnyOrderElementsOf(AuthTestFixtures.ADMIN_PERMISSIONS);
        assertThat(rolePermissions("EMPLOYEE")).containsExactlyInAnyOrderElementsOf(AuthTestFixtures.EMPLOYEE_PERMISSIONS);
        assertThat(rolePermissions("VIEWER")).containsExactlyInAnyOrderElementsOf(AuthTestFixtures.VIEWER_PERMISSIONS);
    }

    @Test
    void effectivePermissionsAreUnionAcrossMultipleRoles() {
        RoleDefinition employee = roleRepository.findByCode("EMPLOYEE").orElseThrow();
        RoleDefinition custom = customRole(
                "MATRIX_" + shortId(),
                List.of(Permission.ROLES_READ, Permission.DOCUMENTS_DELETE));
        UserAccount user = createUser();

        userRoleRepository.replaceUserRoles(user.id(), List.of(employee.id(), custom.id()), user.id(), Instant.now());

        assertThat(permissionEvaluator.effectivePermissionCodes(user.id()))
                .containsExactlyInAnyOrder(
                        "chat.query",
                        "documents.read",
                        "documents.upload",
                        "users.read",
                        "roles.read",
                        "documents.delete");
    }

    private List<String> rolePermissions(String code) {
        RoleDefinition role = roleRepository.findByCode(code).orElseThrow();
        return roleRepository.findPermissions(role.id()).stream()
                .map(Permission::value)
                .toList();
    }

    private RoleDefinition customRole(String code, List<Permission> permissions) {
        Instant now = Instant.now();
        RoleDefinition role = new RoleDefinition(
                UUID.randomUUID(),
                code,
                "Matrix role " + code,
                false,
                now,
                now,
                null,
                0);
        roleRepository.create(role);
        roleRepository.replacePermissions(role.id(), permissions);
        return role;
    }

    private UserAccount createUser() {
        String suffix = shortId().toLowerCase(Locale.ROOT);
        Instant now = Instant.now();
        UserAccount user = new UserAccount(
                UUID.randomUUID(),
                "matrix_" + suffix,
                "matrix_" + suffix + "@example.com",
                "Matrix " + suffix,
                AuthTestFixtures.DEPARTMENT_IT,
                "hash",
                true,
                false,
                now,
                now,
                null,
                0);
        userRepository.create(user);
        return user;
    }

    private String shortId() {
        return UUID.randomUUID().toString().replace("-", "").substring(0, 10).toUpperCase(Locale.ROOT);
    }
}
