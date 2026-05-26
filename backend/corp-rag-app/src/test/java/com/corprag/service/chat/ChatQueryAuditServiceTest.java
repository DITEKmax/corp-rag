package com.corprag.service.chat;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;

import com.corprag.domain.AuditOutcome;
import com.corprag.domain.chat.AssistantMessageStatus;
import com.corprag.domain.chat.ChatRetrievalMetaSnapshot;
import com.corprag.service.audit.AuditEventWriter;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class ChatQueryAuditServiceTest {

    private static final UUID USER_ID = UUID.fromString("00000000-0000-4000-8000-000000000101");
    private static final UUID CONVERSATION_ID = UUID.fromString("00000000-0000-4000-8000-000000000102");
    private static final UUID USER_MESSAGE_ID = UUID.fromString("00000000-0000-4000-8000-000000000103");
    private static final UUID ASSISTANT_MESSAGE_ID = UUID.fromString("00000000-0000-4000-8000-000000000104");

    @Mock
    private AuditEventWriter auditEventWriter;

    private ChatQueryAuditService service;

    @BeforeEach
    void setUp() {
        service = new ChatQueryAuditService(auditEventWriter);
    }

    @Test
    void writesAnsweredAuditWithoutPromptAnswerOrQuoteText() {
        service.answered(details(AssistantMessageStatus.ANSWERED));

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, ?>> detailsCaptor = ArgumentCaptor.forClass(Map.class);
        verify(auditEventWriter).writeEvent(
                eq("CHAT"),
                eq(ChatQueryAuditService.EVENT_ANSWERED),
                eq(AuditOutcome.SUCCESS),
                eq(USER_ID),
                eq(USER_ID),
                eq("CHAT_CONVERSATION"),
                eq(CONVERSATION_ID),
                eq("127.0.0.1"),
                eq("JUnit"),
                detailsCaptor.capture());

        @SuppressWarnings("unchecked")
        Map<String, Object> details = (Map<String, Object>) detailsCaptor.getValue();
        assertThat(details)
                .containsEntry("status", "ANSWERED")
                .containsEntry("conversationId", CONVERSATION_ID)
                .containsEntry("userMessageId", USER_MESSAGE_ID)
                .containsEntry("assistantMessageId", ASSISTANT_MESSAGE_ID)
                .containsEntry("route", "FACTUAL")
                .containsEntry("citationCount", 2);
        assertThat(details.keySet()).doesNotContain("prompt", "message", "answer", "quote", "citations");
    }

    @Test
    void writesDistinctEventsForAllOutcomes() {
        service.refusedGuard(details(null));
        service.noEvidence(details(null));
        service.degraded(details(null));
        service.timeout(details(null));
        service.aiUnavailable(details(null));

        verify(auditEventWriter).writeEvent(
                eq("CHAT"), eq(ChatQueryAuditService.EVENT_REFUSED_GUARD), eq(AuditOutcome.FAILURE),
                eq(USER_ID), eq(USER_ID), eq("CHAT_CONVERSATION"), eq(CONVERSATION_ID), any(), any(), any());
        verify(auditEventWriter).writeEvent(
                eq("CHAT"), eq(ChatQueryAuditService.EVENT_NO_EVIDENCE), eq(AuditOutcome.SUCCESS),
                eq(USER_ID), eq(USER_ID), eq("CHAT_CONVERSATION"), eq(CONVERSATION_ID), any(), any(), any());
        verify(auditEventWriter).writeEvent(
                eq("CHAT"), eq(ChatQueryAuditService.EVENT_DEGRADED), eq(AuditOutcome.FAILURE),
                eq(USER_ID), eq(USER_ID), eq("CHAT_CONVERSATION"), eq(CONVERSATION_ID), any(), any(), any());
        verify(auditEventWriter).writeEvent(
                eq("CHAT"), eq(ChatQueryAuditService.EVENT_TIMEOUT), eq(AuditOutcome.ERROR),
                eq(USER_ID), eq(USER_ID), eq("CHAT_CONVERSATION"), eq(CONVERSATION_ID), any(), any(), any());
        verify(auditEventWriter).writeEvent(
                eq("CHAT"), eq(ChatQueryAuditService.EVENT_AI_UNAVAILABLE), eq(AuditOutcome.ERROR),
                eq(USER_ID), eq(USER_ID), eq("CHAT_CONVERSATION"), eq(CONVERSATION_ID), any(), any(), any());
    }

    @Test
    void writesRateLimitedAuditWithoutChatRows() {
        service.rateLimited(USER_ID, 17, "127.0.0.1", "JUnit");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, ?>> detailsCaptor = ArgumentCaptor.forClass(Map.class);
        verify(auditEventWriter).writeEvent(
                eq("CHAT"),
                eq(ChatQueryAuditService.EVENT_RATE_LIMITED),
                eq(AuditOutcome.FAILURE),
                eq(USER_ID),
                eq(USER_ID),
                eq("USER"),
                eq(USER_ID),
                eq("127.0.0.1"),
                eq("JUnit"),
                detailsCaptor.capture());
        @SuppressWarnings("unchecked")
        Map<String, Object> details = (Map<String, Object>) detailsCaptor.getValue();
        assertThat(details)
                .containsEntry("status", "RATE_LIMITED")
                .containsEntry("retryAfterSeconds", 17);
    }

    private static ChatQueryAuditService.ChatQueryAuditDetails details(AssistantMessageStatus status) {
        return new ChatQueryAuditService.ChatQueryAuditDetails(
                USER_ID,
                CONVERSATION_ID,
                USER_MESSAGE_ID,
                ASSISTANT_MESSAGE_ID,
                status,
                new ChatRetrievalMetaSnapshot(
                        "FACTUAL",
                        List.of("HYBRID"),
                        List.of("HYBRID"),
                        List.of(),
                        1200L,
                        10,
                        2,
                        true,
                        "deepseek/deepseek-v4-flash:free"),
                2,
                null,
                null,
                "127.0.0.1",
                "JUnit");
    }
}
