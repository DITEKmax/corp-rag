package com.corprag.service.chat;

import com.corprag.contracts.api.v1.model.AccessLevel;
import com.corprag.contracts.api.v1.model.Citation;
import com.corprag.contracts.api.v1.model.Conversation;
import com.corprag.contracts.api.v1.model.ConversationRole;
import com.corprag.contracts.api.v1.model.HateoasLink;
import com.corprag.contracts.api.v1.model.Message;
import com.corprag.contracts.api.v1.model.QueryRoute;
import com.corprag.contracts.api.v1.model.RetrievalMeta;
import com.corprag.contracts.api.v1.model.RetrieverType;
import com.corprag.domain.chat.ChatCitationSnapshot;
import com.corprag.domain.chat.ChatConversation;
import com.corprag.domain.chat.ChatConversationSummary;
import com.corprag.domain.chat.ChatMessage;
import com.corprag.domain.chat.ChatMessageRole;
import com.corprag.domain.chat.ChatRetrievalMetaSnapshot;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class ChatMessageMapper {

    public Conversation toConversation(ChatConversation conversation, long messageCount) {
        return new Conversation()
                .id(conversation.id())
                .userId(conversation.userId())
                .title(conversation.title())
                .createdAt(toOffsetDateTime(conversation.createdAt()))
                .updatedAt(toOffsetDateTime(conversation.updatedAt()))
                .messageCount(Math.toIntExact(messageCount))
                .links(conversationLinks(conversation.id().toString()));
    }

    public Conversation toConversation(ChatConversationSummary conversation) {
        return new Conversation()
                .id(conversation.id())
                .userId(conversation.userId())
                .title(conversation.title())
                .createdAt(toOffsetDateTime(conversation.createdAt()))
                .updatedAt(toOffsetDateTime(conversation.updatedAt()))
                .messageCount(Math.toIntExact(conversation.messageCount()))
                .links(conversationLinks(conversation.id().toString()));
    }

    public Message toMessage(ChatMessage message) {
        return new Message()
                .id(message.id())
                .conversationId(message.conversationId())
                .role(toRole(message.role()))
                .status(message.status() == null
                        ? null
                        : com.corprag.contracts.api.v1.model.AssistantMessageStatus.fromValue(message.status().name()))
                .content(message.content())
                .citations(toContractCitations(message.citations()))
                .confidence(toFloat(message.confidence()))
                .retrievalMeta(toContractRetrievalMeta(message.retrievalMeta()))
                .createdAt(toOffsetDateTime(message.createdAt()))
                .links(Map.of("conversation", link("/api/v1/chat/conversations/" + message.conversationId())));
    }

    public List<Citation> toContractCitations(List<ChatCitationSnapshot> citations) {
        if (citations == null) {
            return null;
        }
        return citations.stream()
                .map(ChatMessageMapper::toCitation)
                .toList();
    }

    public RetrievalMeta toContractRetrievalMeta(ChatRetrievalMetaSnapshot meta) {
        if (meta == null) {
            return null;
        }
        return new RetrievalMeta()
                .route(meta.route() == null ? null : QueryRoute.fromValue(meta.route()))
                .retrieversAttempted(toRetrieverTypes(meta.retrieversAttempted()))
                .retrieversUsed(toRetrieverTypes(meta.retrieversUsed()))
                .degradationWarnings(meta.degradationWarnings() == null ? List.of() : meta.degradationWarnings())
                .latencyMs(meta.latencyMs())
                .chunksConsidered(meta.chunksConsidered())
                .chunksReturned(meta.chunksReturned())
                .rerankerUsed(meta.rerankerUsed())
                .modelId(meta.modelId());
    }

    private static ConversationRole toRole(ChatMessageRole role) {
        return switch (role) {
            case USER -> ConversationRole.USER;
            case ASSISTANT -> ConversationRole.ASSISTANT;
        };
    }

    private static Citation toCitation(ChatCitationSnapshot citation) {
        return new Citation()
                .documentId(citation.documentId())
                .documentTitle(citation.documentTitle())
                .chunkId(citation.chunkId())
                .sectionPath(citation.sectionPath())
                .quote(citation.quote())
                .snippet(citation.snippet())
                .pageNumber(citation.pageNumber())
                .score(toFloat(citation.score()))
                .accessLevel(AccessLevel.fromValue(citation.accessLevel().name()));
    }

    private static List<RetrieverType> toRetrieverTypes(List<String> retrievers) {
        if (retrievers == null) {
            return List.of();
        }
        return retrievers.stream()
                .map(RetrieverType::fromValue)
                .toList();
    }

    private static Float toFloat(BigDecimal value) {
        return value == null ? null : value.floatValue();
    }

    private static OffsetDateTime toOffsetDateTime(Instant instant) {
        return OffsetDateTime.ofInstant(instant, ZoneOffset.UTC);
    }

    private static Map<String, HateoasLink> conversationLinks(String conversationId) {
        Map<String, HateoasLink> links = new LinkedHashMap<>();
        links.put("self", link("/api/v1/chat/conversations/" + conversationId));
        links.put("messages", link("/api/v1/chat/conversations/" + conversationId + "/messages"));
        links.put("delete", link("/api/v1/chat/conversations/" + conversationId));
        return links;
    }

    private static HateoasLink link(String href) {
        return new HateoasLink().href(href);
    }
}
