package com.corprag.adapter.rest;

import com.corprag.contracts.api.v1.model.CreateRoleRequest;
import com.corprag.contracts.api.v1.model.HateoasLink;
import com.corprag.contracts.api.v1.model.ListRoles200Response;
import com.corprag.contracts.api.v1.model.PermissionCode;
import com.corprag.contracts.api.v1.model.Role;
import com.corprag.contracts.api.v1.model.UpdateRoleRequest;
import com.corprag.security.Permission;
import com.corprag.service.role.RoleService;
import jakarta.validation.Valid;
import java.net.URI;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/roles")
public class RoleController {

    private final RoleService roleService;

    public RoleController(RoleService roleService) {
        this.roleService = roleService;
    }

    @GetMapping
    ListRoles200Response listRoles(@AuthenticationPrincipal Jwt jwt) {
        JwtAuthorization.requirePermission(jwt, Permission.ROLES_READ.value());
        return new ListRoles200Response()
                .items(roleService.listRoles().stream().map(this::toRole).toList())
                .links(Map.of("self", new HateoasLink().href("/api/v1/roles")));
    }

    @PostMapping
    ResponseEntity<Role> createRole(
            @AuthenticationPrincipal Jwt jwt,
            @Valid @RequestBody CreateRoleRequest request) {
        JwtAuthorization.requirePermission(jwt, Permission.ROLES_CREATE.value());
        RoleService.RoleView role = roleService.createRole(request, JwtAuthorization.userId(jwt));
        return ResponseEntity.created(URI.create("/api/v1/roles/" + role.role().id()))
                .body(toRole(role));
    }

    @GetMapping("/{roleId}")
    ResponseEntity<Role> getRole(@AuthenticationPrincipal Jwt jwt, @PathVariable("roleId") UUID roleId) {
        JwtAuthorization.requirePermission(jwt, Permission.ROLES_READ.value());
        RoleService.RoleView role = roleService.getRole(roleId);
        return ResponseEntity.ok()
                .header(HttpHeaders.ETAG, roleService.etag(role))
                .body(toRole(role));
    }

    @PutMapping("/{roleId}")
    ResponseEntity<Role> updateRole(
            @AuthenticationPrincipal Jwt jwt,
            @PathVariable("roleId") UUID roleId,
            @RequestHeader(value = HttpHeaders.IF_MATCH, required = false) String ifMatch,
            @Valid @RequestBody UpdateRoleRequest request) {
        JwtAuthorization.requirePermission(jwt, Permission.ROLES_UPDATE.value());
        RoleService.RoleView role = roleService.updateRole(roleId, request, ifMatch, JwtAuthorization.userId(jwt));
        return ResponseEntity.ok()
                .header(HttpHeaders.ETAG, roleService.etag(role))
                .body(toRole(role));
    }

    @DeleteMapping("/{roleId}")
    ResponseEntity<Void> deleteRole(@AuthenticationPrincipal Jwt jwt, @PathVariable("roleId") UUID roleId) {
        JwtAuthorization.requirePermission(jwt, Permission.ROLES_DELETE.value());
        roleService.deleteRole(roleId, JwtAuthorization.userId(jwt));
        return ResponseEntity.noContent().build();
    }

    private Role toRole(RoleService.RoleView view) {
        return new Role()
                .id(view.role().id())
                .name(view.role().code())
                .description(view.role().description())
                .permissions(view.permissions().stream()
                        .map(permission -> PermissionCode.fromValue(permission.value()))
                        .toList())
                .system(view.role().system())
                .version(view.role().version())
                .links(Map.of("self", new HateoasLink().href("/api/v1/roles/" + view.role().id())));
    }
}
