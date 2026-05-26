package com.corprag.domain.chat;

import java.time.Instant;
import java.util.UUID;

public record ChatConversation(
        UUID id,
        UUID userId,
        String title,
        Instant createdAt,
        Instant updatedAt,
        Instant deletedAt) {
}
