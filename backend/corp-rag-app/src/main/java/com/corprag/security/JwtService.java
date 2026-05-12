package com.corprag.security;

import com.corprag.config.AppSecurityProperties;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.UUID;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.stereotype.Service;

@Service
public class JwtService {

    private final JwtEncoder jwtEncoder;
    private final AppSecurityProperties properties;

    public JwtService(JwtEncoder jwtEncoder, AppSecurityProperties properties) {
        this.jwtEncoder = jwtEncoder;
        this.properties = properties;
    }

    public IssuedJwt issue(
            UUID userId,
            String username,
            List<String> roles,
            List<String> permissions,
            boolean mustChangePassword) {
        Instant issuedAt = Instant.now().truncatedTo(ChronoUnit.SECONDS);
        Instant expiresAt = issuedAt.plusSeconds(properties.getJwt().getAccessTokenMinutes() * 60L);
        JwtClaimsSet claims = JwtClaimsSet.builder()
                .issuer(properties.getJwt().getIssuer())
                .issuedAt(issuedAt)
                .expiresAt(expiresAt)
                .subject(userId.toString())
                .claim("username", username)
                .claim("roles", roles)
                .claim("permissions", permissions)
                .claim("must_change_password", mustChangePassword)
                .build();
        JwsHeader headers = JwsHeader.with(MacAlgorithm.HS256).build();
        String token = jwtEncoder.encode(JwtEncoderParameters.from(headers, claims)).getTokenValue();
        return new IssuedJwt(token, expiresAt);
    }

    public record IssuedJwt(String token, Instant expiresAt) {
    }
}
