package com.corprag;

import static org.assertj.core.api.Assertions.assertThat;

import com.corprag.testsupport.AuthTestFixtures;
import com.corprag.testsupport.PostgresIntegrationTestSupport;
import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;
import org.springframework.security.test.context.support.WithMockUser;
import org.testcontainers.containers.PostgreSQLContainer;

class SecurityDependencySmokeTest {

    @Test
    void springSecurityJwtClassesAreAvailable() {
        assertThat(Jwt.class).isNotNull();
        assertThat(JwtDecoder.class).isAssignableFrom(NimbusJwtDecoder.class);
        assertThat(JwtEncoder.class).isAssignableFrom(NimbusJwtEncoder.class);
    }

    @Test
    @WithMockUser(authorities = AuthTestFixtures.PERMISSION_USERS_READ)
    void springSecurityTestSupportIsAvailable() {
        assertThat(AuthTestFixtures.PERMISSION_USERS_READ).isEqualTo("users.read");
    }

    @Test
    void authFixturesUseDeterministicTestOnlyValues() {
        assertThat(AuthTestFixtures.ALL_PERMISSIONS)
                .hasSize(16)
                .containsExactly(
                        "users.create",
                        "users.read",
                        "users.update",
                        "users.delete",
                        "roles.create",
                        "roles.read",
                        "roles.update",
                        "roles.delete",
                        "access_policies.create",
                        "access_policies.read",
                        "access_policies.update",
                        "access_policies.delete",
                        "documents.read",
                        "documents.upload",
                        "documents.delete",
                        "chat.query");
        assertThat(AuthTestFixtures.TEST_JWT_SECRET).contains("test-only");
        assertThat(AuthTestFixtures.TEST_JWT_SECRET).doesNotContain("corp_rag_java_password");
        assertThat(AuthTestFixtures.SESSION_COOKIE).isEqualTo("corp_rag_session");
        assertThat(AuthTestFixtures.REFRESH_COOKIE_PATH).isEqualTo("/api/v1/auth");
    }

    @Test
    void postgresIntegrationSupportIsAvailableWithoutStartingDocker() {
        assertThat(PostgresIntegrationTestSupport.POSTGRES_IMAGE.asCanonicalNameString())
                .isEqualTo("postgres:16-alpine");
        assertThat(PostgreSQLContainer.class).isNotNull();
    }
}
