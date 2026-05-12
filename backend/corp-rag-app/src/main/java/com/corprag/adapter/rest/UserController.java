package com.corprag.adapter.rest;

import com.corprag.config.AppSecurityProperties;
import com.corprag.contracts.api.v1.model.CreateUserRequest;
import com.corprag.contracts.api.v1.model.CreateUserResponse;
import com.corprag.contracts.api.v1.model.HateoasLink;
import com.corprag.contracts.api.v1.model.PagedUsers;
import com.corprag.contracts.api.v1.model.TemporaryPasswordResponse;
import com.corprag.contracts.api.v1.model.UpdateUserRequest;
import com.corprag.contracts.api.v1.model.User;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.UserAccount;
import com.corprag.service.auth.RequestMetadata;
import com.corprag.service.user.UserService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @GetMapping
    PagedUsers listUsers(
            @AuthenticationPrincipal Jwt jwt,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        JwtAuthorization.requirePermission(jwt, "users.read");
        return new PagedUsers()
                .items(userService.listUsers(page, size).stream().map(this::toUser).toList())
                .page(page)
                .size(size)
                .total(userService.countUsers());
    }

    @PostMapping
    ResponseEntity<CreateUserResponse> createUser(
            @AuthenticationPrincipal Jwt jwt,
            @RequestBody CreateUserRequest request) {
        JwtAuthorization.requirePermission(jwt, "users.create");
        UserService.CreatedUser created = userService.createUser(request, JwtAuthorization.userId(jwt));
        return ResponseEntity.status(201)
                .body(new CreateUserResponse()
                        .user(toUser(created.user()))
                        .temporaryPassword(created.temporaryPassword()));
    }

    @GetMapping("/{userId}")
    User getUser(@AuthenticationPrincipal Jwt jwt, @PathVariable("userId") UUID userId) {
        if (!JwtAuthorization.userId(jwt).equals(userId)) {
            JwtAuthorization.requirePermission(jwt, "users.read");
        }
        return toUser(userService.getUser(userId));
    }

    @PatchMapping("/{userId}")
    User updateUser(
            @AuthenticationPrincipal Jwt jwt,
            @PathVariable("userId") UUID userId,
            @Valid @RequestBody UpdateUserRequest request) {
        boolean self = JwtAuthorization.userId(jwt).equals(userId);
        if (self && request.getActive() != null) {
            throw new ApiProblemException(ErrorCodes.SELF_MODIFICATION_FORBIDDEN, "Users cannot change their own active flag");
        }
        if (!self) {
            JwtAuthorization.requirePermission(jwt, "users.update");
        }
        return toUser(userService.updateUser(userId, request, JwtAuthorization.userId(jwt)));
    }

    @DeleteMapping("/{userId}")
    ResponseEntity<Void> deleteUser(
            @AuthenticationPrincipal Jwt jwt,
            @PathVariable("userId") UUID userId,
            HttpServletRequest request) {
        JwtAuthorization.requirePermission(jwt, "users.delete");
        userService.deleteUser(userId, JwtAuthorization.userId(jwt), RequestMetadata.from(request));
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/{userId}/reset-password")
    TemporaryPasswordResponse resetPassword(@AuthenticationPrincipal Jwt jwt, @PathVariable("userId") UUID userId) {
        JwtAuthorization.requirePermission(jwt, "users.update");
        return new TemporaryPasswordResponse()
                .userId(userId)
                .temporaryPassword(userService.resetPassword(userId, JwtAuthorization.userId(jwt)));
    }

    private User toUser(UserService.UserView view) {
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
