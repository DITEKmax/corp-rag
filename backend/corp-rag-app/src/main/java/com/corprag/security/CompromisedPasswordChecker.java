package com.corprag.security;

import java.util.Locale;
import java.util.Set;
import org.springframework.stereotype.Component;

@Component
public class CompromisedPasswordChecker {

    private static final Set<String> COMMON_PASSWORDS = Set.of(
            "password",
            "password1",
            "password12",
            "password123",
            "qwerty123",
            "qwerty12345",
            "adminadmin",
            "admin123456",
            "welcome123",
            "letmein123",
            "changeme123",
            "corporate123",
            "company12345");

    public boolean isCompromised(String password) {
        if (password == null) {
            return false;
        }
        String normalized = password.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
        return COMMON_PASSWORDS.contains(normalized);
    }
}
