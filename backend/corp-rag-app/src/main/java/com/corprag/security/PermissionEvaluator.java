package com.corprag.security;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.repository.RoleRepository;
import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Component;

@Component
public class PermissionEvaluator {

    private final RoleRepository roleRepository;

    public PermissionEvaluator(RoleRepository roleRepository) {
        this.roleRepository = roleRepository;
    }

    public Permission requireKnown(String permissionCode) {
        return Permission.findByValue(permissionCode)
                .orElseThrow(() -> new ApiProblemException(
                        ErrorCodes.INVALID_PERMISSION_CODE,
                        "Invalid permission code: " + permissionCode));
    }

    public List<Permission> requireKnown(Collection<String> permissionCodes) {
        return permissionCodes.stream()
                .map(this::requireKnown)
                .distinct()
                .toList();
    }

    public Set<String> effectivePermissionCodes(UUID userId) {
        Set<String> permissions = new LinkedHashSet<>();
        roleRepository.findPermissionsForUser(userId).stream()
                .map(Permission::value)
                .forEach(permissions::add);
        return permissions;
    }

    public boolean hasEffectivePermission(UUID userId, Permission permission) {
        return roleRepository.findPermissionsForUser(userId).contains(permission);
    }

    public boolean hasPermission(Jwt jwt, Permission permission) {
        List<String> permissions = jwt.getClaimAsStringList("permissions");
        return permissions != null && permissions.contains(permission.value());
    }
}
