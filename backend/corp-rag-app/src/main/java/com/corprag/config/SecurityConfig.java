package com.corprag.config;

import com.corprag.adapter.rest.ProblemDetailsWriter;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.security.CookieBearerTokenResolver;
import com.corprag.security.OriginRefererValidationFilter;
import com.nimbusds.jose.jwk.source.ImmutableSecret;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Arrays;
import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;
import org.springframework.security.oauth2.server.resource.web.BearerTokenAuthenticationFilter;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@EnableConfigurationProperties(AppSecurityProperties.class)
public class SecurityConfig {

    private static final Logger LOGGER = LoggerFactory.getLogger(SecurityConfig.class);

    @Bean
    SecurityFilterChain securityFilterChain(
            HttpSecurity http,
            AppSecurityProperties properties,
            ProblemDetailsWriter problemDetailsWriter) throws Exception {
        CookieBearerTokenResolver tokenResolver = new CookieBearerTokenResolver(properties);
        OriginRefererValidationFilter originFilter = new OriginRefererValidationFilter(properties, problemDetailsWriter);

        return http
                .csrf(AbstractHttpConfigurer::disable)
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .oauth2ResourceServer(oauth2 -> oauth2
                        .bearerTokenResolver(tokenResolver)
                        .jwt(Customizer.withDefaults()))
                .exceptionHandling(exceptions -> exceptions
                        .authenticationEntryPoint((request, response, exception) -> problemDetailsWriter.write(
                                response,
                                request,
                                ErrorCodes.AUTHENTICATION_FAILED,
                                "Authentication is required"))
                        .accessDeniedHandler((request, response, exception) -> problemDetailsWriter.write(
                                response,
                                request,
                                ErrorCodes.INSUFFICIENT_PERMISSIONS,
                                "Insufficient permissions")))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/", "/api/v1/", "/actuator/health", "/actuator/health/**").permitAll()
                        .requestMatchers("/api/v1/auth/login", "/api/v1/auth/refresh").permitAll()
                        .anyRequest().authenticated())
                .addFilterBefore(originFilter, BearerTokenAuthenticationFilter.class)
                .build();
    }

    @Bean
    PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder(12);
    }

    @Bean
    SecretKey jwtSecretKey(AppSecurityProperties properties, Environment environment) {
        String configuredSecret = properties.getJwt().getSecret();
        byte[] secretBytes;
        if (configuredSecret == null || configuredSecret.isBlank()) {
            if (Arrays.asList(environment.getActiveProfiles()).contains("prod")) {
                throw new IllegalStateException("JWT_SECRET is required in prod profile");
            }
            secretBytes = new byte[32];
            new SecureRandom().nextBytes(secretBytes);
            LOGGER.warn("JWT_SECRET is not configured; generated a random development-only HS256 secret");
        } else {
            secretBytes = configuredSecret.getBytes(StandardCharsets.UTF_8);
        }

        if (secretBytes.length < 32) {
            throw new IllegalStateException("JWT_SECRET must be at least 32 bytes for HS256");
        }
        return new SecretKeySpec(secretBytes, "HmacSHA256");
    }

    @Bean
    JwtEncoder jwtEncoder(SecretKey jwtSecretKey) {
        return new NimbusJwtEncoder(new ImmutableSecret<>(jwtSecretKey));
    }

    @Bean
    JwtDecoder jwtDecoder(SecretKey jwtSecretKey) {
        return NimbusJwtDecoder.withSecretKey(jwtSecretKey)
                .macAlgorithm(MacAlgorithm.HS256)
                .build();
    }
}
