package com.corprag.adapter.rest;

import com.corprag.config.AppSecurityProperties;
import com.corprag.contracts.api.v1.model.CurrentUser;
import com.corprag.contracts.api.v1.model.HateoasLink;
import com.corprag.contracts.api.v1.model.LoginRequest;
import com.corprag.contracts.api.v1.model.LoginResponse;
import com.corprag.contracts.api.v1.model.User;
import com.corprag.service.auth.AuthService;
import com.corprag.service.auth.AuthSession;
import com.corprag.service.auth.AuthenticatedUser;
import com.corprag.service.auth.RequestMetadata;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1")
public class AuthController {

    private final AuthService authService;
    private final AppSecurityProperties properties;

    public AuthController(AuthService authService, AppSecurityProperties properties) {
        this.authService = authService;
        this.properties = properties;
    }

    @PostMapping("/auth/login")
    ResponseEntity<LoginResponse> login(@Valid @RequestBody LoginRequest request, HttpServletRequest servletRequest) {
        AuthSession session = authService.login(
                request.getUsername(),
                request.getPassword(),
                metadata(servletRequest));
        return sessionResponse(session, "/api/v1/auth/login");
    }

    @PostMapping("/auth/refresh")
    ResponseEntity<LoginResponse> refresh(HttpServletRequest servletRequest) {
        AuthSession session = authService.refresh(
                cookie(servletRequest, properties.getCookies().getRefreshName()),
                metadata(servletRequest));
        return sessionResponse(session, "/api/v1/auth/refresh");
    }

    @GetMapping("/me")
    CurrentUser me(@AuthenticationPrincipal Jwt jwt) {
        AuthenticatedUser user = authService.currentUser(UUID.fromString(jwt.getSubject()));
        return toCurrentUser(user);
    }

    @PostMapping("/auth/logout")
    ResponseEntity<Void> logout(@AuthenticationPrincipal Jwt jwt, HttpServletRequest servletRequest) {
        authService.logout(UUID.fromString(jwt.getSubject()), metadata(servletRequest));
        HttpHeaders headers = new HttpHeaders();
        headers.add(HttpHeaders.SET_COOKIE, clearCookie(
                properties.getCookies().getSessionName(),
                properties.getCookies().getSessionPath()));
        headers.add(HttpHeaders.SET_COOKIE, clearCookie(
                properties.getCookies().getRefreshName(),
                properties.getCookies().getRefreshPath()));
        return ResponseEntity.noContent().headers(headers).build();
    }

    private ResponseEntity<LoginResponse> sessionResponse(AuthSession session, String selfHref) {
        HttpHeaders headers = new HttpHeaders();
        headers.add(HttpHeaders.SET_COOKIE, cookie(
                properties.getCookies().getSessionName(),
                session.accessToken(),
                properties.getCookies().getSessionPath(),
                Duration.ofMinutes(properties.getJwt().getAccessTokenMinutes())));
        headers.add(HttpHeaders.SET_COOKIE, cookie(
                properties.getCookies().getRefreshName(),
                session.refreshToken(),
                properties.getCookies().getRefreshPath(),
                Duration.ofDays(properties.getSessions().getRefreshTokenDays())));

        LoginResponse response = new LoginResponse()
                .user(toUser(session.user()))
                .expiresAt(OffsetDateTime.ofInstant(session.accessTokenExpiresAt(), ZoneOffset.UTC))
                .links(authLinks(selfHref));
        return ResponseEntity.ok().headers(headers).body(response);
    }

    private User toUser(AuthenticatedUser authenticatedUser) {
        return new User()
                .id(authenticatedUser.account().id())
                .username(authenticatedUser.account().username())
                .fullName(authenticatedUser.account().fullName())
                .email(authenticatedUser.account().email())
                .department(authenticatedUser.account().department())
                .roles(authenticatedUser.roles())
                .active(authenticatedUser.account().active())
                .mustChangePassword(authenticatedUser.account().mustChangePassword())
                .createdAt(OffsetDateTime.ofInstant(authenticatedUser.account().createdAt(), ZoneOffset.UTC))
                .links(userLinks(authenticatedUser.account().id()));
    }

    private CurrentUser toCurrentUser(AuthenticatedUser authenticatedUser) {
        return new CurrentUser()
                .id(authenticatedUser.account().id())
                .username(authenticatedUser.account().username())
                .fullName(authenticatedUser.account().fullName())
                .email(authenticatedUser.account().email())
                .department(authenticatedUser.account().department())
                .roles(authenticatedUser.roles())
                .active(authenticatedUser.account().active())
                .mustChangePassword(authenticatedUser.account().mustChangePassword())
                .createdAt(OffsetDateTime.ofInstant(authenticatedUser.account().createdAt(), ZoneOffset.UTC))
                .permissions(authenticatedUser.permissions())
                .links(Map.of(
                        "self", link("/api/v1/me"),
                        "logout", link("/api/v1/auth/logout"),
                        "conversations", link("/api/v1/chat/conversations")));
    }

    private Map<String, HateoasLink> authLinks(String selfHref) {
        return Map.of(
                "self", link(selfHref),
                "me", link("/api/v1/me"),
                "refresh", link("/api/v1/auth/refresh"),
                "logout", link("/api/v1/auth/logout"));
    }

    private Map<String, HateoasLink> userLinks(UUID userId) {
        return Map.of("self", link("/api/v1/users/" + userId));
    }

    private static HateoasLink link(String href) {
        return new HateoasLink().href(href);
    }

    private String cookie(String name, String value, String path, Duration maxAge) {
        return ResponseCookie.from(name, value)
                .httpOnly(true)
                .secure(properties.getCookies().isSecure())
                .sameSite("Strict")
                .path(path)
                .maxAge(maxAge)
                .build()
                .toString();
    }

    private String clearCookie(String name, String path) {
        return cookie(name, "", path, Duration.ZERO);
    }

    private static String cookie(HttpServletRequest request, String name) {
        Cookie[] cookies = request.getCookies();
        if (cookies == null) {
            return null;
        }
        for (Cookie cookie : cookies) {
            if (name.equals(cookie.getName())) {
                return cookie.getValue();
            }
        }
        return null;
    }

    private static RequestMetadata metadata(HttpServletRequest request) {
        return new RequestMetadata(request.getRemoteAddr(), request.getHeader(HttpHeaders.USER_AGENT));
    }
}
