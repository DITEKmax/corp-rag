package com.corprag.service.user;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.api.v1.model.CreateUserRequest;
import com.corprag.contracts.api.v1.model.UpdateUserRequest;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.AuditOutcome;
import com.corprag.domain.RoleDefinition;
import com.corprag.domain.UserAccount;
import com.corprag.repository.RoleRepository;
import com.corprag.repository.UserRepository;
import com.corprag.repository.UserRoleRepository;
import com.corprag.security.JwtService;
import com.corprag.security.Permission;
import com.corprag.security.PasswordPolicyValidator;
import com.corprag.service.auth.AuthSession;
import com.corprag.service.auth.AuthenticatedUser;
import com.corprag.service.auth.RefreshTokenService;
import com.corprag.service.auth.RequestMetadata;
import com.corprag.service.audit.AuditEventWriter;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class UserService {

    public static final UUID ADMIN_ROLE_ID = UUID.fromString("00000000-0000-4000-8000-000000000001");
    public static final UUID EMPLOYEE_ROLE_ID = UUID.fromString("00000000-0000-4000-8000-000000000002");

    private final UserRepository userRepository;
    private final UserRoleRepository userRoleRepository;
    private final RoleRepository roleRepository;
    private final PasswordEncoder passwordEncoder;
    private final PasswordPolicyValidator passwordPolicyValidator;
    private final TemporaryPasswordGenerator temporaryPasswordGenerator;
    private final RefreshTokenService refreshTokenService;
    private final JwtService jwtService;
    private final AuditEventWriter auditEventWriter;

    public UserService(
            UserRepository userRepository,
            UserRoleRepository userRoleRepository,
            RoleRepository roleRepository,
            PasswordEncoder passwordEncoder,
            PasswordPolicyValidator passwordPolicyValidator,
            TemporaryPasswordGenerator temporaryPasswordGenerator,
            RefreshTokenService refreshTokenService,
            JwtService jwtService,
            AuditEventWriter auditEventWriter) {
        this.userRepository = userRepository;
        this.userRoleRepository = userRoleRepository;
        this.roleRepository = roleRepository;
        this.passwordEncoder = passwordEncoder;
        this.passwordPolicyValidator = passwordPolicyValidator;
        this.temporaryPasswordGenerator = temporaryPasswordGenerator;
        this.refreshTokenService = refreshTokenService;
        this.jwtService = jwtService;
        this.auditEventWriter = auditEventWriter;
    }

    public List<UserView> listUsers(int page, int size) {
        return userRepository.list(size, page * size).stream()
                .map(this::toView)
                .toList();
    }

    public long countUsers() {
        return userRepository.count();
    }

    public UserView getUser(UUID userId) {
        return toView(findUser(userId));
    }

    @Transactional
    public CreatedUser createUser(CreateUserRequest request, UUID actorUserId) {
        String temporaryPassword = temporaryPasswordGenerator.generate();
        List<UUID> roleIds = resolveRoleIds(request.getRoles());
        Instant now = Instant.now();
        UserAccount user = new UserAccount(
                UUID.randomUUID(),
                request.getUsername(),
                request.getEmail(),
                request.getFullName(),
                request.getDepartment(),
                passwordEncoder.encode(temporaryPassword),
                true,
                true,
                now,
                now,
                null,
                0);
        try {
            userRepository.create(user);
            userRoleRepository.replaceUserRoles(user.id(), roleIds, actorUserId, now);
        } catch (DataIntegrityViolationException exception) {
            throw new ApiProblemException(ErrorCodes.DUPLICATE_RESOURCE, "User already exists");
        }
        auditEventWriter.writeEvent(
                "USER",
                "USER_CREATED",
                AuditOutcome.SUCCESS,
                actorUserId,
                user.id(),
                "USER",
                user.id(),
                null,
                null,
                Map.of("roles", roleIds));
        return new CreatedUser(toView(user), temporaryPassword);
    }

    @Transactional
    public UserView updateUser(UUID userId, UpdateUserRequest request) {
        return updateUser(userId, request, null);
    }

    @Transactional
    public UserView updateUser(UUID userId, UpdateUserRequest request, UUID actorUserId) {
        UserAccount existing = findUser(userId);
        UserAccount updated = new UserAccount(
                existing.id(),
                existing.username(),
                request.getEmail() == null ? existing.email() : request.getEmail(),
                request.getFullName() == null ? existing.fullName() : request.getFullName(),
                request.getDepartment() == null ? existing.department() : request.getDepartment(),
                existing.passwordHash(),
                request.getActive() == null ? existing.active() : request.getActive(),
                existing.mustChangePassword(),
                existing.createdAt(),
                existing.updatedAt(),
                existing.deletedAt(),
                existing.version());
        if (!userRepository.update(updated, existing.version())) {
            throw new ApiProblemException(ErrorCodes.PRECONDITION_FAILED, "User version changed");
        }
        String eventType = existing.active() && Boolean.FALSE.equals(request.getActive())
                ? "USER_DISABLED"
                : "USER_UPDATED";
        auditEventWriter.writeEvent(
                "USER",
                eventType,
                AuditOutcome.SUCCESS,
                actorUserId,
                userId,
                "USER",
                userId,
                null,
                null,
                Map.of());
        return getUser(userId);
    }

    @Transactional
    public String resetPassword(UUID userId) {
        return resetPassword(userId, null);
    }

    @Transactional
    public String resetPassword(UUID userId, UUID actorUserId) {
        UserAccount existing = findUser(userId);
        String temporaryPassword = temporaryPasswordGenerator.generate();
        UserAccount updated = new UserAccount(
                existing.id(),
                existing.username(),
                existing.email(),
                existing.fullName(),
                existing.department(),
                passwordEncoder.encode(temporaryPassword),
                existing.active(),
                true,
                existing.createdAt(),
                existing.updatedAt(),
                existing.deletedAt(),
                existing.version());
        if (!userRepository.update(updated, existing.version())) {
            throw new ApiProblemException(ErrorCodes.PRECONDITION_FAILED, "User version changed");
        }
        refreshTokenService.revokeAllForUser(userId);
        auditEventWriter.writeEvent(
                "USER",
                "PASSWORD_RESET",
                AuditOutcome.SUCCESS,
                actorUserId,
                userId,
                "USER",
                userId,
                null,
                null,
                Map.of("must_change_password", true));
        return temporaryPassword;
    }

    @Transactional
    public AuthSession changePassword(UUID userId, String currentPassword, String newPassword, RequestMetadata metadata) {
        UserAccount existing = findUser(userId);
        if (!passwordEncoder.matches(currentPassword, existing.passwordHash())) {
            throw new ApiProblemException(ErrorCodes.AUTHENTICATION_FAILED, "Current password is invalid");
        }
        assertPasswordAllowed(newPassword, existing);
        UserAccount updated = new UserAccount(
                existing.id(),
                existing.username(),
                existing.email(),
                existing.fullName(),
                existing.department(),
                passwordEncoder.encode(newPassword),
                existing.active(),
                false,
                existing.createdAt(),
                existing.updatedAt(),
                existing.deletedAt(),
                existing.version());
        if (!userRepository.update(updated, existing.version())) {
            throw new ApiProblemException(ErrorCodes.PRECONDITION_FAILED, "User version changed");
        }
        refreshTokenService.revokeAllForUser(userId);
        AuthenticatedUser authenticatedUser = authenticatedUser(userRepository.findById(userId).orElseThrow());
        RefreshTokenService.IssuedRefreshToken refreshToken = refreshTokenService.issueNewFamily(authenticatedUser.account(), metadata);
        JwtService.IssuedJwt accessToken = jwtService.issue(
                authenticatedUser.account().id(),
                authenticatedUser.account().username(),
                authenticatedUser.roles(),
                authenticatedUser.permissions(),
                false);
        auditEventWriter.writeEvent(
                "USER",
                "PASSWORD_CHANGED",
                AuditOutcome.SUCCESS,
                userId,
                userId,
                "USER",
                userId,
                metadata.ipAddress(),
                metadata.userAgent(),
                Map.of());
        return new AuthSession(authenticatedUser, accessToken.token(), accessToken.expiresAt(), refreshToken.rawToken());
    }

    @Transactional
    public void createBootstrapAdmin(String username, String email, String password) {
        Instant now = Instant.now();
        UserAccount user = new UserAccount(
                UUID.randomUUID(),
                username,
                email,
                "System Administrator",
                "IT",
                passwordEncoder.encode(password),
                true,
                true,
                now,
                now,
                null,
                0);
        userRepository.create(user);
        userRoleRepository.replaceUserRoles(user.id(), List.of(ADMIN_ROLE_ID), user.id(), now);
    }

    public boolean hasAdminUser() {
        return !userRoleRepository.findByRoleId(ADMIN_ROLE_ID).isEmpty();
    }

    private void assertPasswordAllowed(String password, UserAccount user) {
        List<PasswordPolicyValidator.Violation> violations = passwordPolicyValidator.validate(
                password,
                new PasswordPolicyValidator.Context(user.username(), user.email(), user.fullName()));
        if (!violations.isEmpty()) {
            throw new ApiProblemException(
                    ErrorCodes.PASSWORD_POLICY_VIOLATION,
                    violations.stream().map(PasswordPolicyValidator.Violation::message).reduce((a, b) -> a + "; " + b).orElse(""));
        }
    }

    private List<UUID> resolveRoleIds(List<String> requestedRoles) {
        List<String> roleCodes = requestedRoles == null || requestedRoles.isEmpty()
                ? List.of("EMPLOYEE")
                : requestedRoles;
        return roleCodes.stream()
                .map(code -> roleRepository.findByCode(code)
                        .orElseThrow(() -> new ApiProblemException(ErrorCodes.ROLE_NOT_FOUND, "Role not found: " + code)))
                .map(RoleDefinition::id)
                .toList();
    }

    private UserAccount findUser(UUID userId) {
        return userRepository.findById(userId)
                .orElseThrow(() -> new ApiProblemException(ErrorCodes.USER_NOT_FOUND, "User not found"));
    }

    private UserView toView(UserAccount user) {
        return new UserView(user, roleRepository.findRolesForUser(user.id()).stream()
                .map(RoleDefinition::code)
                .toList());
    }

    private AuthenticatedUser authenticatedUser(UserAccount user) {
        return new AuthenticatedUser(
                user,
                roleRepository.findRolesForUser(user.id()).stream().map(RoleDefinition::code).toList(),
                roleRepository.findPermissionsForUser(user.id()).stream().map(Permission::value).toList());
    }

    public record UserView(UserAccount user, List<String> roles) {
    }

    public record CreatedUser(UserView user, String temporaryPassword) {
    }
}
