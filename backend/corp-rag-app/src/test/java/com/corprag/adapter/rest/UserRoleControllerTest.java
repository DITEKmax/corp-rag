package com.corprag.adapter.rest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.corprag.contracts.api.v1.model.AssignUserRolesRequest;
import com.corprag.contracts.api.v1.model.User;
import com.corprag.domain.UserAccount;
import com.corprag.service.role.RoleService;
import com.corprag.testsupport.AuthTestFixtures;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.oauth2.jwt.Jwt;

@ExtendWith(MockitoExtension.class)
class UserRoleControllerTest {

    private static final UUID ACTOR_ID = UUID.fromString("00000000-0000-4000-8000-00000000c001");
    private static final UUID TARGET_ID = UUID.fromString("00000000-0000-4000-8000-00000000c002");

    @Mock
    private RoleService roleService;

    private UserRoleController controller;

    @BeforeEach
    void setUp() {
        controller = new UserRoleController(roleService);
    }

    @Test
    void mapsReplaceSetResponse() {
        AssignUserRolesRequest request = new AssignUserRolesRequest().roles(List.of("EMPLOYEE"));
        when(roleService.replaceUserRoles(TARGET_ID, request.getRoles(), ACTOR_ID, false))
                .thenReturn(new RoleService.UserRoleView(user(), List.of("EMPLOYEE")));

        User response = controller.assignUserRoles(
                jwtWith(ACTOR_ID, AuthTestFixtures.PERMISSION_USERS_UPDATE),
                TARGET_ID,
                request);

        assertThat(response.getId()).isEqualTo(TARGET_ID);
        assertThat(response.getRoles()).containsExactly("EMPLOYEE");
        verify(roleService).replaceUserRoles(TARGET_ID, request.getRoles(), ACTOR_ID, false);
    }

    @Test
    void passesAdditionalRolesUpdatePermissionToService() {
        AssignUserRolesRequest request = new AssignUserRolesRequest().roles(List.of("ADMIN"));
        when(roleService.replaceUserRoles(TARGET_ID, request.getRoles(), ACTOR_ID, true))
                .thenReturn(new RoleService.UserRoleView(user(), List.of("ADMIN")));

        controller.assignUserRoles(
                jwtWith(
                        ACTOR_ID,
                        AuthTestFixtures.PERMISSION_USERS_UPDATE,
                        AuthTestFixtures.PERMISSION_ROLES_UPDATE),
                TARGET_ID,
                request);

        verify(roleService).replaceUserRoles(TARGET_ID, request.getRoles(), ACTOR_ID, true);
    }

    @Test
    void requiresUsersUpdatePermission() {
        AssignUserRolesRequest request = new AssignUserRolesRequest().roles(List.of("EMPLOYEE"));

        assertThatThrownBy(() -> controller.assignUserRoles(
                        jwtWith(ACTOR_ID, AuthTestFixtures.PERMISSION_USERS_READ),
                        TARGET_ID,
                        request))
                .isInstanceOf(ApiProblemException.class)
                .satisfies(exception -> assertThat(((ApiProblemException) exception).errorCode().code())
                        .isEqualTo("INSUFFICIENT_PERMISSIONS"));
        verifyNoInteractions(roleService);
    }

    private Jwt jwtWith(UUID subject, String... permissions) {
        return Jwt.withTokenValue("test-token")
                .header("alg", "none")
                .subject(subject.toString())
                .claim("permissions", List.of(permissions))
                .claim("roles", List.of(AuthTestFixtures.ROLE_ADMIN))
                .claim("must_change_password", false)
                .build();
    }

    private UserAccount user() {
        Instant now = Instant.now();
        return new UserAccount(
                TARGET_ID,
                "target.user",
                "target.user@example.com",
                "Target User",
                AuthTestFixtures.DEPARTMENT_IT,
                "hash",
                true,
                false,
                now,
                now,
                null,
                0);
    }
}
