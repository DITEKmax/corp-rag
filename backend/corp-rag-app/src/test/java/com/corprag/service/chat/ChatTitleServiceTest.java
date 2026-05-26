package com.corprag.service.chat;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import com.corprag.repository.ChatConversationRepository;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class ChatTitleServiceTest {

    private static final UUID OWNER_ID = UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final UUID CONVERSATION_ID = UUID.fromString("c1234567-e89b-12d3-a456-426614174000");
    private static final Instant NOW = Instant.parse("2026-05-21T10:00:00Z");

    private final ChatConversationRepository conversationRepository = mock(ChatConversationRepository.class);
    private final ChatTitleService titleService = new ChatTitleService(conversationRepository);

    @Test
    void derivesBoundedTitleFromFirstUserMessage() {
        String title = titleService.deriveTitle(
                "  Explain   the annual leave policy for employees with long tenure and include every detail.  ");

        assertThat(title).startsWith("Explain the annual leave policy for employees with long tenure");
        assertThat(title).endsWith("...");
        assertThat(title).hasSizeLessThanOrEqualTo(80);
    }

    @Test
    void delegatesOneTimePlaceholderReplacementToRepository() {
        titleService.deriveTitleFromFirstMessageIfNeeded(
                OWNER_ID,
                CONVERSATION_ID,
                "What is the HR policy?",
                NOW);

        verify(conversationRepository).deriveTitleFromFirstMessage(
                CONVERSATION_ID,
                OWNER_ID,
                "What is the HR policy?",
                NOW);
    }
}
