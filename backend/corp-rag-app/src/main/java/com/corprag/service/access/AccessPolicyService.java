package com.corprag.service.access;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.api.v1.model.CreateAccessPolicyRequest;
import com.corprag.contracts.api.v1.model.UpdateAccessPolicyRequest;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.AccessLevel;
import com.corprag.domain.AccessPolicyDefinition;
import com.corprag.domain.AuditOutcome;
import com.corprag.domain.DocType;
import com.corprag.domain.RoleDefinition;
import com.corprag.repository.AccessPolicyRepository;
import com.corprag.repository.RoleRepository;
import com.corprag.service.audit.AuditEventWriter;
import java.time.Instant;
import java.util.Comparator;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AccessPolicyService {

    private static final Pattern ACCESS_POLICY_ETAG = Pattern.compile("\"?access-policy-v(\\d+)\"?");
    private static final Pattern DEPARTMENT_CODE = Pattern.compile("^[A-Z][A-Z0-9_]{0,63}$");

    private final AccessPolicyRepository accessPolicyRepository;
    private final RoleRepository roleRepository;
    private final AccessFilterCacheInvalidator cacheInvalidator;
    private final AuditEventWriter auditEventWriter;

    public AccessPolicyService(
            AccessPolicyRepository accessPolicyRepository,
            RoleRepository roleRepository,
            AccessFilterCacheInvalidator cacheInvalidator,
            AuditEventWriter auditEventWriter) {
        this.accessPolicyRepository = accessPolicyRepository;
        this.roleRepository = roleRepository;
        this.cacheInvalidator = cacheInvalidator;
        this.auditEventWriter = auditEventWriter;
    }

    public List<AccessPolicyView> listPolicies() {
        return accessPolicyRepository.list().stream()
                .map(this::toView)
                .toList();
    }

    @Transactional
    public AccessPolicyView createPolicy(CreateAccessPolicyRequest request, UUID actorUserId) {
        RoleDefinition role = findRole(request.getRoleId());
        if (accessPolicyRepository.findByRoleId(role.id()).isPresent()) {
            throw new ApiProblemException(ErrorCodes.ROLE_POLICY_ALREADY_EXISTS, "Access policy already exists for role");
        }

        Instant now = Instant.now();
        AccessPolicyDefinition policy = new AccessPolicyDefinition(
                UUID.randomUUID(),
                role.id(),
                accessLevels(request.getAccessLevels()),
                departments(request.getDepartments()),
                docTypes(request.getDocTypes()),
                now,
                now,
                0);
        try {
            accessPolicyRepository.create(policy);
        } catch (DataIntegrityViolationException exception) {
            throw new ApiProblemException(ErrorCodes.ROLE_POLICY_ALREADY_EXISTS, "Access policy already exists for role");
        }

        cacheInvalidator.invalidateForRole(role.id());
        auditEventWriter.writeEvent(
                "ACCESS_POLICY",
                "ACCESS_POLICY_CREATED",
                AuditOutcome.SUCCESS,
                actorUserId,
                null,
                "ACCESS_POLICY",
                policy.id(),
                null,
                null,
                Map.of("role_id", role.id(), "role", role.code()));
        return getPolicy(policy.id());
    }

    public AccessPolicyView getPolicy(UUID policyId) {
        return toView(findPolicy(policyId));
    }

    @Transactional
    public AccessPolicyView updatePolicy(UUID policyId, UpdateAccessPolicyRequest request, String ifMatch, UUID actorUserId) {
        long expectedVersion = parseIfMatch(ifMatch);
        AccessPolicyDefinition existing = findPolicy(policyId);
        AccessPolicyDefinition updated = new AccessPolicyDefinition(
                existing.id(),
                existing.roleId(),
                accessLevels(request.getAccessLevels()),
                departments(request.getDepartments()),
                docTypes(request.getDocTypes()),
                existing.createdAt(),
                existing.updatedAt(),
                existing.version());

        assertLastAdminVisibilityPreserved(existing, updated);
        if (!accessPolicyRepository.update(updated, expectedVersion)) {
            throw new ApiProblemException(ErrorCodes.PRECONDITION_FAILED, "Access policy ETag is stale");
        }

        cacheInvalidator.invalidateForRole(existing.roleId());
        auditEventWriter.writeEvent(
                "ACCESS_POLICY",
                "ACCESS_POLICY_UPDATED",
                AuditOutcome.SUCCESS,
                actorUserId,
                null,
                "ACCESS_POLICY",
                existing.id(),
                null,
                null,
                Map.of("role_id", existing.roleId()));
        return getPolicy(policyId);
    }

    @Transactional
    public void deletePolicy(UUID policyId, UUID actorUserId) {
        AccessPolicyDefinition existing = findPolicy(policyId);
        assertLastAdminVisibilityPreserved(existing, null);
        if (!accessPolicyRepository.deleteById(policyId)) {
            throw new ApiProblemException(ErrorCodes.ACCESS_POLICY_NOT_FOUND, "Access policy not found");
        }
        cacheInvalidator.invalidateForRole(existing.roleId());
        auditEventWriter.writeEvent(
                "ACCESS_POLICY",
                "ACCESS_POLICY_DELETED",
                AuditOutcome.SUCCESS,
                actorUserId,
                null,
                "ACCESS_POLICY",
                existing.id(),
                null,
                null,
                Map.of("role_id", existing.roleId()));
    }

    public String etag(AccessPolicyView policy) {
        return "\"access-policy-v" + policy.policy().version() + "\"";
    }

    private AccessPolicyDefinition findPolicy(UUID policyId) {
        return accessPolicyRepository.findById(policyId)
                .orElseThrow(() -> new ApiProblemException(ErrorCodes.ACCESS_POLICY_NOT_FOUND, "Access policy not found"));
    }

    private RoleDefinition findRole(UUID roleId) {
        return roleRepository.findById(roleId)
                .orElseThrow(() -> new ApiProblemException(ErrorCodes.ROLE_NOT_FOUND, "Role not found"));
    }

    private AccessPolicyView toView(AccessPolicyDefinition policy) {
        String roleName = roleRepository.findById(policy.roleId())
                .map(RoleDefinition::code)
                .orElse(null);
        return new AccessPolicyView(policy, roleName);
    }

    private List<AccessLevel> accessLevels(List<com.corprag.contracts.api.v1.model.AccessLevel> requestedLevels) {
        if (requestedLevels == null || requestedLevels.isEmpty()) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "At least one access level is required");
        }
        return requestedLevels.stream()
                .map(level -> AccessLevel.valueOf(level.getValue()))
                .distinct()
                .sorted(Comparator.comparingInt(AccessLevel::rank))
                .toList();
    }

    private List<String> departments(List<String> requestedDepartments) {
        if (requestedDepartments == null || requestedDepartments.isEmpty()) {
            return List.of();
        }
        List<String> departments = requestedDepartments.stream()
                .distinct()
                .toList();
        for (String department : departments) {
            if (department == null || !DEPARTMENT_CODE.matcher(department).matches()) {
                throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "Department code is invalid");
            }
        }
        return departments;
    }

    private List<DocType> docTypes(List<com.corprag.contracts.api.v1.model.DocType> requestedDocTypes) {
        if (requestedDocTypes == null || requestedDocTypes.isEmpty()) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "At least one document type is required");
        }
        return requestedDocTypes.stream()
                .map(docType -> DocType.valueOf(docType.getValue()))
                .distinct()
                .sorted()
                .toList();
    }

    private long parseIfMatch(String ifMatch) {
        if (ifMatch == null || ifMatch.isBlank()) {
            throw new ApiProblemException(ErrorCodes.PRECONDITION_REQUIRED, "If-Match header is required");
        }
        Matcher matcher = ACCESS_POLICY_ETAG.matcher(ifMatch.trim());
        if (!matcher.matches()) {
            throw new ApiProblemException(ErrorCodes.PRECONDITION_FAILED, "Access policy ETag is invalid");
        }
        return Long.parseLong(matcher.group(1));
    }

    private void assertLastAdminVisibilityPreserved(
            AccessPolicyDefinition existing,
            AccessPolicyDefinition replacement) {
        if (!hasFullVisibility(existing) || (replacement != null && hasFullVisibility(replacement))) {
            return;
        }
        if (accessPolicyRepository.countActiveUsersWithRole(existing.roleId()) == 0) {
            return;
        }
        if (accessPolicyRepository.countActiveUsersWithFullVisibilityExcludingRole(existing.roleId()) == 0) {
            throw new ApiProblemException(
                    ErrorCodes.LAST_ADMIN_VISIBILITY_LOST,
                    "Mutation would remove the last full-visibility administrator");
        }
    }

    private boolean hasFullVisibility(AccessPolicyDefinition policy) {
        return policy.accessLevels().contains(AccessLevel.RESTRICTED)
                && policy.departments().isEmpty()
                && EnumSet.copyOf(policy.docTypes()).containsAll(EnumSet.allOf(DocType.class));
    }

    public record AccessPolicyView(AccessPolicyDefinition policy, String roleName) {
    }
}
