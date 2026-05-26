package com.corprag.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.corprag.domain.AccessLevel;
import com.corprag.domain.UserAccount;
import com.corprag.domain.chat.AssistantMessageStatus;
import com.corprag.domain.chat.ChatCitationSnapshot;
import com.corprag.domain.chat.ChatConversation;
import com.corprag.domain.chat.ChatConversationSummary;
import com.corprag.domain.chat.ChatMessage;
import com.corprag.domain.chat.ChatMessageRole;
import com.corprag.domain.chat.ChatRetrievalMetaSnapshot;
import com.corprag.testsupport.PostgresIntegrationTestSupport;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest
@Testcontainers(disabledWithoutDocker = true)
class ChatRepositoryPersistenceIT extends PostgresIntegrationTestSupport {

    @Autowired
    private JdbcClient jdbc;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private ChatConversationRepository conversationRepository;

    @Autowired
    private ChatMessageRepository messageRepository;

    @Test
    void migratedChatTablesUseVerifiedNamesAndForeignKeys() {
        List<String> tableNames = jdbc.sql(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                        """)
                .query(String.class)
                .list();

        assertThat(tableNames).contains("chat_conversations", "chat_messages");

        List<String> foreignKeys = jdbc.sql(
                        """
                        SELECT tc.constraint_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.constraint_column_usage ccu
                          ON ccu.constraint_name = tc.constraint_name
                        WHERE tc.constraint_type = 'FOREIGN KEY'
                          AND tc.table_name IN ('chat_conversations', 'chat_messages')
                          AND ccu.table_name IN ('users', 'chat_conversations')
                        """)
                .query(String.class)
                .list();

        assertThat(foreignKeys).hasSizeGreaterThanOrEqualTo(2);
    }

    @Test
    void conversationsUseOneTimeTitleDerivationAndUpdatedAtOrdering() {
        UserAccount user = createUser("chat-title");
        Instant now = Instant.parse("2026-05-20T10:00:00Z");
        ChatConversation older = conversation(user.id(), now);
        ChatConversation newer = conversation(user.id(), now.plusSeconds(10));
        conversationRepository.create(older);
        conversationRepository.create(newer);

        assertThat(conversationRepository.deriveTitleFromFirstMessage(
                        older.id(), user.id(), "Vacation policy", now.plusSeconds(20)))
                .isTrue();
        appendPair(user.id(), older.id(), "first question", AssistantMessageStatus.ANSWERED, "first answer", now.plusSeconds(21));
        assertThat(conversationRepository.deriveTitleFromFirstMessage(
                        older.id(), user.id(), "Later rename attempt", now.plusSeconds(30)))
                .isFalse();

        assertThat(conversationRepository.findActiveByOwner(older.id(), user.id()))
                .hasValueSatisfying(found -> assertThat(found.title()).isEqualTo("Vacation policy"));

        List<ChatConversationSummary> conversations = conversationRepository.listActiveByOwner(user.id(), 10, 0);
        assertThat(conversations).extracting(ChatConversationSummary::id).containsExactly(older.id(), newer.id());
        assertThat(conversations.get(0).messageCount()).isEqualTo(2);
    }

    @Test
    void messagesRoundTripJsonSnapshotsCorrelationAndNullableOutcomeContent() {
        UserAccount user = createUser("chat-json");
        Instant now = Instant.parse("2026-05-20T11:00:00Z");
        ChatConversation conversation = conversation(user.id(), now);
        conversationRepository.create(conversation);

        UUID correlationId = UUID.randomUUID();
        ChatMessage userMessage = userMessage(conversation.id(), correlationId, "What is the leave policy?", now.plusSeconds(1));
        ChatMessage assistantMessage = assistantMessage(
                conversation.id(),
                correlationId,
                AssistantMessageStatus.ANSWERED,
                "Employees get 31 days after five years [1].",
                List.of(citation()),
                retrievalMeta(),
                new BigDecimal("0.812"),
                now.plusSeconds(2));
        messageRepository.appendPair(user.id(), userMessage, assistantMessage, now.plusSeconds(2));

        UUID degradedCorrelationId = UUID.randomUUID();
        messageRepository.appendPair(
                user.id(),
                userMessage(conversation.id(), degradedCorrelationId, "Retry formatting", now.plusSeconds(3)),
                assistantMessage(
                        conversation.id(),
                        degradedCorrelationId,
                        AssistantMessageStatus.DEGRADED,
                        null,
                        null,
                        retrievalMeta(),
                        null,
                        now.plusSeconds(4)),
                now.plusSeconds(4));

        List<ChatMessage> messages = messageRepository.listActiveByConversation(user.id(), conversation.id(), 20, 0);
        assertThat(messages).hasSize(4);
        assertThat(messages.get(0).correlationId()).isEqualTo(correlationId);
        assertThat(messages.get(1).correlationId()).isEqualTo(correlationId);
        assertThat(messages.get(1).citations()).containsExactly(citation());
        assertThat(messages.get(1).retrievalMeta()).isEqualTo(retrievalMeta());
        assertThat(messages.get(3).status()).isEqualTo(AssistantMessageStatus.DEGRADED);
        assertThat(messages.get(3).content()).isNull();
        assertThat(messages.get(3).citations()).isNull();
    }

    @Test
    void softDeleteIsIdempotentAndHidesConversationAndMessagesWithoutHardDelete() {
        UserAccount user = createUser("chat-delete");
        Instant now = Instant.parse("2026-05-20T12:00:00Z");
        ChatConversation conversation = conversation(user.id(), now);
        conversationRepository.create(conversation);
        appendPair(user.id(), conversation.id(), "delete me", AssistantMessageStatus.ANSWERED, "answer", now.plusSeconds(1));

        assertThat(conversationRepository.softDelete(conversation.id(), user.id(), now.plusSeconds(10))).isTrue();
        assertThat(conversationRepository.softDelete(conversation.id(), user.id(), now.plusSeconds(11))).isTrue();

        assertThat(conversationRepository.findActiveByOwner(conversation.id(), user.id())).isEmpty();
        assertThat(conversationRepository.listActiveByOwner(user.id(), 10, 0)).isEmpty();
        assertThat(messageRepository.listActiveByConversation(user.id(), conversation.id(), 10, 0)).isEmpty();

        Integer conversationRows = jdbc.sql("SELECT COUNT(*) FROM chat_conversations WHERE id = :id")
                .param("id", conversation.id())
                .query(Integer.class)
                .single();
        Integer deletedMessages = jdbc.sql(
                        """
                        SELECT COUNT(*)
                        FROM chat_messages
                        WHERE conversation_id = :conversationId
                          AND deleted_at IS NOT NULL
                        """)
                .param("conversationId", conversation.id())
                .query(Integer.class)
                .single();

        assertThat(conversationRows).isEqualTo(1);
        assertThat(deletedMessages).isEqualTo(2);
    }

    @Test
    void answeredHistoryReturnsLastTenCompletePairsAndDropsFailedPairs() {
        UserAccount user = createUser("chat-history");
        Instant now = Instant.parse("2026-05-20T13:00:00Z");
        ChatConversation conversation = conversation(user.id(), now);
        conversationRepository.create(conversation);

        for (int index = 0; index < 12; index++) {
            appendPair(
                    user.id(),
                    conversation.id(),
                    "question-" + index,
                    AssistantMessageStatus.ANSWERED,
                    "answer-" + index,
                    now.plusSeconds(index * 10L));
        }
        appendPair(
                user.id(),
                conversation.id(),
                "failed-question",
                AssistantMessageStatus.TIMEOUT,
                null,
                now.plusSeconds(200));
        appendPair(
                user.id(),
                conversation.id(),
                "degraded-question",
                AssistantMessageStatus.DEGRADED,
                null,
                now.plusSeconds(210));

        List<ChatMessage> history = messageRepository.findAnsweredHistoryMessages(user.id(), conversation.id(), 10);

        assertThat(history).hasSize(20);
        assertThat(history).extracting(ChatMessage::content)
                .doesNotContain("failed-question", "degraded-question")
                .containsExactlyElementsOf(expectedHistoryContents(2, 12));
        assertThat(history)
                .filteredOn(message -> message.role() == ChatMessageRole.ASSISTANT)
                .allSatisfy(message -> assertThat(message.status()).isEqualTo(AssistantMessageStatus.ANSWERED));
    }

    private UserAccount createUser(String prefix) {
        Instant now = Instant.parse("2026-05-20T09:00:00Z");
        String suffix = UUID.randomUUID()
                .toString()
                .replace("-", "")
                .substring(0, 10)
                .toLowerCase(Locale.ROOT);
        UserAccount user = new UserAccount(
                UUID.randomUUID(),
                prefix + "." + suffix,
                prefix + "." + suffix + "@example.com",
                "Chat Test User",
                "HR",
                "test-only-password-hash",
                true,
                false,
                now,
                now,
                null,
                0);
        userRepository.create(user);
        return user;
    }

    private static ChatConversation conversation(UUID userId, Instant createdAt) {
        return new ChatConversation(
                UUID.randomUUID(),
                userId,
                ChatConversationRepository.PLACEHOLDER_TITLE,
                createdAt,
                createdAt,
                null);
    }

    private void appendPair(
            UUID ownerUserId,
            UUID conversationId,
            String userContent,
            AssistantMessageStatus assistantStatus,
            String assistantContent,
            Instant createdAt) {
        UUID correlationId = UUID.randomUUID();
        messageRepository.appendPair(
                ownerUserId,
                userMessage(conversationId, correlationId, userContent, createdAt),
                assistantMessage(
                        conversationId,
                        correlationId,
                        assistantStatus,
                        assistantContent,
                        assistantStatus == AssistantMessageStatus.ANSWERED ? List.of(citation()) : null,
                        assistantStatus == AssistantMessageStatus.TIMEOUT ? null : retrievalMeta(),
                        assistantStatus == AssistantMessageStatus.ANSWERED ? new BigDecimal("0.700") : null,
                        createdAt.plusMillis(1)),
                createdAt.plusMillis(1));
    }

    private static ChatMessage userMessage(UUID conversationId, UUID correlationId, String content, Instant createdAt) {
        return new ChatMessage(
                UUID.randomUUID(),
                conversationId,
                ChatMessageRole.USER,
                null,
                content,
                null,
                null,
                null,
                correlationId,
                createdAt,
                null);
    }

    private static ChatMessage assistantMessage(
            UUID conversationId,
            UUID correlationId,
            AssistantMessageStatus status,
            String content,
            List<ChatCitationSnapshot> citations,
            ChatRetrievalMetaSnapshot retrievalMeta,
            BigDecimal confidence,
            Instant createdAt) {
        return new ChatMessage(
                UUID.randomUUID(),
                conversationId,
                ChatMessageRole.ASSISTANT,
                status,
                content,
                citations,
                retrievalMeta,
                confidence,
                correlationId,
                createdAt,
                null);
    }

    private static ChatCitationSnapshot citation() {
        return new ChatCitationSnapshot(
                UUID.fromString("11111111-1111-4111-8111-111111111111"),
                "Vacation Policy",
                UUID.fromString("22222222-2222-4222-8222-222222222222"),
                "HR > Leave",
                "Employees with five years of tenure receive 31 calendar days.",
                "31 calendar days",
                7,
                new BigDecimal("0.812"),
                AccessLevel.INTERNAL);
    }

    private static ChatRetrievalMetaSnapshot retrievalMeta() {
        return new ChatRetrievalMetaSnapshot(
                "FACTUAL",
                List.of("HYBRID"),
                List.of("HYBRID"),
                List.of(),
                1234L,
                10,
                2,
                true,
                "deepseek/deepseek-v4-flash:free");
    }

    private static List<String> expectedHistoryContents(int fromInclusive, int toExclusive) {
        List<String> contents = new ArrayList<>();
        for (int index = fromInclusive; index < toExclusive; index++) {
            contents.add("question-" + index);
            contents.add("answer-" + index);
        }
        return contents;
    }
}
