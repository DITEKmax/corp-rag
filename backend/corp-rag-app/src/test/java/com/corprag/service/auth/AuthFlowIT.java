package com.corprag.service.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.cookie;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.corprag.config.AppSecurityProperties;
import com.corprag.domain.UserAccount;
import com.jayway.jsonpath.JsonPath;
import com.corprag.repository.RefreshTokenRepository;
import com.corprag.repository.UserRepository;
import com.corprag.repository.UserRoleRepository;
import com.corprag.testsupport.AuthTestFixtures;
import com.corprag.testsupport.PostgresIntegrationTestSupport;
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
class AuthFlowIT extends PostgresIntegrationTestSupport {

    private static final UUID EMPLOYEE_ROLE_ID = UUID.fromString("00000000-0000-4000-8000-000000000002");
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
    private RefreshTokenRepository refreshTokenRepository;

    @Autowired
    private AppSecurityProperties properties;

    @Test
    void loginMeRefreshReuseAndLogoutWorkThroughSecureCookies() throws Exception {
        TestUser user = createUser(false);

        MvcResult login = mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"%s","password":"CorrectHorseBattery12!"}
                                """.formatted(user.username())))
                .andExpect(status().isOk())
                .andExpect(header().exists(HttpHeaders.SET_COOKIE))
                .andExpect(cookie().httpOnly(properties.getCookies().getSessionName(), true))
                .andExpect(cookie().path(properties.getCookies().getSessionName(), properties.getCookies().getSessionPath()))
                .andExpect(cookie().httpOnly(properties.getCookies().getRefreshName(), true))
                .andExpect(cookie().path(properties.getCookies().getRefreshName(), properties.getCookies().getRefreshPath()))
                .andExpect(jsonPath("$.user.username").value(user.username()))
                .andExpect(jsonPath("$.user.mustChangePassword").value(false))
                .andReturn();

        Cookie sessionCookie = login.getResponse().getCookie(properties.getCookies().getSessionName());
        Cookie refreshCookie = login.getResponse().getCookie(properties.getCookies().getRefreshName());
        assertThat(login.getResponse().getHeaders(HttpHeaders.SET_COOKIE))
                .allSatisfy(value -> assertThat(value).contains("SameSite=Strict").doesNotContain("Secure"));

        mockMvc.perform(get("/api/v1/me").cookie(sessionCookie))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.username").value(user.username()))
                .andExpect(jsonPath("$.roles[0]").value(AuthTestFixtures.ROLE_EMPLOYEE))
                .andExpect(jsonPath("$.permissions").isArray());

        MvcResult refresh = mockMvc.perform(post("/api/v1/auth/refresh")
                        .header(HttpHeaders.ORIGIN, "http://localhost")
                        .cookie(refreshCookie))
                .andExpect(status().isOk())
                .andReturn();
        Cookie rotatedRefresh = refresh.getResponse().getCookie(properties.getCookies().getRefreshName());
        assertThat(rotatedRefresh.getValue()).isNotEqualTo(refreshCookie.getValue());

        mockMvc.perform(post("/api/v1/auth/refresh")
                        .header(HttpHeaders.ORIGIN, "http://localhost")
                        .cookie(refreshCookie))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.errorCode").value("REFRESH_TOKEN_REUSED"));

        mockMvc.perform(post("/api/v1/auth/refresh")
                        .header(HttpHeaders.ORIGIN, "http://localhost")
                        .cookie(rotatedRefresh))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.errorCode").value("REFRESH_TOKEN_INVALID"));

        MvcResult secondLogin = login(user.username());
        Cookie secondSession = secondLogin.getResponse().getCookie(properties.getCookies().getSessionName());

        mockMvc.perform(post("/api/v1/auth/logout")
                        .header(HttpHeaders.ORIGIN, "http://localhost")
                        .cookie(secondSession))
                .andExpect(status().isNoContent())
                .andExpect(cookie().maxAge(properties.getCookies().getSessionName(), 0))
                .andExpect(cookie().maxAge(properties.getCookies().getRefreshName(), 0));
    }

    @Test
    void protectedEndpointsReturnProblemDetailsAndOriginGuardBlocksUnsafeCookieRequests() throws Exception {
        TestUser user = createUser(false);
        MvcResult login = login(user.username());
        Cookie session = login.getResponse().getCookie(properties.getCookies().getSessionName());

        mockMvc.perform(get("/api/v1/me"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.errorCode").value("AUTHENTICATION_FAILED"));

        mockMvc.perform(post("/api/v1/auth/logout")
                        .header(HttpHeaders.ORIGIN, "http://evil.test")
                        .cookie(session))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.errorCode").value("ORIGIN_VALIDATION_FAILED"));
    }

    @Test
    void loginEvictsOldestSessionAboveLimitAndPreservesMustChangePasswordClaim() throws Exception {
        TestUser user = createUser(true);

        for (int index = 0; index < 6; index++) {
            mockMvc.perform(post("/api/v1/auth/login")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("""
                                    {"username":"%s","password":"CorrectHorseBattery12!"}
                                    """.formatted(user.username())))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.user.mustChangePassword").value(true));
        }

        assertThat(refreshTokenRepository.findActiveTerminalTokensForUser(user.id(), Instant.now()))
                .hasSize(5);
    }

    @Test
    void adminCreatesUserWithTemporaryPasswordAndCanResetIt() throws Exception {
        TestUser admin = createUser(false, ADMIN_ROLE_ID);
        Cookie adminSession = login(admin.username()).getResponse().getCookie(properties.getCookies().getSessionName());
        String username = "created_" + UUID.randomUUID().toString().replace("-", "").substring(0, 10).toLowerCase(Locale.ROOT);

        MvcResult created = mockMvc.perform(post("/api/v1/users")
                        .header(HttpHeaders.ORIGIN, "http://localhost")
                        .cookie(adminSession)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"%s","fullName":"Created User","email":"%s@example.com","department":"IT"}
                                """.formatted(username, username)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.temporaryPassword").isString())
                .andExpect(jsonPath("$.user.roles[0]").value(AuthTestFixtures.ROLE_EMPLOYEE))
                .andExpect(jsonPath("$.user.mustChangePassword").value(true))
                .andReturn();

