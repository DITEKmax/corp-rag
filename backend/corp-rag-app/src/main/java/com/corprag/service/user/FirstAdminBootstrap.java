package com.corprag.service.user;

import com.corprag.config.FirstAdminProperties;
import java.util.Arrays;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

@Component
public class FirstAdminBootstrap implements ApplicationRunner {

    private static final Logger LOGGER = LoggerFactory.getLogger(FirstAdminBootstrap.class);

    private final FirstAdminProperties properties;
    private final TemporaryPasswordGenerator temporaryPasswordGenerator;
    private final UserService userService;
    private final Environment environment;

    public FirstAdminBootstrap(
            FirstAdminProperties properties,
            TemporaryPasswordGenerator temporaryPasswordGenerator,
            UserService userService,
            Environment environment) {
        this.properties = properties;
        this.temporaryPasswordGenerator = temporaryPasswordGenerator;
        this.userService = userService;
        this.environment = environment;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (!properties.isEnabled()) {
            return;
        }
        if (properties.getUsername().isBlank() || properties.getEmail().isBlank()) {
            return;
        }
        if (userService.hasAdminUser()) {
            return;
        }
        String password = properties.getPassword();
        if (password.isBlank()) {
            if (Arrays.asList(environment.getActiveProfiles()).contains("prod")) {
                throw new IllegalStateException("ADMIN_PASSWORD is required in prod when first-admin bootstrap is configured");
            }
            password = temporaryPasswordGenerator.generate();
            LOGGER.warn("Generated first-admin development password for {}: {}", properties.getUsername(), password);
        }
        userService.createBootstrapAdmin(properties.getUsername(), properties.getEmail(), password);
    }
}
