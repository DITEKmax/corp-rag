package com.corprag.domain.chat;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record ChatMessage(
        UUID id,
        UUID conversationId,
        ChatMessageRole role,
        AssistantMessageStatus status,
        String content,
        List<ChatCitationSnapshot> citations,
        ChatRetrievalMetaSnapshot retrievalMeta,
        BigDecimal confidence,
        UUID correlationId,
        Instant createdAt,
        Instant deletedAt) {
}
