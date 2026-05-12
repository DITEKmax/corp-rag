package com.corprag.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.corprag.config.AppSecurityProperties;
import com.corprag.config.SecurityConfig;
import com.nimbusds.jose.jwk.source.ImmutableSecret;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.UUID;
import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import org.junit.jupiter.api.Test;
import org.springframework.core.env.Environment;
import org.springframework.mock.env.MockEnvironment;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;

class JwtServiceTest {

    private static final String TEST_SECRET = "test-only-phase-two-hs256-secret-never-use-in-runtime";

    @Test
    void issuesHs256JwtWithIdentityClaims() {
        AppSecurityProperties properties = properties(TEST_SECRET);
        SecretKey key = new SecretKeySpec(TEST_SECRET.getBytes(StandardCharsets.UTF_8), "HmacSHA256");
        JwtEncoder encoder = new NimbusJwtEncoder(new ImmutableSecret<>(key));
        JwtDecoder decoder = NimbusJwtDecoder.withSecretKey(key)
                .macAlgorithm(MacAlgorithm.HS256)
                .build();
        JwtService service = new JwtService(encoder, properties);

        UUID userId = UUID.randomUUID();
        JwtService.IssuedJwt issued = service.issue(
                userId,
                "employee.test",
                List.of("EMPLOYEE"),
                List.of("chat.query", "documents.read"),
                true);

        Jwt decoded = decoder.decode(issued.token());
        assertThat(decoded.getSubject()).isEqualTo(userId.toString());
        assertThat(decoded.getClaimAsString("username")).isEqualTo("employee.test");
        assertThat(decoded.getClaimAsStringList("roles")).containsExactly("EMPLOYEE");
        assertThat(decoded.getClaimAsStringList("permissions")).containsExactly("chat.query", "documents.read");
        assertThat(decoded.getClaimAsBoolean("must_change_password")).isTrue();
        assertThat(decoded.getExpiresAt()).isEqualTo(issued.expiresAt());
    }

    @Test
    void rejectsShortConfiguredSecret() {
        AppSecurityProperties properties = properties("too-short");
        SecurityConfig securityConfig = new SecurityConfig();

        assertThatThrownBy(() -> securityConfig.jwtSecretKey(properties, new MockEnvironment()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("at least 32 bytes");
    }

    @Test
    void rejectsMissingSecretInProd() {
        AppSecurityProperties properties = properties("");
        Environment environment = new MockEnvironment().withProperty("spring.profiles.active", "prod");
        SecurityConfig securityConfig = new SecurityConfig();

        assertThatThrownBy(() -> securityConfig.jwtSecretKey(properties, environment))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("required in prod");
    }

    private static AppSecurityProperties properties(String secret) {
        AppSecurityProperties properties = new AppSecurityProperties();
        properties.getJwt().setSecret(secret);
        properties.getJwt().setIssuer("corp-rag-test");
        return properties;
    }
}
