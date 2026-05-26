package com.corprag.service.chat;

import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.api.v1.model.Conversation;
import com.corprag.contracts.api.v1.model.CreateConversationRequest;
import com.corprag.contracts.api.v1.model.HateoasLink;
import com.corprag.contracts.api.v1.model.PagedConversations;
import com.corprag.contracts.api.v1.model.PagedMessages;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.chat.ChatConversation;
import com.corprag.repository.ChatConversationRepository;
import com.corprag.repository.ChatMessageRepository;
import java.time.Clock;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class ChatConversationService {

    private static final int MAX_PAGE_SIZE = 100;

    private final ChatConversationRepository conversationRepository;
    private final ChatMessageRepository messageRepository;
    private final ChatMessageMapper mapper;
    private final Clock clock;

    @Autowired
    public ChatConversationService(
            ChatConversationRepository conversationRepository,
            ChatMessageRepository messageRepository,
            ChatMessageMapper mapper) {
        this(conversationRepository, messageRepository, mapper, Clock.systemUTC());
    }

    ChatConversationService(
            ChatConversationRepository conversationRepository,
            ChatMessageRepository messageRepository,
            ChatMessageMapper mapper,
            Clock clock) {
        this.conversationRepository = conversationRepository;
        this.messageRepository = messageRepository;
        this.mapper = mapper;
        this.clock = clock;
    }

    public Conversation create(UUID ownerUserId, CreateConversationRequest request) {
        Instant now = clock.instant();
        ChatConversation conversation = new ChatConversation(
                UUID.randomUUID(),
                ownerUserId,
                normalizeTitle(request),
                now,
                now,
                null);
        conversationRepository.create(conversation);
        return mapper.toConversation(conversation, 0);
    }

    public PagedConversations list(UUID ownerUserId, int page, int size) {
        validatePage(page);
        validateSize(size);
        return new PagedConversations()
                .items(conversationRepository.listActiveByOwner(ownerUserId, size, offset(page, size)).stream()
                        .map(mapper::toConversation)
                        .toList())
                .page(page)
                .size(size)
                .total(conversationRepository.countActiveByOwner(ownerUserId))
                .links(Map.of("self", link("/api/v1/chat/conversations?page=" + page + "&size=" + size)));
    }

    public Conversation get(UUID ownerUserId, UUID conversationId) {
        ChatConversation conversation = activeConversation(ownerUserId, conversationId);
        long messageCount = messageRepository.countActiveByConversation(ownerUserId, conversationId);
        return mapper.toConversation(conversation, messageCount);
    }

    public void delete(UUID ownerUserId, UUID conversationId) {
        if (!conversationRepository.softDelete(conversationId, ownerUserId, clock.instant())) {
            throw notFound();
        }
    }

    public PagedMessages listMessages(UUID ownerUserId, UUID conversationId, int page, int size) {
        validatePage(page);
        validateSize(size);
        activeConversation(ownerUserId, conversationId);
        return new PagedMessages()
                .items(messageRepository.listActiveByConversation(ownerUserId, conversationId, size, offset(page, size))
                        .stream()
                        .map(mapper::toMessage)
                        .toList())
                .page(page)
                .size(size)
                .total(messageRepository.countActiveByConversation(ownerUserId, conversationId))
                .links(Map.of("self", link("/api/v1/chat/conversations/" + conversationId
                        + "/messages?page=" + page + "&size=" + size)));
    }

    private ChatConversation activeConversation(UUID ownerUserId, UUID conversationId) {
        return conversationRepository.findActiveByOwner(conversationId, ownerUserId)
                .orElseThrow(ChatConversationService::notFound);
    }

    private static String normalizeTitle(CreateConversationRequest request) {
        String title = request == null ? null : request.getTitle();
        if (title == null || title.isBlank()) {
            return ChatConversationRepository.PLACEHOLDER_TITLE;
        }
        String trimmed = title.trim();
        if (trimmed.length() > 200) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "Conversation title is invalid");
        }
        return trimmed;
    }

    private static int offset(int page, int size) {
        return Math.multiplyExact(page, size);
    }

    private static void validatePage(int page) {
        if (page < 0) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "Page must be non-negative");
        }
    }

    private static void validateSize(int size) {
        if (size < 1 || size > MAX_PAGE_SIZE) {
            throw new ApiProblemException(ErrorCodes.VALIDATION_FAILED, "Size must be between 1 and 100");
        }
    }

    private static ApiProblemException notFound() {
        return new ApiProblemException(ErrorCodes.CONVERSATION_NOT_FOUND, "Conversation not found");
    }

    private static HateoasLink link(String href) {
        return new HateoasLink().href(href);
    }
}
