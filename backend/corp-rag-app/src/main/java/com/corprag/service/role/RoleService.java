package com.corprag.service.role;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.api.v1.model.CreateRoleRequest;
import com.corprag.contracts.api.v1.model.PermissionCode;
import com.corprag.contracts.api.v1.model.UpdateRoleRequest;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.RoleDefinition;
import com.corprag.repository.RoleRepository;
import com.corprag.repository.UserRoleRepository;
import com.corprag.security.Permission;
import com.corprag.security.PermissionEvaluator;
import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RoleService {

    private static final Pattern ROLE_ETAG = Pattern.compile("\"?role-v(\\d+)\"?");

    private final RoleRepository roleRepository;
    private final UserRoleRepository userRoleRepository;
    private final PermissionEvaluator permissionEvaluator;

    public RoleService(
            RoleRepository roleRepository,
            UserRoleRepository userRoleRepository,
            PermissionEvaluator permissionEvaluator) {
        this.roleRepository = roleRepository;
        this.userRoleRepository = userRoleRepository;
        this.permissionEvaluator = permissionEvaluator;
    }

    public List<RoleView> listRoles() {
        return roleRepository.listActive().stream()
                .map(this::toView)
                .toList();
    }

    @Transactional
    public RoleView createRole(CreateRoleRequest request) {
        List<Permission> permissions = permissions(request.getPermissions());
        Instant now = Instant.now();
        RoleDefinition role = new RoleDefinition(
                UUID.randomUUID(),
                request.getName(),
                request.getDescription(),
                false,
                now,
                now,
                null,
                0);
        try {
            roleRepository.create(role);
            roleRepository.replacePermissions(role.id(), permissions);
        } catch (DataIntegrityViolationException exception) {
            throw new ApiProblemException(ErrorCodes.DUPLICATE_RESOURCE, "Role already exists");
        }
        return getRole(role.id());
    }

    public RoleView getRole(UUID roleId) {
        return toView(findRole(roleId));
    }

    @Transactional
    public RoleView updateRole(UUID roleId, UpdateRoleRequest request, String ifMatch) {
        long expectedVersion = parseIfMatch(ifMatch);
        RoleDefinition existing = findRole(roleId);
        if (existing.system()) {
            throw new ApiProblemException(ErrorCodes.SYSTEM_ROLE_PROTECTED, "System role cannot be updated");
        }

        List<Permission> permissions = permissions(request.getPermissions());
        assertUsersUpdateAuthorityPreserved(existing, permissions);
        RoleDefinition updated = new RoleDefinition(
                existing.id(),
                request.getName(),
                request.getDescription(),
                existing.system(),
                existing.createdAt(),
                existing.updatedAt(),
                existing.deletedAt(),
                existing.version());
        try {
            if (!roleRepository.update(updated, expectedVersion)) {
                throw new ApiProblemException(ErrorCodes.PRECONDITION_FAILED, "Role ETag is stale");
            }
            roleRepository.replacePermissions(roleId, permissions);
        } catch (DataIntegrityViolationException exception) {
            throw new ApiProblemException(ErrorCodes.DUPLICATE_RESOURCE, "Role already exists");
        }
        return getRole(roleId);
    }

    @Transactional
    public void deleteRole(UUID roleId) {
        RoleDefinition existing = findRole(roleId);
        if (existing.system()) {
            throw new ApiProblemException(ErrorCodes.SYSTEM_ROLE_PROTECTED, "System role cannot be deleted");
        }
        if (!userRoleRepository.findByRoleId(roleId).isEmpty()) {
            throw new ApiProblemException(ErrorCodes.DUPLICATE_RESOURCE, "Role is assigned to users");
        }
        if (!roleRepository.softDelete(roleId, existing.version())) {
            throw new ApiProblemException(ErrorCodes.PRECONDITION_FAILED, "Role version changed");
        }
    }

    public String etag(RoleView role) {
        return "\"role-v" + role.role().version() + "\"";
    }

    private RoleDefinition findRole(UUID roleId) {
        return roleRepository.findById(roleId)
                .orElseThrow(() -> new ApiProblemException(ErrorCodes.ROLE_NOT_FOUND, "Role not found"));
    }

    private RoleView toView(RoleDefinition role) {
        return new RoleView(role, roleRepository.findPermissions(role.id()));
    }

    private List<Permission> permissions(Collection<PermissionCode> permissionCodes) {
        if (permissionCodes == null || permissionCodes.isEmpty()) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "At least one permission is required");
        }
        return permissionEvaluator.requireKnown(permissionCodes.stream()
                .map(PermissionCode::getValue)
                .toList());
    }

    private long parseIfMatch(String ifMatch) {
        if (ifMatch == null || ifMatch.isBlank()) {
            throw new ApiProblemException(ErrorCodes.PRECONDITION_REQUIRED, "If-Match header is required");
        }
        Matcher matcher = ROLE_ETAG.matcher(ifMatch.trim());
        if (!matcher.matches()) {
            throw new ApiProblemException(ErrorCodes.PRECONDITION_FAILED, "Role ETag is invalid");
        }
        return Long.parseLong(matcher.group(1));
    }

    private void assertUsersUpdateAuthorityPreserved(RoleDefinition role, List<Permission> replacementPermissions) {
        boolean currentlyGrantsUsersUpdate = roleRepository.findPermissions(role.id()).contains(Permission.USERS_UPDATE);
        boolean replacementGrantsUsersUpdate = replacementPermissions.contains(Permission.USERS_UPDATE);
        if (currentlyGrantsUsersUpdate
                && !replacementGrantsUsersUpdate
                && roleRepository.countActiveUsersWithPermissionExcludingRole(role.id(), Permission.USERS_UPDATE) == 0) {
            throw new ApiProblemException(ErrorCodes.LAST_ADMIN_PROTECTED, "Mutation would remove the last users.update authority");
        }
    }

    public record RoleView(RoleDefinition role, List<Permission> permissions) {
    }
}
