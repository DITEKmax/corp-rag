package com.corprag.domain;

import java.time.Instant;
import java.util.UUID;

public record UserRoleAssignment(
        UUID userId,
        UUID roleId,
        UUID assignedBy,
        Instant assignedAt) {
}
