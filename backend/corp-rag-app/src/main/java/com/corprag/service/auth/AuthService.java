package com.corprag.service.auth;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.AuditOutcome;
import com.corprag.domain.RoleDefinition;
import com.corprag.domain.UserAccount;
import com.corprag.repository.RoleRepository;
import com.corprag.repository.UserRepository;
import com.corprag.security.JwtService;
import com.corprag.security.Permission;
import com.corprag.service.audit.AuditEventWriter;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final RoleRepository roleRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;
    private final RefreshTokenService refreshTokenService;
    private final AuditEventWriter auditEventWriter;

    public AuthService(
            UserRepository userRepository,
            RoleRepository roleRepository,
            PasswordEncoder passwordEncoder,
            JwtService jwtService,
            RefreshTokenService refreshTokenService,
            AuditEventWriter auditEventWriter) {
        this.userRepository = userRepository;
        this.roleRepository = roleRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
        this.refreshTokenService = refreshTokenService;
        this.auditEventWriter = auditEventWriter;
    }

    @Transactional
    public AuthSession login(String username, String password, RequestMetadata metadata) {
        UserAccount user = userRepository.findByUsername(username)
                .or(() -> userRepository.findByEmail(username))
                .orElse(null);
        if (user == null || !user.active() || !passwordEncoder.matches(password, user.passwordHash())) {
            auditEventWriter.writeAuthEvent(
                    "LOGIN_FAILED",
                    AuditOutcome.FAILURE,
                    user == null ? null : user.id(),
                    user == null ? null : user.id(),
                    metadata.ipAddress(),
                    metadata.userAgent(),
                    Map.of("username", username));
            throw new ApiProblemException(ErrorCodes.AUTHENTICATION_FAILED, "Invalid username or password");
        }

        AuthenticatedUser authenticatedUser = loadAuthenticatedUser(user);
        RefreshTokenService.IssuedRefreshToken refreshToken = refreshTokenService.issueNewFamily(user, metadata);
        JwtService.IssuedJwt accessToken = issueAccessToken(authenticatedUser);
        auditEventWriter.writeAuthEvent(
                "LOGIN_SUCCESS",
                AuditOutcome.SUCCESS,
                user.id(),
                user.id(),
                metadata.ipAddress(),
                metadata.userAgent(),
                Map.of("must_change_password", user.mustChangePassword()));
        return new AuthSession(authenticatedUser, accessToken.token(), accessToken.expiresAt(), refreshToken.rawToken());
    }

    @Transactional(noRollbackFor = ApiProblemException.class)
    public AuthSession refresh(String rawRefreshToken, RequestMetadata metadata) {
        try {
            RefreshTokenService.Rotation rotation = refreshTokenService.rotate(rawRefreshToken, metadata);
            AuthenticatedUser authenticatedUser = loadAuthenticatedUser(rotation.userId());
            JwtService.IssuedJwt accessToken = issueAccessToken(authenticatedUser);
            auditEventWriter.writeAuthEvent(
                    "REFRESH_SUCCESS",
                    AuditOutcome.SUCCESS,
                    authenticatedUser.account().id(),
                    authenticatedUser.account().id(),
                    metadata.ipAddress(),
                    metadata.userAgent(),
                    Map.of());
            return new AuthSession(
                    authenticatedUser,
                    accessToken.token(),
                    accessToken.expiresAt(),
                    rotation.refreshToken().rawToken());
        } catch (ApiProblemException exception) {
            if (ErrorCodes.REFRESH_TOKEN_REUSED.code().equals(exception.errorCode().code())) {
                auditEventWriter.writeAuthEvent(
                        "REFRESH_TOKEN_REUSED",
                        AuditOutcome.FAILURE,
                        null,
                        null,
                        metadata.ipAddress(),
                        metadata.userAgent(),
                        Map.of());
            }
            throw exception;
        }
    }

    public AuthenticatedUser currentUser(UUID userId) {
        return loadAuthenticatedUser(userId);
    }

    public void logout(UUID userId, RequestMetadata metadata) {
        int revoked = refreshTokenService.revokeAllForUser(userId);
        auditEventWriter.writeAuthEvent(
                "LOGOUT",
                AuditOutcome.SUCCESS,
                userId,
                userId,
                metadata.ipAddress(),
                metadata.userAgent(),
                Map.of("revoked_tokens", revoked));
    }

    private JwtService.IssuedJwt issueAccessToken(AuthenticatedUser authenticatedUser) {
        return jwtService.issue(
                authenticatedUser.account().id(),
                authenticatedUser.account().username(),
                authenticatedUser.roles(),
                authenticatedUser.permissions(),
                authenticatedUser.account().mustChangePassword());
    }

    private AuthenticatedUser loadAuthenticatedUser(UUID userId) {
        UserAccount user = userRepository.findById(userId)
                .orElseThrow(() -> new ApiProblemException(ErrorCodes.AUTHENTICATION_FAILED, "Authenticated user not found"));
        return loadAuthenticatedUser(user);
    }

    private AuthenticatedUser loadAuthenticatedUser(UserAccount user) {
        List<String> roles = roleRepository.findRolesForUser(user.id()).stream()
                .map(RoleDefinition::code)
                .toList();
        List<String> permissions = roleRepository.findPermissionsForUser(user.id()).stream()
                .map(Permission::value)
                .toList();
        return new AuthenticatedUser(user, roles, permissions);
    }
}
