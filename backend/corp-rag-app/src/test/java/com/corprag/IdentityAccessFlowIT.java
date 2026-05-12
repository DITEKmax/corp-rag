package com.corprag;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.cookie;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.corprag.config.AppSecurityProperties;
import com.corprag.domain.AccessLevel;
import com.corprag.domain.AccessPolicyDefinition;
import com.corprag.domain.DocType;
import com.corprag.domain.ResolvedAccessFilter;
import com.corprag.domain.UserAccount;
import com.corprag.repository.AccessPolicyRepository;
import com.corprag.repository.UserRepository;
import com.corprag.repository.UserRoleRepository;
import com.corprag.service.access.AccessFilterResolver;
import com.corprag.testsupport.AuthTestFixtures;
import com.corprag.testsupport.PostgresIntegrationTestSupport;
import com.jayway.jsonpath.JsonPath;
import jakarta.servlet.http.Cookie;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.testcontainers.junit.jupiter.Testcontainers;

@AutoConfigureMockMvc
@SpringBootTest(properties = {
        "app.security.jwt.secret=test-only-phase-two-hs256-secret-never-use-in-runtime",
        "app.security.jwt.issuer=corp-rag-test",
        "app.security.cookies.secure=false"
})
@Testcontainers(disabledWithoutDocker = true)
class IdentityAccessFlowIT extends PostgresIntegrationTestSupport {

    private static final UUID ADMIN_ROLE_ID = UUID.fromString("00000000-0000-4000-8000-000000000001");

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private UserRoleRepository userRoleRepository;

    @Autowired
    private AccessPolicyRepository accessPolicyRepository;

    @Autowired
    private AccessFilterResolver accessFilterResolver;

    @Autowired
    private JdbcClient jdbc;

    @Autowired
    private AppSecurityProperties properties;

