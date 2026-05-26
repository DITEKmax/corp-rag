package com.corprag.service.chat;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.corprag.domain.chat.AssistantMessageStatus;
import com.corprag.domain.chat.ChatMessage;
import com.corprag.domain.chat.ChatMessageRole;
import com.corprag.repository.ChatMessageRepository;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class ChatHistoryAssemblerTest {

    private static final UUID OWNER_ID = UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final UUID CONVERSATION_ID = UUID.fromString("c1234567-e89b-12d3-a456-426614174000");
    private static final UUID GOOD_CORRELATION = UUID.fromString("22222222-2222-4222-8222-222222222222");
    private static final UUID FAILED_CORRELATION = UUID.fromString("33333333-3333-4333-8333-333333333333");
    private static final Instant NOW = Instant.parse("2026-05-21T10:00:00Z");

    private final ChatMessageRepository messageRepository = mock(ChatMessageRepository.class);
    private final ChatHistoryAssembler assembler = new ChatHistoryAssembler(messageRepository);

    @Test
    void loadsLastTenAnsweredPairsFromRepositoryAndDropsDanglingPairs() {
        when(messageRepository.findAnsweredHistoryMessages(
                        OWNER_ID,
                        CONVERSATION_ID,
                        ChatHistoryAssembler.ANSWERED_PAIR_LIMIT))
                .thenReturn(List.of(
                        user(GOOD_CORRELATION, "Q1"),
                        assistant(GOOD_CORRELATION, AssistantMessageStatus.ANSWERED, "A1"),
                        user(FAILED_CORRELATION, "Q2"),
                        assistant(FAILED_CORRELATION, AssistantMessageStatus.TIMEOUT, null)));

        List<ChatMessage> history = assembler.answeredPairHistory(OWNER_ID, CONVERSATION_ID);

        assertThat(history).extracting(ChatMessage::content).containsExactly("Q1", "A1");
        verify(messageRepository).findAnsweredHistoryMessages(
                OWNER_ID,
                CONVERSATION_ID,
                ChatHistoryAssembler.ANSWERED_PAIR_LIMIT);
    }

    private static ChatMessage user(UUID correlationId, String content) {
        return new ChatMessage(
                UUID.randomUUID(),
                CONVERSATION_ID,
                ChatMessageRole.USER,
                null,
                content,
                null,
                null,
                null,
                correlationId,
                NOW,
                null);
    }

    private static ChatMessage assistant(UUID correlationId, AssistantMessageStatus status, String content) {
        return new ChatMessage(
                UUID.randomUUID(),
                CONVERSATION_ID,
                ChatMessageRole.ASSISTANT,
                status,
                content,
                null,
                null,
                null,
                correlationId,
                NOW.plusMillis(1),
                null);
    }
}
