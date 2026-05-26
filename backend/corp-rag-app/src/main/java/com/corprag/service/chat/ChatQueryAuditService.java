package com.corprag.service.chat;

import com.corprag.domain.AuditOutcome;
import com.corprag.domain.chat.AssistantMessageStatus;
import com.corprag.domain.chat.ChatRetrievalMetaSnapshot;
import com.corprag.service.audit.AuditEventWriter;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class ChatQueryAuditService {

    public static final String EVENT_ANSWERED = "CHAT_QUERY_ANSWERED";
    public static final String EVENT_REFUSED_GUARD = "CHAT_QUERY_REFUSED_GUARD";
    public static final String EVENT_NO_EVIDENCE = "CHAT_QUERY_NO_EVIDENCE";
    public static final String EVENT_DEGRADED = "CHAT_QUERY_DEGRADED";
    public static final String EVENT_TIMEOUT = "CHAT_QUERY_TIMEOUT";
    public static final String EVENT_AI_UNAVAILABLE = "CHAT_QUERY_AI_UNAVAILABLE";
    public static final String EVENT_RATE_LIMITED = "CHAT_QUERY_RATE_LIMITED";

    private static final String CATEGORY = "CHAT";
    private static final String ENTITY_CONVERSATION = "CHAT_CONVERSATION";
    private static final String ENTITY_USER = "USER";

    private final AuditEventWriter auditEventWriter;

    public ChatQueryAuditService(AuditEventWriter auditEventWriter) {
        this.auditEventWriter = auditEventWriter;
    }

    public void answered(ChatQueryAuditDetails details) {
        write(EVENT_ANSWERED, AuditOutcome.SUCCESS, details.status(AssistantMessageStatus.ANSWERED));
    }

    public void refusedGuard(ChatQueryAuditDetails details) {
        write(EVENT_REFUSED_GUARD, AuditOutcome.FAILURE, details.status(AssistantMessageStatus.REFUSED_GUARD));
    }

    public void noEvidence(ChatQueryAuditDetails details) {
        write(EVENT_NO_EVIDENCE, AuditOutcome.SUCCESS, details.status(AssistantMessageStatus.NO_EVIDENCE));
    }

    public void degraded(ChatQueryAuditDetails details) {
        write(EVENT_DEGRADED, AuditOutcome.FAILURE, details.status(AssistantMessageStatus.DEGRADED));
    }

    public void timeout(ChatQueryAuditDetails details) {
        write(EVENT_TIMEOUT, AuditOutcome.ERROR, details.status(AssistantMessageStatus.TIMEOUT));
    }

    public void aiUnavailable(ChatQueryAuditDetails details) {
        write(EVENT_AI_UNAVAILABLE, AuditOutcome.ERROR, details.status(AssistantMessageStatus.AI_UNAVAILABLE));
    }

    public void rateLimited(UUID userId, Integer retryAfterSeconds, String ipAddress, String userAgent) {
        Map<String, Object> details = new LinkedHashMap<>();
        put(details, "status", "RATE_LIMITED");
        put(details, "retryAfterSeconds", retryAfterSeconds);
        auditEventWriter.writeEvent(
                CATEGORY,
                EVENT_RATE_LIMITED,
                AuditOutcome.FAILURE,
                userId,
                userId,
                ENTITY_USER,
                userId,
                ipAddress,
                userAgent,
                details);
    }

    private void write(String eventType, AuditOutcome outcome, ChatQueryAuditDetails details) {
        auditEventWriter.writeEvent(
                CATEGORY,
                eventType,
                outcome,
                details.userId(),
                details.userId(),
                ENTITY_CONVERSATION,
                details.conversationId(),
                details.ipAddress(),
                details.userAgent(),
                details.toMap());
    }

    private static void put(Map<String, Object> values, String key, Object value) {
        if (value != null) {
            values.put(key, value);
        }
    }

    public record ChatQueryAuditDetails(
            UUID userId,
            UUID conversationId,
            UUID userMessageId,
            UUID assistantMessageId,
            AssistantMessageStatus status,
            ChatRetrievalMetaSnapshot retrievalMeta,
            Integer citationCount,
            String upstreamErrorCode,
            String upstreamErrorClass,
            String ipAddress,
            String userAgent) {

        public ChatQueryAuditDetails status(AssistantMessageStatus newStatus) {
            return new ChatQueryAuditDetails(
                    userId,
                    conversationId,
                    userMessageId,
                    assistantMessageId,
                    newStatus,
                    retrievalMeta,
                    citationCount,
                    upstreamErrorCode,
                    upstreamErrorClass,
                    ipAddress,
                    userAgent);
        }

        Map<String, Object> toMap() {
            Map<String, Object> values = new LinkedHashMap<>();
            put(values, "conversationId", conversationId);
            put(values, "userMessageId", userMessageId);
            put(values, "assistantMessageId", assistantMessageId);
            put(values, "status", status == null ? null : status.name());
            put(values, "citationCount", citationCount);
            put(values, "upstreamErrorCode", upstreamErrorCode);
            put(values, "upstreamErrorClass", upstreamErrorClass);
            if (retrievalMeta != null) {
                put(values, "route", retrievalMeta.route());
                put(values, "retrieversUsed", nullSafeList(retrievalMeta.retrieversUsed()));
                put(values, "degradationWarnings", nullSafeList(retrievalMeta.degradationWarnings()));
                put(values, "latencyMs", retrievalMeta.latencyMs());
                put(values, "chunksConsidered", retrievalMeta.chunksConsidered());
                put(values, "chunksReturned", retrievalMeta.chunksReturned());
                put(values, "rerankerUsed", retrievalMeta.rerankerUsed());
                put(values, "modelId", retrievalMeta.modelId());
            }
            return values;
        }

        private static List<String> nullSafeList(List<String> values) {
            return values == null ? List.of() : values;
        }
    }
}
