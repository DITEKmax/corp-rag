package com.corprag.security;

import com.fasterxml.jackson.annotation.JsonValue;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

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

    public static List<String> codes() {
        return Arrays.stream(values())
                .map(Permission::value)
                .toList();
    }

    public static Set<String> codeSet() {
        return Arrays.stream(values())
                .map(Permission::value)
                .collect(Collectors.toUnmodifiableSet());
    }

    public static Optional<Permission> findByValue(String value) {
        return Arrays.stream(values())
                .filter(permission -> permission.value.equals(value))
                .findFirst();
    }

    public static Permission fromValue(String value) {
        return findByValue(value)
                .orElseThrow(() -> new IllegalArgumentException("Unknown permission: " + value));
    }
}
