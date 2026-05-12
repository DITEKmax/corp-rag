package com.corprag.service.access;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.api.v1.model.CreateAccessPolicyRequest;
import com.corprag.contracts.api.v1.model.UpdateAccessPolicyRequest;
import com.corprag.domain.AccessLevel;
import com.corprag.domain.AccessPolicyDefinition;
import com.corprag.domain.AuditOutcome;
import com.corprag.domain.DocType;
import com.corprag.domain.RoleDefinition;
import com.corprag.repository.AccessPolicyRepository;
import com.corprag.repository.RoleRepository;
import com.corprag.service.audit.AuditEventWriter;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class AccessPolicyServiceTest {

    private static final UUID POLICY_ID = UUID.fromString("00000000-0000-4000-9000-00000000a001");
    private static final UUID ROLE_ID = UUID.fromString("00000000-0000-4000-8000-00000000a001");
    private static final UUID ACTOR_ID = UUID.fromString("00000000-0000-4000-8000-00000000b001");

    @Mock
    private AccessPolicyRepository accessPolicyRepository;

    @Mock
    private RoleRepository roleRepository;

    @Mock
    private AccessFilterCacheInvalidator cacheInvalidator;

    @Mock
    private AuditEventWriter auditEventWriter;

    private AccessPolicyService service;

    @BeforeEach
    void setUp() {
        service = new AccessPolicyService(accessPolicyRepository, roleRepository, cacheInvalidator, auditEventWriter);
    }

    @Test
    void updatesPolicyByFullReplacementWithEtag() {
        AccessPolicyDefinition existing = policy(
                List.of(AccessLevel.PUBLIC),
                List.of("HR"),
                List.of(DocType.POLICY),
                0);
        AccessPolicyDefinition updated = policy(
                List.of(AccessLevel.INTERNAL),
                List.of("IT"),
                List.of(DocType.REPORT),
                1);
        when(accessPolicyRepository.findById(POLICY_ID)).thenReturn(Optional.of(existing), Optional.of(updated));
        when(accessPolicyRepository.update(any(AccessPolicyDefinition.class), eq(0L))).thenReturn(true);
        when(roleRepository.findById(ROLE_ID)).thenReturn(Optional.of(role()));

        AccessPolicyService.AccessPolicyView result = service.updatePolicy(
                POLICY_ID,
                new UpdateAccessPolicyRequest()
                        .accessLevels(List.of(com.corprag.contracts.api.v1.model.AccessLevel.INTERNAL))
                        .departments(List.of("IT"))
                        .docTypes(List.of(com.corprag.contracts.api.v1.model.DocType.REPORT)),
                "\"access-policy-v0\"",
                ACTOR_ID);

        ArgumentCaptor<AccessPolicyDefinition> captor = ArgumentCaptor.forClass(AccessPolicyDefinition.class);
        verify(accessPolicyRepository).update(captor.capture(), eq(0L));
        assertThat(captor.getValue().accessLevels()).containsExactly(AccessLevel.INTERNAL);
        assertThat(captor.getValue().departments()).containsExactly("IT");
        assertThat(captor.getValue().docTypes()).containsExactly(DocType.REPORT);
        verify(cacheInvalidator).invalidateForRole(ROLE_ID);
        verify(auditEventWriter).writeEvent(
                eq("ACCESS_POLICY"),
                eq("ACCESS_POLICY_UPDATED"),
                eq(AuditOutcome.SUCCESS),
                eq(ACTOR_ID),
                isNull(),
                eq("ACCESS_POLICY"),
                eq(POLICY_ID),
                isNull(),
                isNull(),
                any());
        assertThat(result.policy().version()).isEqualTo(1);
        assertThat(result.roleName()).isEqualTo("CUSTOM");
    }

    @Test
    void missingIfMatchIsRejectedBeforeMutation() {
        assertProblem(
                () -> service.updatePolicy(POLICY_ID, new UpdateAccessPolicyRequest(), null, ACTOR_ID),
                "PRECONDITION_REQUIRED");
    }

    @Test
    void duplicateRolePolicyCreationUsesContractError() {
        when(roleRepository.findById(ROLE_ID)).thenReturn(Optional.of(role()));
        when(accessPolicyRepository.findByRoleId(ROLE_ID)).thenReturn(Optional.of(policy(
                List.of(AccessLevel.PUBLIC),
                List.of(),
                List.of(DocType.POLICY),
                0)));

        assertProblem(
                () -> service.createPolicy(
                        new CreateAccessPolicyRequest()
                                .roleId(ROLE_ID)
                                .accessLevels(List.of(com.corprag.contracts.api.v1.model.AccessLevel.PUBLIC))
                                .docTypes(List.of(com.corprag.contracts.api.v1.model.DocType.POLICY)),
                        ACTOR_ID),
                "ROLE_POLICY_ALREADY_EXISTS");
    }

    @Test
    void lastAdminVisibilityCannotBeRemoved() {
        when(accessPolicyRepository.findById(POLICY_ID)).thenReturn(Optional.of(policy(
                List.of(AccessLevel.PUBLIC, AccessLevel.INTERNAL, AccessLevel.CONFIDENTIAL, AccessLevel.RESTRICTED),
                List.of(),
                List.of(DocType.POLICY, DocType.REGULATION, DocType.GUIDE, DocType.REPORT, DocType.MANUAL, DocType.OTHER),
                0)));
        when(accessPolicyRepository.countActiveUsersWithRole(ROLE_ID)).thenReturn(1L);
        when(accessPolicyRepository.countActiveUsersWithFullVisibilityExcludingRole(ROLE_ID)).thenReturn(0L);

        assertProblem(
                () -> service.updatePolicy(
                        POLICY_ID,
                        new UpdateAccessPolicyRequest()
                                .accessLevels(List.of(com.corprag.contracts.api.v1.model.AccessLevel.PUBLIC))
                                .departments(List.of())
                                .docTypes(List.of(
                                        com.corprag.contracts.api.v1.model.DocType.POLICY,
                                        com.corprag.contracts.api.v1.model.DocType.REGULATION,
                                        com.corprag.contracts.api.v1.model.DocType.GUIDE,
                                        com.corprag.contracts.api.v1.model.DocType.REPORT,
                                        com.corprag.contracts.api.v1.model.DocType.MANUAL,
                                        com.corprag.contracts.api.v1.model.DocType.OTHER)),
                        "\"access-policy-v0\"",
                        ACTOR_ID),
                "LAST_ADMIN_VISIBILITY_LOST");
    }

    private void assertProblem(Runnable action, String errorCode) {
        assertThatThrownBy(action::run)
                .isInstanceOf(ApiProblemException.class)
                .satisfies(exception -> assertThat(((ApiProblemException) exception).errorCode().code())
                        .isEqualTo(errorCode));
    }

    private AccessPolicyDefinition policy(
            List<AccessLevel> accessLevels,
            List<String> departments,
            List<DocType> docTypes,
            long version) {
        Instant now = Instant.now();
        return new AccessPolicyDefinition(POLICY_ID, ROLE_ID, accessLevels, departments, docTypes, now, now, version);
    }

    private RoleDefinition role() {
        Instant now = Instant.now();
        return new RoleDefinition(ROLE_ID, "CUSTOM", "Custom role", false, now, now, null, 0);
    }
}
