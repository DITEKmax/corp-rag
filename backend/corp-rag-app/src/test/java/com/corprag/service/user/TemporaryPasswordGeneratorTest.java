package com.corprag.service.user;

import static org.assertj.core.api.Assertions.assertThat;

import com.corprag.security.CompromisedPasswordChecker;
import com.corprag.security.PasswordPolicyValidator;
import java.util.List;
import org.junit.jupiter.api.Test;

class TemporaryPasswordGeneratorTest {

    @Test
    void generatedPasswordsPassPolicy() {
        TemporaryPasswordGenerator generator = new TemporaryPasswordGenerator();
        PasswordPolicyValidator validator = new PasswordPolicyValidator(new CompromisedPasswordChecker());
        PasswordPolicyValidator.Context context =
                new PasswordPolicyValidator.Context("john", "john@example.com", "John");

        for (int index = 0; index < 100; index++) {
            String password = generator.generate();
            List<PasswordPolicyValidator.Violation> violations = validator.validate(password, context);

            assertThat(password).matches("[A-Za-z2-9]+");
            assertThat(violations).as("password: %s", password).isEmpty();
        }
    }
}
