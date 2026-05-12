package com.corprag.service.role;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.api.v1.model.CreateRoleRequest;
import com.corprag.contracts.api.v1.model.PermissionCode;
import com.corprag.contracts.api.v1.model.UpdateRoleRequest;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.AuditOutcome;
import com.corprag.domain.RoleDefinition;
import com.corprag.domain.UserAccount;
import com.corprag.repository.RoleRepository;
import com.corprag.repository.UserRepository;
import com.corprag.repository.UserRoleRepository;
import com.corprag.security.Permission;
import com.corprag.security.PermissionEvaluator;
import com.corprag.service.access.AccessFilterCacheInvalidator;
import com.corprag.service.audit.AuditEventWriter;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
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
    private final UserRepository userRepository;
    private final UserRoleRepository userRoleRepository;
    private final PermissionEvaluator permissionEvaluator;
    private final AccessFilterCacheInvalidator cacheInvalidator;
    private final AuditEventWriter auditEventWriter;

    public RoleService(
            RoleRepository roleRepository,
            UserRepository userRepository,
            UserRoleRepository userRoleRepository,
            PermissionEvaluator permissionEvaluator,
            AccessFilterCacheInvalidator cacheInvalidator,
            AuditEventWriter auditEventWriter) {
        this.roleRepository = roleRepository;
        this.userRepository = userRepository;
        this.userRoleRepository = userRoleRepository;
        this.permissionEvaluator = permissionEvaluator;
        this.cacheInvalidator = cacheInvalidator;
        this.auditEventWriter = auditEventWriter;
    }

    public List<RoleView> listRoles() {
        return roleRepository.listActive().stream()
                .map(this::toView)
                .toList();
    }

    @Transactional
    public RoleView createRole(CreateRoleRequest request) {
        return createRole(request, null);
    }

    @Transactional
    public RoleView createRole(CreateRoleRequest request, UUID actorUserId) {
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
        auditEventWriter.writeEvent(
                "ROLE",
                "ROLE_CREATED",
                AuditOutcome.SUCCESS,
                actorUserId,
                null,
                "ROLE",
                role.id(),
                null,
                null,
                Map.of("role", role.code()));
        return getRole(role.id());
    }

    public RoleView getRole(UUID roleId) {
        return toView(findRole(roleId));
    }

    @Transactional
    public RoleView updateRole(UUID roleId, UpdateRoleRequest request, String ifMatch) {
        return updateRole(roleId, request, ifMatch, null);
    }

    @Transactional
    public RoleView updateRole(UUID roleId, UpdateRoleRequest request, String ifMatch, UUID actorUserId) {
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
            cacheInvalidator.invalidateForRole(roleId);
        } catch (DataIntegrityViolationException exception) {
            throw new ApiProblemException(ErrorCodes.DUPLICATE_RESOURCE, "Role already exists");
        }
        auditEventWriter.writeEvent(
                "ROLE",
                "ROLE_UPDATED",
                AuditOutcome.SUCCESS,
                actorUserId,
                null,
                "ROLE",
                roleId,
                null,
                null,
                Map.of("previous_role", existing.code(), "role", request.getName()));
        return getRole(roleId);
    }

    @Transactional
    public void deleteRole(UUID roleId) {
        deleteRole(roleId, null);
    }

    @Transactional
    public void deleteRole(UUID roleId, UUID actorUserId) {
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
        cacheInvalidator.invalidateForRole(roleId);
        auditEventWriter.writeEvent(
                "ROLE",
                "ROLE_DELETED",
                AuditOutcome.SUCCESS,
                actorUserId,
                null,
                "ROLE",
                roleId,
                null,
                null,
                Map.of("role", existing.code()));
    }

    @Transactional
    public UserRoleView replaceUserRoles(
            UUID userId,
            List<String> requestedRoleCodes,
            UUID actorUserId,
            boolean actorCanUpdateRoles) {
        if (actorUserId.equals(userId)) {
            throw new ApiProblemException(ErrorCodes.SELF_MODIFICATION_FORBIDDEN, "Users cannot change their own roles");
        }
        UserAccount user = userRepository.findById(userId)
                .orElseThrow(() -> new ApiProblemException(ErrorCodes.USER_NOT_FOUND, "User not found"));
        if (requestedRoleCodes == null || requestedRoleCodes.isEmpty()) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "At least one role is required");
        }

        List<RoleDefinition> replacementRoles = resolveRoles(requestedRoleCodes);
        if (replacementRoles.stream().anyMatch(role -> "ADMIN".equals(role.code())) && !actorCanUpdateRoles) {
            throw new ApiProblemException(
                    ErrorCodes.INSUFFICIENT_PERMISSIONS,
                    "Assigning ADMIN also requires roles.update");
        }

        List<Permission> currentPermissions = roleRepository.findPermissionsForUser(userId);
        List<Permission> replacementPermissions = permissionsForRoles(replacementRoles);
        if (currentPermissions.contains(Permission.USERS_UPDATE)
                && !replacementPermissions.contains(Permission.USERS_UPDATE)
                && roleRepository.countActiveUsersWithPermissionExcludingUser(userId, Permission.USERS_UPDATE) == 0) {
            throw new ApiProblemException(ErrorCodes.LAST_ADMIN_PROTECTED, "Mutation would remove the last users.update authority");
        }

        List<String> previousRoles = roleRepository.findRolesForUser(userId).stream()
                .map(RoleDefinition::code)
                .toList();
        userRoleRepository.replaceUserRoles(
                userId,
                replacementRoles.stream().map(RoleDefinition::id).toList(),
                actorUserId,
                Instant.now());
        cacheInvalidator.invalidate(userId);
        List<String> nextRoles = replacementRoles.stream().map(RoleDefinition::code).toList();
        auditEventWriter.writeEvent(
                "AUTHZ",
                "USER_ROLES_REPLACED",
                AuditOutcome.SUCCESS,
                actorUserId,
                userId,
                "USER",
                userId,
                null,
                null,
                Map.of("previous_roles", previousRoles, "roles", nextRoles));
        return new UserRoleView(user, nextRoles);
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

    private List<RoleDefinition> resolveRoles(List<String> roleCodes) {
        List<RoleDefinition> roles = new ArrayList<>();
        for (String code : new LinkedHashSet<>(roleCodes)) {
            roles.add(roleRepository.findByCode(code)
                    .orElseThrow(() -> new ApiProblemException(ErrorCodes.ROLE_NOT_FOUND, "Role not found: " + code)));
        }
        return roles;
    }

    private List<Permission> permissionsForRoles(List<RoleDefinition> roles) {
        return roles.stream()
                .flatMap(role -> roleRepository.findPermissions(role.id()).stream())
                .distinct()
                .toList();
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

    public record UserRoleView(UserAccount user, List<String> roles) {
    }
}
