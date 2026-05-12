package com.corprag.adapter.rest;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.corprag.config.AppSecurityProperties;
import com.corprag.contracts.api.v1.model.CreateRoleRequest;
import com.corprag.contracts.api.v1.model.PermissionCode;
import com.corprag.service.role.RoleService;
import com.corprag.testsupport.AuthTestFixtures;
import com.corprag.testsupport.PostgresIntegrationTestSupport;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.RequestPostProcessor;
import org.testcontainers.junit.jupiter.Testcontainers;

@AutoConfigureMockMvc
@SpringBootTest(properties = {
        "app.security.jwt.secret=test-only-phase-two-hs256-secret-never-use-in-runtime",
        "app.security.jwt.issuer=corp-rag-test",
        "app.security.cookies.secure=false"
})
@Testcontainers(disabledWithoutDocker = true)
class RoleControllerTest extends PostgresIntegrationTestSupport {

    private static final UUID ADMIN_ROLE_ID = UUID.fromString("00000000-0000-4000-8000-000000000001");

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private RoleService roleService;

    @Autowired
    private AppSecurityProperties properties;

    @Test
    void listRolesRequiresRolesReadPermission() throws Exception {
        mockMvc.perform(get("/api/v1/roles").with(jwtWith(AuthTestFixtures.PERMISSION_USERS_READ)))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.errorCode").value("INSUFFICIENT_PERMISSIONS"));

        mockMvc.perform(get("/api/v1/roles").with(jwtWith(AuthTestFixtures.PERMISSION_ROLES_READ)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items").isArray());
    }

    @Test
    void createsCustomRole() throws Exception {
        String roleName = "CTRL_" + shortId();

        mockMvc.perform(post("/api/v1/roles")
                        .with(jwtWith(AuthTestFixtures.PERMISSION_ROLES_CREATE))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"%s","description":"Controller role","permissions":["chat.query","documents.read"]}
                                """.formatted(roleName)))
                .andExpect(status().isCreated())
                .andExpect(header().string(HttpHeaders.LOCATION, org.hamcrest.Matchers.containsString("/api/v1/roles/")))
                .andExpect(jsonPath("$.name").value(roleName))
                .andExpect(jsonPath("$.permissions[0]").value("chat.query"))
                .andExpect(jsonPath("$.permissions[1]").value("documents.read"));
    }

    @Test
    void getAndUpdateRoleUseEtags() throws Exception {
        RoleService.RoleView created = roleService.createRole(new CreateRoleRequest()
                .name("ETAG_" + shortId())
                .permissions(List.of(PermissionCode.CHAT_QUERY, PermissionCode.DOCUMENTS_READ)));

        mockMvc.perform(get("/api/v1/roles/{roleId}", created.role().id())
                        .with(jwtWith(AuthTestFixtures.PERMISSION_ROLES_READ)))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.ETAG, roleService.etag(created)));

        mockMvc.perform(put("/api/v1/roles/{roleId}", created.role().id())
                        .with(jwtWith(AuthTestFixtures.PERMISSION_ROLES_UPDATE))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"%s","permissions":["roles.read"]}
                                """.formatted(created.role().code())))
                .andExpect(status().isPreconditionRequired())
                .andExpect(jsonPath("$.errorCode").value("PRECONDITION_REQUIRED"));

        mockMvc.perform(put("/api/v1/roles/{roleId}", created.role().id())
                        .with(jwtWith(AuthTestFixtures.PERMISSION_ROLES_UPDATE))
                        .header(HttpHeaders.IF_MATCH, "\"role-v99\"")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"%s","permissions":["roles.read"]}
                                """.formatted(created.role().code())))
                .andExpect(status().isPreconditionFailed())
                .andExpect(jsonPath("$.errorCode").value("PRECONDITION_FAILED"));

        MvcResult update = mockMvc.perform(put("/api/v1/roles/{roleId}", created.role().id())
                        .with(jwtWith(AuthTestFixtures.PERMISSION_ROLES_UPDATE))
                        .header(HttpHeaders.IF_MATCH, roleService.etag(created))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"%s","description":"Updated","permissions":["roles.read"]}
                                """.formatted(created.role().code())))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.version").value(1))
                .andExpect(jsonPath("$.permissions[0]").value("roles.read"))
                .andReturn();

        org.assertj.core.api.Assertions.assertThat(update.getResponse().getHeader(HttpHeaders.ETAG)).isEqualTo("\"role-v1\"");
    }

    @Test
    void invalidPermissionCodesReturnContractError() throws Exception {
        mockMvc.perform(post("/api/v1/roles")
                        .with(jwtWith(AuthTestFixtures.PERMISSION_ROLES_CREATE))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"BAD_%s","permissions":["documents.update"]}
                                """.formatted(shortId())))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errorCode").value("INVALID_PERMISSION_CODE"));
    }

    @Test
    void systemRolesCannotBeDeleted() throws Exception {
        mockMvc.perform(delete("/api/v1/roles/{roleId}", ADMIN_ROLE_ID)
                        .with(jwtWith(AuthTestFixtures.PERMISSION_ROLES_DELETE)))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.errorCode").value("SYSTEM_ROLE_PROTECTED"));
    }

    private RequestPostProcessor jwtWith(String... permissions) {
        return jwt().jwt(token -> token
                .subject(AuthTestFixtures.ADMIN_USER_ID.toString())
                .claim("permissions", List.of(permissions))
                .claim("roles", List.of(AuthTestFixtures.ROLE_ADMIN))
                .claim("must_change_password", false)
                .issuer(properties.getJwt().getIssuer()));
    }

    private String shortId() {
        return UUID.randomUUID()
                .toString()
                .replace("-", "")
                .replaceAll("[0-9]", "A")
                .substring(0, 10)
                .toUpperCase(Locale.ROOT);
    }
}
