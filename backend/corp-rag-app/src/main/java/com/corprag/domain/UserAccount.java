package com.corprag.domain;

import java.time.Instant;
import java.util.UUID;

public record UserAccount(
        UUID id,
        String username,
        String email,
        String fullName,
        String department,
        String passwordHash,
        boolean active,
        boolean mustChangePassword,
        Instant createdAt,
        Instant updatedAt,
        Instant deletedAt,
        long version) {
}
