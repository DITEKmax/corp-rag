package com.corprag.security;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class PasswordPolicyValidatorTest {

    private final PasswordPolicyValidator validator = new PasswordPolicyValidator(new CompromisedPasswordChecker());

    @Test
    void acceptsStrongPasswordUnrelatedToUser() {
        assertThat(validator.validate(
                        "N3w!SecurePassx",
                        new PasswordPolicyValidator.Context("ivanov", "ivanov@example.com", "Ivan Ivanov")))
                .isEmpty();
    }

    @Test
    void returnsAllApplicableViolations() {
        assertThat(validator.validate(
                        "ivanov2026",
                        new PasswordPolicyValidator.Context("ivanov", "ivanov@example.com", "Ivan Ivanov")))
                .extracting(PasswordPolicyValidator.Violation::code)
                .contains("length", "complexity", "username", "email", "year");
    }

    @Test
    void rejectsLocallyCompromisedPassword() {
        assertThat(validator.validate(
                        "Password123!",
                        new PasswordPolicyValidator.Context("user", "user@example.com", "User Example")))
                .extracting(PasswordPolicyValidator.Violation::code)
                .contains("compromised");
    }
}
