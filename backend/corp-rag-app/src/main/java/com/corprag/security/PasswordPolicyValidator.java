package com.corprag.security;

import java.time.Year;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import org.springframework.stereotype.Component;

@Component
public class PasswordPolicyValidator {

    private final CompromisedPasswordChecker compromisedPasswordChecker;

    public PasswordPolicyValidator(CompromisedPasswordChecker compromisedPasswordChecker) {
        this.compromisedPasswordChecker = compromisedPasswordChecker;
    }

    public List<Violation> validate(String password, Context context) {
        List<Violation> violations = new ArrayList<>();
        if (password == null || password.length() < 12) {
            violations.add(new Violation("length", "Password must be at least 12 characters"));
        }
        if (complexityClasses(password) < 3) {
            violations.add(new Violation("complexity", "Password must use at least three character classes"));
        }
        String normalizedPassword = normalize(password);
        if (containsNonBlank(normalizedPassword, normalize(context.username()))) {
            violations.add(new Violation("username", "Password must not contain the username"));
        }
        String emailLocalPart = context.email() == null ? "" : context.email().split("@", 2)[0];
        if (containsNonBlank(normalizedPassword, normalize(emailLocalPart))) {
            violations.add(new Violation("email", "Password must not contain the email local part"));
        }
        if (normalizedPassword.contains(String.valueOf(Year.now().getValue()))) {
            violations.add(new Violation("year", "Password must not contain the current year"));
        }
        if (compromisedPasswordChecker.isCompromised(password)) {
            violations.add(new Violation("compromised", "Password is too common"));
        }
        return violations;
    }

    private static int complexityClasses(String password) {
        if (password == null) {
            return 0;
        }
        int classes = 0;
        if (password.chars().anyMatch(Character::isLowerCase)) {
            classes++;
        }
        if (password.chars().anyMatch(Character::isUpperCase)) {
            classes++;
        }
        if (password.chars().anyMatch(Character::isDigit)) {
            classes++;
        }
        if (password.chars().anyMatch(value -> !Character.isLetterOrDigit(value))) {
            classes++;
        }
        return classes;
    }

    private static boolean containsNonBlank(String haystack, String needle) {
        return needle != null && needle.length() >= 3 && haystack.contains(needle);
    }

    private static String normalize(String value) {
        return value == null ? "" : value.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
    }

    public record Context(String username, String email, String fullName) {
    }

    public record Violation(String code, String message) {
    }
}
