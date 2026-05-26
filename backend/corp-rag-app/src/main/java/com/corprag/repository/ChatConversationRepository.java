package com.corprag.repository;

import com.corprag.domain.chat.ChatConversation;
import com.corprag.domain.chat.ChatConversationSummary;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

@Repository
public class ChatConversationRepository {

    public static final String PLACEHOLDER_TITLE = "Новый диалог";

    private static final RowMapper<ChatConversation> CONVERSATION_MAPPER = (rs, rowNum) -> new ChatConversation(
            rs.getObject("id", UUID.class),
            rs.getObject("user_id", UUID.class),
            rs.getString("title"),
            JdbcRowSupport.instant(rs, "created_at"),
            JdbcRowSupport.instant(rs, "updated_at"),
            JdbcRowSupport.instant(rs, "deleted_at"));

    private static final RowMapper<ChatConversationSummary> SUMMARY_MAPPER = (rs, rowNum) -> new ChatConversationSummary(
            rs.getObject("id", UUID.class),
            rs.getObject("user_id", UUID.class),
            rs.getString("title"),
            JdbcRowSupport.instant(rs, "created_at"),
            JdbcRowSupport.instant(rs, "updated_at"),
            rs.getLong("message_count"));

    private final JdbcClient jdbc;

    public ChatConversationRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public void create(ChatConversation conversation) {
        jdbc.sql(
                        """
                        INSERT INTO chat_conversations (
                            id, user_id, title, created_at, updated_at, deleted_at
                        )
                        VALUES (
                            :id, :userId, :title, :createdAt, :updatedAt, :deletedAt
                        )
                        """)
                .param("id", conversation.id())
                .param("userId", conversation.userId())
                .param("title", conversation.title())
                .param("createdAt", JdbcRowSupport.timestamp(conversation.createdAt()))
                .param("updatedAt", JdbcRowSupport.timestamp(conversation.updatedAt()))
                .param("deletedAt", JdbcRowSupport.timestamp(conversation.deletedAt()))
                .update();
    }

    public Optional<ChatConversation> findActiveByOwner(UUID conversationId, UUID ownerUserId) {
        return jdbc.sql(
                        """
                        SELECT *
                        FROM chat_conversations
                        WHERE id = :conversationId
                          AND user_id = :ownerUserId
                          AND deleted_at IS NULL
                        """)
                .param("conversationId", conversationId)
                .param("ownerUserId", ownerUserId)
                .query(CONVERSATION_MAPPER)
                .optional();
    }

    public List<ChatConversationSummary> listActiveByOwner(UUID ownerUserId, int limit, int offset) {
        return jdbc.sql(
                        """
                        SELECT c.*,
                               (
                                   SELECT COUNT(*)
                                   FROM chat_messages m
                                   WHERE m.conversation_id = c.id
                                     AND m.deleted_at IS NULL
                               ) AS message_count
                        FROM chat_conversations c
                        WHERE c.user_id = :ownerUserId
                          AND c.deleted_at IS NULL
                        ORDER BY c.updated_at DESC, c.id DESC
                        LIMIT :limit OFFSET :offset
                        """)
                .param("ownerUserId", ownerUserId)
                .param("limit", limit)
                .param("offset", offset)
                .query(SUMMARY_MAPPER)
                .list();
    }

    public long countActiveByOwner(UUID ownerUserId) {
        return jdbc.sql(
                        """
                        SELECT COUNT(*)
                        FROM chat_conversations
                        WHERE user_id = :ownerUserId
                          AND deleted_at IS NULL
                        """)
                .param("ownerUserId", ownerUserId)
                .query(Long.class)
                .single();
    }

    public boolean deriveTitleFromFirstMessage(UUID conversationId, UUID ownerUserId, String title, Instant updatedAt) {
        int updated = jdbc.sql(
                        """
                        UPDATE chat_conversations
                        SET title = :title,
                            updated_at = :updatedAt
                        WHERE id = :conversationId
                          AND user_id = :ownerUserId
                          AND deleted_at IS NULL
                          AND title = :placeholderTitle
                          AND NOT EXISTS (
                              SELECT 1
                              FROM chat_messages
                              WHERE conversation_id = :conversationId
                                AND deleted_at IS NULL
                          )
                        """)
                .param("conversationId", conversationId)
                .param("ownerUserId", ownerUserId)
                .param("title", title)
                .param("updatedAt", JdbcRowSupport.timestamp(updatedAt))
                .param("placeholderTitle", PLACEHOLDER_TITLE)
                .update();
        return updated == 1;
    }

    @Transactional
    public boolean softDelete(UUID conversationId, UUID ownerUserId, Instant deletedAt) {
        int parentUpdated = jdbc.sql(
                        """
                        UPDATE chat_conversations
                        SET deleted_at = COALESCE(deleted_at, :deletedAt),
                            updated_at = CASE
                                WHEN deleted_at IS NULL THEN :deletedAt
                                ELSE updated_at
                            END
                        WHERE id = :conversationId
                          AND user_id = :ownerUserId
                        """)
                .param("conversationId", conversationId)
                .param("ownerUserId", ownerUserId)
                .param("deletedAt", JdbcRowSupport.timestamp(deletedAt))
                .update();

        if (parentUpdated == 0) {
            return false;
        }

        jdbc.sql(
                        """
                        UPDATE chat_messages
                        SET deleted_at = COALESCE(deleted_at, :deletedAt)
                        WHERE conversation_id = :conversationId
                        """)
                .param("conversationId", conversationId)
                .param("deletedAt", JdbcRowSupport.timestamp(deletedAt))
                .update();
        return true;
    }
}
