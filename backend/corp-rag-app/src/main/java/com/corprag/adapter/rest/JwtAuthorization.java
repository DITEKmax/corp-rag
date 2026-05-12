package com.corprag.adapter.rest;

import com.corprag.contracts.constants.ErrorCodes;
import java.util.List;
import java.util.UUID;
import org.springframework.security.oauth2.jwt.Jwt;

final class JwtAuthorization {

    private JwtAuthorization() {
    }

    static UUID userId(Jwt jwt) {
        return UUID.fromString(jwt.getSubject());
    }

    static void requirePermission(Jwt jwt, String permission) {
        List<String> permissions = jwt.getClaimAsStringList("permissions");
        if (permissions == null || !permissions.contains(permission)) {
            throw new ApiProblemException(ErrorCodes.INSUFFICIENT_PERMISSIONS, "Missing permission: " + permission);
        }
    }

    static boolean hasPermission(Jwt jwt, String permission) {
        List<String> permissions = jwt.getClaimAsStringList("permissions");
        return permissions != null && permissions.contains(permission);
    }
}
