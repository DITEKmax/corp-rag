package com.corprag.service.chat;

import com.corprag.repository.ChatConversationRepository;
import java.time.Instant;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class ChatTitleService {

    private static final int MAX_DERIVED_TITLE_LENGTH = 80;

    private final ChatConversationRepository conversationRepository;

    public ChatTitleService(ChatConversationRepository conversationRepository) {
        this.conversationRepository = conversationRepository;
    }

    public void deriveTitleFromFirstMessageIfNeeded(
            UUID ownerUserId,
            UUID conversationId,
            String firstUserMessage,
            Instant updatedAt) {
        conversationRepository.deriveTitleFromFirstMessage(
                conversationId,
                ownerUserId,
                deriveTitle(firstUserMessage),
                updatedAt);
    }

    String deriveTitle(String message) {
        String normalized = message == null
                ? ""
                : message.replaceAll("\\s+", " ").trim();
        if (normalized.isBlank()) {
            return ChatConversationRepository.PLACEHOLDER_TITLE;
        }
        if (normalized.length() <= MAX_DERIVED_TITLE_LENGTH) {
            return normalized;
        }
        return normalized.substring(0, MAX_DERIVED_TITLE_LENGTH - 3).stripTrailing() + "...";
    }
}
