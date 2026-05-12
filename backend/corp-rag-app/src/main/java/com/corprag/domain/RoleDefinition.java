package com.corprag.domain;

import java.time.Instant;
import java.util.UUID;

public record RoleDefinition(
        UUID id,
        String code,
        String description,
        boolean system,
        Instant createdAt,
        Instant updatedAt,
        Instant deletedAt,
        long version) {
}
