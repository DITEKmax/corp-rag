package com.corprag.service.chat;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.api.v1.model.AssistantMessageStatus;
import com.corprag.contracts.api.v1.model.Conversation;
import com.corprag.contracts.api.v1.model.CreateConversationRequest;
import com.corprag.contracts.api.v1.model.PagedMessages;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.chat.ChatConversation;
import com.corprag.domain.chat.ChatConversationSummary;
import com.corprag.domain.chat.ChatMessage;
import com.corprag.domain.chat.ChatMessageRole;
import com.corprag.repository.ChatConversationRepository;
import com.corprag.repository.ChatMessageRepository;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class ChatConversationServiceTest {

    private static final UUID OWNER_ID = UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final UUID CONVERSATION_ID = UUID.fromString("c1234567-e89b-12d3-a456-426614174000");
    private static final UUID USER_MESSAGE_ID = UUID.fromString("11111111-1111-4111-8111-111111111001");
    private static final UUID ASSISTANT_MESSAGE_ID = UUID.fromString("22222222-2222-4222-8222-222222222002");
    private static final UUID CORRELATION_ID = UUID.fromString("33333333-3333-4333-8333-333333333003");
    private static final Instant NOW = Instant.parse("2026-05-21T10:00:00Z");

    private final ChatConversationRepository conversationRepository = mock(ChatConversationRepository.class);
    private final ChatMessageRepository messageRepository = mock(ChatMessageRepository.class);
    private final ChatConversationService service = new ChatConversationService(
            conversationRepository,
            messageRepository,
            new ChatMessageMapper(),
            Clock.fixed(NOW, ZoneOffset.UTC));

    @Test
    void createUsesPlaceholderWhenNoTitleIsProvided() {
        ArgumentCaptor<ChatConversation> conversationCaptor = ArgumentCaptor.forClass(ChatConversation.class);

        Conversation created = service.create(OWNER_ID, new CreateConversationRequest());

        verify(conversationRepository).create(conversationCaptor.capture());
        ChatConversation saved = conversationCaptor.getValue();
        assertThat(saved.id()).isNotNull();
        assertThat(saved.userId()).isEqualTo(OWNER_ID);
        assertThat(saved.title()).isEqualTo(ChatConversationRepository.PLACEHOLDER_TITLE);
        assertThat(saved.createdAt()).isEqualTo(NOW);
        assertThat(saved.updatedAt()).isEqualTo(NOW);
        assertThat(created.getTitle()).isEqualTo(ChatConversationRepository.PLACEHOLDER_TITLE);
        assertThat(created.getMessageCount()).isZero();
    }

    @Test
    void createAcceptsTrimmedContractTitleWhenProvided() {
        Conversation created = service.create(OWNER_ID, new CreateConversationRequest().title("  HR policy  "));

        assertThat(created.getTitle()).isEqualTo("HR policy");
    }

    @Test
    void listDelegatesPaginationToRepositoryAndMapsMessageCount() {
        when(conversationRepository.listActiveByOwner(OWNER_ID, 10, 20))
                .thenReturn(List.of(summary()));
        when(conversationRepository.countActiveByOwner(OWNER_ID)).thenReturn(1L);

        var page = service.list(OWNER_ID, 2, 10);

        assertThat(page.getPage()).isEqualTo(2);
        assertThat(page.getSize()).isEqualTo(10);
        assertThat(page.getTotal()).isEqualTo(1);
        assertThat(page.getItems()).singleElement()
                .satisfies(item -> {
                    assertThat(item.getId()).isEqualTo(CONVERSATION_ID);
                    assertThat(item.getMessageCount()).isEqualTo(3);
                    assertThat(item.getLinks()).containsKeys("self", "messages", "delete");
                });
    }

    @Test
    void getReturnsConversationNotFoundForMissingForeignOrDeletedConversation() {
        when(conversationRepository.findActiveByOwner(CONVERSATION_ID, OWNER_ID)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.get(OWNER_ID, CONVERSATION_ID))
                .isInstanceOf(ApiProblemException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCodes.CONVERSATION_NOT_FOUND);
    }

    @Test
    void deleteReturnsConversationNotFoundWhenRepositoryCannotFindOwnerRow() {
        when(conversationRepository.softDelete(CONVERSATION_ID, OWNER_ID, NOW)).thenReturn(false);

        assertThatThrownBy(() -> service.delete(OWNER_ID, CONVERSATION_ID))
                .isInstanceOf(ApiProblemException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCodes.CONVERSATION_NOT_FOUND);
    }

    @Test
    void listMessagesKeepsFailedAssistantOutcomesVisibleWithoutPlaceholderContent() {
        when(conversationRepository.findActiveByOwner(CONVERSATION_ID, OWNER_ID))
                .thenReturn(Optional.of(conversation()));
        when(messageRepository.listActiveByConversation(OWNER_ID, CONVERSATION_ID, 20, 0))
                .thenReturn(List.of(userMessage(), timeoutAssistantMessage()));
        when(messageRepository.countActiveByConversation(OWNER_ID, CONVERSATION_ID)).thenReturn(2L);

        PagedMessages messages = service.listMessages(OWNER_ID, CONVERSATION_ID, 0, 20);

        assertThat(messages.getItems()).hasSize(2);
        assertThat(messages.getItems().get(0).getStatus()).isNull();
        assertThat(messages.getItems().get(0).getContent()).isEqualTo("Why did it fail?");
        assertThat(messages.getItems().get(1).getStatus()).isEqualTo(AssistantMessageStatus.TIMEOUT);
        assertThat(messages.getItems().get(1).getContent()).isNull();
        assertThat(messages.getItems().get(1).getCitations()).isNull();
        assertThat(messages.getItems().get(1).getRetrievalMeta()).isNull();
    }

    @Test
    void listMessagesRequiresActiveConversationBeforeReadingRows() {
        when(conversationRepository.findActiveByOwner(CONVERSATION_ID, OWNER_ID)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.listMessages(OWNER_ID, CONVERSATION_ID, 0, 20))
                .isInstanceOf(ApiProblemException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCodes.CONVERSATION_NOT_FOUND);
    }

    private static ChatConversation conversation() {
        return new ChatConversation(
                CONVERSATION_ID,
                OWNER_ID,
                "HR policy",
                NOW,
                NOW,
                null);
    }

    private static ChatConversationSummary summary() {
        return new ChatConversationSummary(
                CONVERSATION_ID,
                OWNER_ID,
                "HR policy",
                NOW.minusSeconds(60),
                NOW,
                3);
    }

    private static ChatMessage userMessage() {
        return new ChatMessage(
                USER_MESSAGE_ID,
                CONVERSATION_ID,
                ChatMessageRole.USER,
                null,
                "Why did it fail?",
                null,
                null,
                null,
                CORRELATION_ID,
                NOW,
                null);
    }

    private static ChatMessage timeoutAssistantMessage() {
        return new ChatMessage(
                ASSISTANT_MESSAGE_ID,
                CONVERSATION_ID,
                ChatMessageRole.ASSISTANT,
                com.corprag.domain.chat.AssistantMessageStatus.TIMEOUT,
                null,
                null,
                null,
                null,
                CORRELATION_ID,
                NOW.plusMillis(1),
                null);
    }
}
