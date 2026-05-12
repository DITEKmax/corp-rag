package com.corprag.adapter.rest;

import com.corprag.contracts.api.v1.model.AssignUserRolesRequest;
import com.corprag.contracts.api.v1.model.HateoasLink;
import com.corprag.contracts.api.v1.model.User;
import com.corprag.domain.UserAccount;
import com.corprag.security.Permission;
import com.corprag.service.role.RoleService;
import jakarta.validation.Valid;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.UUID;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/users/{userId}/roles")
public class UserRoleController {

    private final RoleService roleService;

    public UserRoleController(RoleService roleService) {
        this.roleService = roleService;
    }

    @PostMapping
    User assignUserRoles(
            @AuthenticationPrincipal Jwt jwt,
            @PathVariable("userId") UUID userId,
            @Valid @RequestBody AssignUserRolesRequest request) {
        JwtAuthorization.requirePermission(jwt, Permission.USERS_UPDATE.value());
        RoleService.UserRoleView view = roleService.replaceUserRoles(
                userId,
                request.getRoles(),
                JwtAuthorization.userId(jwt),
                JwtAuthorization.hasPermission(jwt, Permission.ROLES_UPDATE.value()));
        return toUser(view);
    }

    private User toUser(RoleService.UserRoleView view) {
        UserAccount user = view.user();
        return new User()
                .id(user.id())
                .username(user.username())
                .fullName(user.fullName())
                .email(user.email())
                .department(user.department())
                .roles(view.roles())
                .active(user.active())
                .mustChangePassword(user.mustChangePassword())
                .createdAt(OffsetDateTime.ofInstant(user.createdAt(), ZoneOffset.UTC))
                .links(Map.of("self", new HateoasLink().href("/api/v1/users/" + user.id())));
    }
}
