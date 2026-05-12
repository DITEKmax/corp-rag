package com.corprag.domain;

import com.fasterxml.jackson.annotation.JsonValue;
import java.util.Arrays;

public enum Permission {
    USERS_CREATE("users.create"),
    USERS_READ("users.read"),
    USERS_UPDATE("users.update"),
    USERS_DELETE("users.delete"),
    ROLES_CREATE("roles.create"),
    ROLES_READ("roles.read"),
    ROLES_UPDATE("roles.update"),
    ROLES_DELETE("roles.delete"),
    ACCESS_POLICIES_CREATE("access_policies.create"),
    ACCESS_POLICIES_READ("access_policies.read"),
    ACCESS_POLICIES_UPDATE("access_policies.update"),
    ACCESS_POLICIES_DELETE("access_policies.delete"),
    DOCUMENTS_READ("documents.read"),
    DOCUMENTS_UPLOAD("documents.upload"),
    DOCUMENTS_DELETE("documents.delete"),
    CHAT_QUERY("chat.query");

    private final String value;

    Permission(String value) {
        this.value = value;
    }

    @JsonValue
    public String value() {
        return value;
    }

    public static Permission fromValue(String value) {
        return Arrays.stream(values())
                .filter(permission -> permission.value.equals(value))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("Unknown permission: " + value));
    }
}