        String temporaryPassword = JsonPath.read(created.getResponse().getContentAsString(), "$.temporaryPassword");
        UUID userId = UUID.fromString(JsonPath.read(created.getResponse().getContentAsString(), "$.user.id"));

        mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"%s","password":"%s"}
                                """.formatted(username, temporaryPassword)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.user.mustChangePassword").value(true));

        MvcResult reset = mockMvc.perform(post("/api/v1/users/{userId}/reset-password", userId)
                        .header(HttpHeaders.ORIGIN, "http://localhost")
                        .cookie(adminSession))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.temporaryPassword").isString())
                .andReturn();
        String resetPassword = JsonPath.read(reset.getResponse().getContentAsString(), "$.temporaryPassword");
        assertThat(resetPassword).isNotEqualTo(temporaryPassword);
    }

    @Test
    void mustChangePasswordUsersAreBlockedUntilPasswordChangeCompletes() throws Exception {
        TestUser user = createUser(true);
        Cookie session = login(user.username()).getResponse().getCookie(properties.getCookies().getSessionName());

        mockMvc.perform(get("/api/v1/users/{userId}", user.id()).cookie(session))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.errorCode").value("PASSWORD_CHANGE_REQUIRED"));

        MvcResult changed = mockMvc.perform(post("/api/v1/auth/password")
                        .header(HttpHeaders.ORIGIN, "http://localhost")
                        .cookie(session)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"currentPassword":"CorrectHorseBattery12!","newPassword":"N3w!SecurePassx"}
                                """))
                .andExpect(status().isNoContent())
                .andExpect(cookie().exists(properties.getCookies().getSessionName()))
                .andReturn();

        Cookie newSession = changed.getResponse().getCookie(properties.getCookies().getSessionName());
        mockMvc.perform(get("/api/v1/users/{userId}", user.id()).cookie(newSession))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.mustChangePassword").value(false));
    }

    private MvcResult login(String username) throws Exception {
        return mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"%s","password":"CorrectHorseBattery12!"}
                                """.formatted(username)))
                .andExpect(status().isOk())
                .andReturn();
    }

    private TestUser createUser(boolean mustChangePassword) {
        return createUser(mustChangePassword, EMPLOYEE_ROLE_ID);
    }

    private TestUser createUser(boolean mustChangePassword, UUID roleId) {
        UUID id = UUID.randomUUID();
        String suffix = UUID.randomUUID()
                .toString()
                .replace("-", "")
                .substring(0, 10)
                .toLowerCase(Locale.ROOT);
        Instant now = Instant.now();
        UserAccount user = new UserAccount(
                id,
                "authit_" + suffix,
                "authit_" + suffix + "@example.com",
                "Auth IT " + suffix,
                AuthTestFixtures.DEPARTMENT_IT,
                passwordEncoder.encode("CorrectHorseBattery12!"),
                true,
                mustChangePassword,
                now,
                now,
                null,
                0);
        userRepository.create(user);
        userRoleRepository.replaceUserRoles(id, List.of(roleId), id, now);
        return new TestUser(id, user.username());
    }

    private record TestUser(UUID id, String username) {
    }
}
