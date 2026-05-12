package com.corprag.adapter.rest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.corprag.contracts.api.v1.model.AccessPolicy;
import com.corprag.contracts.api.v1.model.UpdateAccessPolicyRequest;
import com.corprag.domain.AccessLevel;
import com.corprag.domain.AccessPolicyDefinition;
import com.corprag.domain.DocType;
import com.corprag.service.access.AccessPolicyService;
import com.corprag.testsupport.AuthTestFixtures;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.security.oauth2.jwt.Jwt;

@ExtendWith(MockitoExtension.class)
class AccessPolicyControllerTest {

    private static final UUID ACTOR_ID = UUID.fromString("00000000-0000-4000-8000-00000000e001");
    private static final UUID POLICY_ID = UUID.fromString("00000000-0000-4000-9000-00000000e001");
    private static final UUID ROLE_ID = UUID.fromString("00000000-0000-4000-8000-00000000e002");

    @Mock
    private AccessPolicyService accessPolicyService;

    private AccessPolicyController controller;

    @BeforeEach
    void setUp() {
        controller = new AccessPolicyController(accessPolicyService);
    }

    @Test
    void listRequiresAccessPolicyReadPermission() {
        assertThatThrownBy(() -> controller.listPolicies(jwtWith(AuthTestFixtures.PERMISSION_USERS_READ)))
                .isInstanceOf(ApiProblemException.class)
                .satisfies(exception -> assertThat(((ApiProblemException) exception).errorCode().code())
                        .isEqualTo("INSUFFICIENT_PERMISSIONS"));
        verifyNoInteractions(accessPolicyService);
    }

    @Test
    void getPolicyMapsEtagAndContractFields() {
        AccessPolicyService.AccessPolicyView view = view();
        when(accessPolicyService.getPolicy(POLICY_ID)).thenReturn(view);
        when(accessPolicyService.etag(view)).thenReturn("\"access-policy-v2\"");

        ResponseEntity<AccessPolicy> response = controller.getPolicy(
                jwtWith(AuthTestFixtures.PERMISSION_ACCESS_POLICIES_READ),
                POLICY_ID);

        assertThat(response.getHeaders().getFirst(HttpHeaders.ETAG)).isEqualTo("\"access-policy-v2\"");
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().getRoleName()).isEqualTo("CUSTOM");
        assertThat(response.getBody().getAccessLevels()).containsExactly(com.corprag.contracts.api.v1.model.AccessLevel.PUBLIC);
        assertThat(response.getBody().getDocTypes()).containsExactly(com.corprag.contracts.api.v1.model.DocType.POLICY);
    }

    @Test
    void updatePassesActorAndIfMatchToService() {
        UpdateAccessPolicyRequest request = new UpdateAccessPolicyRequest()
                .accessLevels(List.of(com.corprag.contracts.api.v1.model.AccessLevel.INTERNAL))
                .departments(List.of("IT"))
                .docTypes(List.of(com.corprag.contracts.api.v1.model.DocType.REPORT));
        AccessPolicyService.AccessPolicyView view = view();
        when(accessPolicyService.updatePolicy(POLICY_ID, request, "\"access-policy-v1\"", ACTOR_ID)).thenReturn(view);
        when(accessPolicyService.etag(view)).thenReturn("\"access-policy-v2\"");

        ResponseEntity<AccessPolicy> response = controller.updatePolicy(
                jwtWith(AuthTestFixtures.PERMISSION_ACCESS_POLICIES_UPDATE),
                POLICY_ID,
                "\"access-policy-v1\"",
                request);

        assertThat(response.getStatusCode().value()).isEqualTo(200);
        verify(accessPolicyService).updatePolicy(POLICY_ID, request, "\"access-policy-v1\"", ACTOR_ID);
    }

    private Jwt jwtWith(String... permissions) {
        return Jwt.withTokenValue("test-token")
                .header("alg", "none")
                .subject(ACTOR_ID.toString())
                .claim("permissions", List.of(permissions))
                .claim("roles", List.of(AuthTestFixtures.ROLE_ADMIN))
                .claim("must_change_password", false)
                .build();
    }

    private AccessPolicyService.AccessPolicyView view() {
        Instant now = Instant.now();
        return new AccessPolicyService.AccessPolicyView(
                new AccessPolicyDefinition(
                        POLICY_ID,
                        ROLE_ID,
                        List.of(AccessLevel.PUBLIC),
                        List.of("HR"),
                        List.of(DocType.POLICY),
                        now,
                        now,
                        2),
                "CUSTOM");
    }
}