    @Test
    void phaseTwoAdminFlowManagesUsersRolesPoliciesFiltersAndAudit() throws Exception {
        TestUser admin = createAdmin();
        MvcResult adminLogin = login(admin.username(), "CorrectHorseBattery12!")
                .andExpect(status().isOk())
                .andReturn();
        Cookie adminSession = adminLogin.getResponse().getCookie(properties.getCookies().getSessionName());

        mockMvc.perform(get("/api/v1/access-policies").cookie(adminSession))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items").isArray());

        String username = "flow_" + shortId().toLowerCase(Locale.ROOT);
        MvcResult createdUser = mockMvc.perform(post("/api/v1/users")
                        .header(HttpHeaders.ORIGIN, "http://localhost")
                        .cookie(adminSession)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"%s","fullName":"Flow User","email":"%s@example.com","department":"IT"}
                                """.formatted(username, username)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.user.roles[0]").value(AuthTestFixtures.ROLE_EMPLOYEE))
                .andExpect(jsonPath("$.temporaryPassword").isString())
                .andReturn();

        UUID userId = UUID.fromString(JsonPath.read(createdUser.getResponse().getContentAsString(), "$.user.id"));
        String temporaryPassword = JsonPath.read(createdUser.getResponse().getContentAsString(), "$.temporaryPassword");
        MvcResult firstLogin = login(username, temporaryPassword)
                .andExpect(jsonPath("$.user.mustChangePassword").value(true))
                .andReturn();
        Cookie firstSession = firstLogin.getResponse().getCookie(properties.getCookies().getSessionName());

        MvcResult changedPassword = mockMvc.perform(post("/api/v1/auth/password")
                        .header(HttpHeaders.ORIGIN, "http://localhost")
                        .cookie(firstSession)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"currentPassword":"%s","newPassword":"N3w!SecurePassx"}
                                """.formatted(temporaryPassword)))
                .andExpect(status().isNoContent())
                .andExpect(cookie().exists(properties.getCookies().getSessionName()))
                .andReturn();
        Cookie userSession = changedPassword.getResponse().getCookie(properties.getCookies().getSessionName());

        mockMvc.perform(get("/api/v1/access-policies").cookie(userSession))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.errorCode").value("INSUFFICIENT_PERMISSIONS"));

        String roleName = "FLOW_" + shortId();
        MvcResult createdRole = mockMvc.perform(post("/api/v1/roles")
                        .header(HttpHeaders.ORIGIN, "http://localhost")
                        .cookie(adminSession)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"%s","permissions":["chat.query","documents.read"]}
                                """.formatted(roleName)))
                .andExpect(status().isCreated())
                .andReturn();
        UUID roleId = UUID.fromString(JsonPath.read(createdRole.getResponse().getContentAsString(), "$.id"));

        MvcResult createdPolicy = mockMvc.perform(post("/api/v1/access-policies")
                        .header(HttpHeaders.ORIGIN, "http://localhost")
                        .cookie(adminSession)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"roleId":"%s","accessLevels":["PUBLIC","INTERNAL"],"departments":["IT"],"docTypes":["POLICY","REPORT"]}
                                """.formatted(roleId)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.roleName").value(roleName))
                .andReturn();
        UUID policyId = UUID.fromString(JsonPath.read(createdPolicy.getResponse().getContentAsString(), "$.id"));

        MvcResult policy = mockMvc.perform(get("/api/v1/access-policies/{policyId}", policyId)
                        .cookie(adminSession))
                .andExpect(status().isOk())
                .andReturn();
        String policyEtag = policy.getResponse().getHeader(HttpHeaders.ETAG);

        mockMvc.perform(put("/api/v1/access-policies/{policyId}", policyId)
                        .header(HttpHeaders.ORIGIN, "http://localhost")
                        .cookie(adminSession)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"accessLevels":["CONFIDENTIAL"],"departments":["IT"],"docTypes":["REPORT"]}
                                """))
                .andExpect(status().isPreconditionRequired())
                .andExpect(jsonPath("$.errorCode").value("PRECONDITION_REQUIRED"));

        mockMvc.perform(put("/api/v1/access-policies/{policyId}", policyId)
                        .header(HttpHeaders.ORIGIN, "http://localhost")
                        .header(HttpHeaders.IF_MATCH, policyEtag)
                        .cookie(adminSession)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"accessLevels":["CONFIDENTIAL"],"departments":["IT"],"docTypes":["REPORT"]}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.version").value(1));

        mockMvc.perform(post("/api/v1/users/{userId}/roles", userId)
                        .header(HttpHeaders.ORIGIN, "http://localhost")
                        .cookie(adminSession)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"roles":["%s"]}
                                """.formatted(roleName)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.roles[0]").value(roleName));

        ResolvedAccessFilter resolved = accessFilterResolver.resolve(userId);
        assertThat(resolved.accessLevels())
                .containsExactly(AccessLevel.PUBLIC, AccessLevel.INTERNAL, AccessLevel.CONFIDENTIAL);
        assertThat(resolved.departments()).containsExactly("IT");
        assertThat(resolved.docTypes()).containsExactly(DocType.REPORT);

        AccessPolicyDefinition adminPolicy = accessPolicyRepository.findByRoleId(ADMIN_ROLE_ID).orElseThrow();
        String adminPolicyEtag = mockMvc.perform(get("/api/v1/access-policies/{policyId}", adminPolicy.id())
                        .cookie(adminSession))
                .andReturn()
                .getResponse()
                .getHeader(HttpHeaders.ETAG);
        mockMvc.perform(put("/api/v1/access-policies/{policyId}", adminPolicy.id())
                        .header(HttpHeaders.ORIGIN, "http://localhost")
                        .header(HttpHeaders.IF_MATCH, adminPolicyEtag)
                        .cookie(adminSession)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"accessLevels":["PUBLIC"],"departments":[],"docTypes":["POLICY","REGULATION","GUIDE","REPORT","MANUAL","OTHER"]}
                                """))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.errorCode").value("LAST_ADMIN_VISIBILITY_LOST"));

        List<String> eventTypes = jdbc.sql("SELECT event_type FROM audit_events")
                .query(String.class)
                .list();
        assertThat(eventTypes)
                .contains(
                        "LOGIN_SUCCESS",
                        "USER_CREATED",
                        "PASSWORD_CHANGED",
                        "ROLE_CREATED",
                        "ACCESS_POLICY_CREATED",
                        "ACCESS_POLICY_UPDATED",
                        "USER_ROLES_REPLACED");
    }

    private org.springframework.test.web.servlet.ResultActions login(String username, String password) throws Exception {
        return mockMvc.perform(post("/api/v1/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                        {"username":"%s","password":"%s"}
                        """.formatted(username, password)));
    }

    private TestUser createAdmin() {
        UUID id = UUID.randomUUID();
        String username = "admin_" + shortId().toLowerCase(Locale.ROOT);
        Instant now = Instant.now();
        UserAccount user = new UserAccount(
                id,
                username,
                username + "@example.com",
                "Flow Admin",
                AuthTestFixtures.DEPARTMENT_IT,
                passwordEncoder.encode("CorrectHorseBattery12!"),
                true,
                false,
                now,
                now,
                null,
                0);
        userRepository.create(user);
        userRoleRepository.replaceUserRoles(id, List.of(ADMIN_ROLE_ID), id, now);
        return new TestUser(id, username);
    }

    private String shortId() {
        return UUID.randomUUID()
                .toString()
                .replace("-", "")
                .replaceAll("[0-9]", "A")
                .substring(0, 10)
                .toUpperCase(Locale.ROOT);
    }

    private record TestUser(UUID id, String username) {
    }
}
