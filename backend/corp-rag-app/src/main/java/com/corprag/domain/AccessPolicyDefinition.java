package com.corprag.domain;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record AccessPolicyDefinition(
        UUID id,
        UUID roleId,
        List<AccessLevel> accessLevels,
        List<String> departments,
        List<DocType> docTypes,
        Instant createdAt,
        Instant updatedAt,
        long version) {
}
