package com.corprag.repository;

import com.corprag.domain.chat.AssistantMessageStatus;
import com.corprag.domain.chat.ChatCitationSnapshot;
import com.corprag.domain.chat.ChatMessage;
import com.corprag.domain.chat.ChatMessageRole;
import com.corprag.domain.chat.ChatRetrievalMetaSnapshot;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

@Repository
public class ChatMessageRepository {

    private static final TypeReference<List<ChatCitationSnapshot>> CITATION_LIST_TYPE = new TypeReference<>() {
    };

    private final JdbcClient jdbc;
    private final ObjectMapper objectMapper;

    private final RowMapper<ChatMessage> messageMapper = (rs, rowNum) -> new ChatMessage(
            rs.getObject("id", UUID.class),
            rs.getObject("conversation_id", UUID.class),
            ChatMessageRole.valueOf(rs.getString("role")),
            assistantStatus(rs.getString("status")),
            rs.getString("content"),
            readJson(rs.getString("citations"), CITATION_LIST_TYPE),
            readJson(rs.getString("retrieval_meta"), ChatRetrievalMetaSnapshot.class),
            rs.getBigDecimal("confidence"),
            rs.getObject("correlation_id", UUID.class),
            JdbcRowSupport.instant(rs, "created_at"),
            JdbcRowSupport.instant(rs, "deleted_at"));

