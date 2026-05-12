package com.corprag.service.role;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.api.v1.model.PermissionCode;
import com.corprag.contracts.api.v1.model.UpdateRoleRequest;
import com.corprag.domain.RoleDefinition;
import com.corprag.domain.UserRoleAssignment;
import com.corprag.repository.RoleRepository;
import com.corprag.repository.UserRoleRepository;
import com.corprag.security.Permission;
import com.corprag.security.PermissionEvaluator;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class RoleServiceTest {

    private static final UUID ROLE_ID = UUID.fromString("00000000-0000-4000-8000-00000000a001");
    private static final UUID USER_ID = UUID.fromString("00000000-0000-4000-8000-00000000b001");

    @Mock
    private RoleRepository roleRepository;

    @Mock
    private UserRoleRepository userRoleRepository;

    @Mock
    private PermissionEvaluator permissionEvaluator;

    private RoleService roleService;

    @BeforeEach
    void setUp() {
        roleService = new RoleService(roleRepository, userRoleRepository, permissionEvaluator);
    }

    @Test
    void updatesCustomRoleByFullReplacementWithEtag() {
        RoleDefinition existing = role("CUSTOM", false, 0);
        RoleDefinition updated = role("RENAMED", false, 1);
        when(roleRepository.findById(ROLE_ID)).thenReturn(Optional.of(existing), Optional.of(updated));
        when(roleRepository.findPermissions(ROLE_ID))
                .thenReturn(List.of(Permission.CHAT_QUERY), List.of(Permission.ROLES_READ));
        when(permissionEvaluator.requireKnown(List.of("roles.read"))).thenReturn(List.of(Permission.ROLES_READ));
        when(roleRepository.update(any(RoleDefinition.class), org.mockito.ArgumentMatchers.eq(0L))).thenReturn(true);

        RoleService.RoleView result = roleService.updateRole(
                ROLE_ID,
                new UpdateRoleRequest()
                        .name("RENAMED")
                        .description("Replacement")
                        .permissions(List.of(PermissionCode.ROLES_READ)),
                "\"role-v0\"");

        ArgumentCaptor<RoleDefinition> captor = ArgumentCaptor.forClass(RoleDefinition.class);
        verify(roleRepository).update(captor.capture(), org.mockito.ArgumentMatchers.eq(0L));
        assertThat(captor.getValue().code()).isEqualTo("RENAMED");
        assertThat(captor.getValue().description()).isEqualTo("Replacement");
        verify(roleRepository).replacePermissions(ROLE_ID, List.of(Permission.ROLES_READ));
        assertThat(result.role().version()).isEqualTo(1);
        assertThat(result.permissions()).containsExactly(Permission.ROLES_READ);
    }

    @Test
    void staleEtagIsRejected() {
        RoleDefinition existing = role("CUSTOM", false, 0);
        when(roleRepository.findById(ROLE_ID)).thenReturn(Optional.of(existing));
        when(roleRepository.findPermissions(ROLE_ID)).thenReturn(List.of(Permission.CHAT_QUERY));
        when(permissionEvaluator.requireKnown(List.of("roles.read"))).thenReturn(List.of(Permission.ROLES_READ));
        when(roleRepository.update(any(RoleDefinition.class), org.mockito.ArgumentMatchers.eq(99L))).thenReturn(false);

        assertProblem(
                () -> roleService.updateRole(
                        ROLE_ID,
                        new UpdateRoleRequest()
                                .name("CUSTOM")
                                .permissions(List.of(PermissionCode.ROLES_READ)),
                        "\"role-v99\""),
                "PRECONDITION_FAILED");
    }

    @Test
    void systemRolesCannotBeUpdated() {
        when(roleRepository.findById(ROLE_ID)).thenReturn(Optional.of(role("ADMIN", true, 0)));

        assertProblem(
                () -> roleService.updateRole(
                        ROLE_ID,
                        new UpdateRoleRequest()
                                .name("ADMIN")
                                .permissions(List.of(PermissionCode.CHAT_QUERY)),
                        "\"role-v0\""),
                "SYSTEM_ROLE_PROTECTED");
    }

    @Test
    void assignedCustomRolesCannotBeDeleted() {
        when(roleRepository.findById(ROLE_ID)).thenReturn(Optional.of(role("CUSTOM", false, 0)));
        when(userRoleRepository.findByRoleId(ROLE_ID)).thenReturn(List.of(new UserRoleAssignment(
                USER_ID,
                ROLE_ID,
                USER_ID,
                Instant.now())));

        assertProblem(() -> roleService.deleteRole(ROLE_ID), "DUPLICATE_RESOURCE");
    }

    private void assertProblem(Runnable action, String errorCode) {
        assertThatThrownBy(action::run)
                .isInstanceOf(ApiProblemException.class)
                .satisfies(exception -> assertThat(((ApiProblemException) exception).errorCode().code()).isEqualTo(errorCode));
    }

    private RoleDefinition role(String code, boolean system, long version) {
        Instant now = Instant.now();
        return new RoleDefinition(ROLE_ID, code, "Role " + code, system, now, now, null, version);
    }
}