    public ChatMessageRepository(JdbcClient jdbc, ObjectMapper objectMapper) {
        this.jdbc = jdbc;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public void appendPair(UUID ownerUserId, ChatMessage userMessage, ChatMessage assistantMessage, Instant updatedAt) {
        requireRole(userMessage, ChatMessageRole.USER);
        requireRole(assistantMessage, ChatMessageRole.ASSISTANT);
        if (!userMessage.conversationId().equals(assistantMessage.conversationId())) {
            throw new IllegalArgumentException("Chat pair must use one conversation id");
        }
        if (!userMessage.correlationId().equals(assistantMessage.correlationId())) {
            throw new IllegalArgumentException("Chat pair must share one correlation id");
        }

        int conversationUpdated = jdbc.sql(
                        """
                        UPDATE chat_conversations
                        SET updated_at = :updatedAt
                        WHERE id = :conversationId
                          AND user_id = :ownerUserId
                          AND deleted_at IS NULL
                        """)
                .param("conversationId", userMessage.conversationId())
                .param("ownerUserId", ownerUserId)
                .param("updatedAt", JdbcRowSupport.timestamp(updatedAt))
                .update();
        if (conversationUpdated != 1) {
            throw new EmptyResultDataAccessException("Active chat conversation not found", 1);
        }

        insert(userMessage);
        insert(assistantMessage);
    }

    public List<ChatMessage> listActiveByConversation(UUID ownerUserId, UUID conversationId, int limit, int offset) {
        return jdbc.sql(
                        """
                        SELECT m.*
                        FROM chat_messages m
                        JOIN chat_conversations c ON c.id = m.conversation_id
                        WHERE c.id = :conversationId
                          AND c.user_id = :ownerUserId
                          AND c.deleted_at IS NULL
                          AND m.deleted_at IS NULL
                        ORDER BY m.created_at ASC, m.id ASC
                        LIMIT :limit OFFSET :offset
                        """)
                .param("conversationId", conversationId)
                .param("ownerUserId", ownerUserId)
                .param("limit", limit)
                .param("offset", offset)
                .query(messageMapper)
                .list();
    }

    public long countActiveByConversation(UUID ownerUserId, UUID conversationId) {
        return jdbc.sql(
                        """
                        SELECT COUNT(*)
                        FROM chat_messages m
                        JOIN chat_conversations c ON c.id = m.conversation_id
                        WHERE c.id = :conversationId
                          AND c.user_id = :ownerUserId
                          AND c.deleted_at IS NULL
                          AND m.deleted_at IS NULL
                        """)
                .param("conversationId", conversationId)
                .param("ownerUserId", ownerUserId)
                .query(Long.class)
                .single();
    }

    public List<ChatMessage> findAnsweredHistoryMessages(UUID ownerUserId, UUID conversationId, int pairLimit) {
        return jdbc.sql(
                        """
                        WITH eligible_pairs AS (
                            SELECT u.correlation_id, MAX(a.created_at) AS assistant_created_at
                            FROM chat_messages u
                            JOIN chat_messages a
                              ON a.conversation_id = u.conversation_id
                             AND a.correlation_id = u.correlation_id
                             AND a.role = 'ASSISTANT'
                             AND a.status = 'ANSWERED'
                             AND a.deleted_at IS NULL
                            JOIN chat_conversations c
                              ON c.id = u.conversation_id
                             AND c.user_id = :ownerUserId
                             AND c.deleted_at IS NULL
                            WHERE u.conversation_id = :conversationId
                              AND u.role = 'USER'
                              AND u.deleted_at IS NULL
                            GROUP BY u.correlation_id
                            ORDER BY assistant_created_at DESC
                            LIMIT :pairLimit
                        )
                        SELECT m.*
                        FROM chat_messages m
                        JOIN eligible_pairs p ON p.correlation_id = m.correlation_id
                        WHERE m.conversation_id = :conversationId
                          AND m.deleted_at IS NULL
                          AND (
                              m.role = 'USER'
                              OR (m.role = 'ASSISTANT' AND m.status = 'ANSWERED')
                          )
                        ORDER BY p.assistant_created_at ASC, m.created_at ASC, m.id ASC
                        """)
                .param("conversationId", conversationId)
                .param("ownerUserId", ownerUserId)
                .param("pairLimit", pairLimit)
                .query(messageMapper)
                .list();
    }

    private void insert(ChatMessage message) {
        jdbc.sql(
                        """
                        INSERT INTO chat_messages (
                            id, conversation_id, role, status, content, citations,
                            retrieval_meta, confidence, correlation_id, created_at, deleted_at
                        )
                        VALUES (
                            :id, :conversationId, :role, :status, :content,
                            CAST(:citationsJson AS jsonb), CAST(:retrievalMetaJson AS jsonb),
                            :confidence, :correlationId, :createdAt, :deletedAt
                        )
                        """)
                .param("id", message.id())
                .param("conversationId", message.conversationId())
                .param("role", message.role().name())
                .param("status", message.status() == null ? null : message.status().name())
                .param("content", message.content())
                .param("citationsJson", toJson(message.citations()))
                .param("retrievalMetaJson", toJson(message.retrievalMeta()))
                .param("confidence", message.confidence())
                .param("correlationId", message.correlationId())
                .param("createdAt", JdbcRowSupport.timestamp(message.createdAt()))
                .param("deletedAt", JdbcRowSupport.timestamp(message.deletedAt()))
                .update();
    }

    private static AssistantMessageStatus assistantStatus(String status) {
        return status == null ? null : AssistantMessageStatus.valueOf(status);
    }

    private static void requireRole(ChatMessage message, ChatMessageRole expectedRole) {
        if (message.role() != expectedRole) {
            throw new IllegalArgumentException("Expected " + expectedRole + " chat message");
        }
    }

    private String toJson(Object value) {
        if (value == null) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Failed to serialize chat message JSON", exception);
        }
    }

    private <T> T readJson(String json, Class<T> type) {
        if (json == null) {
            return null;
        }
        try {
            return objectMapper.readValue(json, type);
        } catch (IOException exception) {
            throw new IllegalStateException("Failed to read chat message JSON", exception);
        }
    }

    private <T> T readJson(String json, TypeReference<T> type) {
        if (json == null) {
            return null;
        }
        try {
            return objectMapper.readValue(json, type);
        } catch (IOException exception) {
            throw new IllegalStateException("Failed to read chat message JSON", exception);
        }
    }
}
