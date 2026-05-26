package com.corprag.service.chat;

import com.corprag.adapter.ai.PythonQueryClient;
import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.api.v1.model.ChatQueryRequest;
import com.corprag.contracts.api.v1.model.ChatQueryResponse;
import com.corprag.contracts.api.v1.model.HateoasLink;
import com.corprag.contracts.ai.v1.model.QueryResponse;
import com.corprag.contracts.ai.v1.model.RetrievalOptions;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.AccessLevel;
import com.corprag.domain.ResolvedAccessFilter;
import com.corprag.domain.chat.AssistantMessageStatus;
import com.corprag.domain.chat.ChatCitationSnapshot;
import com.corprag.domain.chat.ChatMessage;
import com.corprag.domain.chat.ChatMessageRole;
import com.corprag.domain.chat.ChatRetrievalMetaSnapshot;
import com.corprag.repository.ChatConversationRepository;
import com.corprag.repository.ChatMessageRepository;
import com.corprag.service.access.AccessFilterResolver;
import com.corprag.service.auth.RequestMetadata;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.stereotype.Service;

@Service
public class ChatQueryService {

    private final ChatConversationRepository conversationRepository;
    private final ChatMessageRepository messageRepository;
    private final AccessFilterResolver accessFilterResolver;
    private final PythonQueryClient pythonQueryClient;
    private final ChatHistoryAssembler historyAssembler;
    private final ChatTitleService titleService;
    private final ChatMessageMapper messageMapper;
    private final ChatQueryAuditService auditService;
    private final Clock clock;

    @Autowired
    public ChatQueryService(
            ChatConversationRepository conversationRepository,
            ChatMessageRepository messageRepository,
            AccessFilterResolver accessFilterResolver,
            PythonQueryClient pythonQueryClient,
            ChatHistoryAssembler historyAssembler,
            ChatTitleService titleService,
            ChatMessageMapper messageMapper,
            ChatQueryAuditService auditService) {
        this(
                conversationRepository,
                messageRepository,
                accessFilterResolver,
                pythonQueryClient,
                historyAssembler,
                titleService,
                messageMapper,
                auditService,
                Clock.systemUTC());
    }

    ChatQueryService(
            ChatConversationRepository conversationRepository,
            ChatMessageRepository messageRepository,
            AccessFilterResolver accessFilterResolver,
            PythonQueryClient pythonQueryClient,
            ChatHistoryAssembler historyAssembler,
            ChatTitleService titleService,
            ChatMessageMapper messageMapper,
            ChatQueryAuditService auditService,
            Clock clock) {
        this.conversationRepository = conversationRepository;
        this.messageRepository = messageRepository;
        this.accessFilterResolver = accessFilterResolver;
        this.pythonQueryClient = pythonQueryClient;
        this.historyAssembler = historyAssembler;
        this.titleService = titleService;
        this.messageMapper = messageMapper;
        this.auditService = auditService;
        this.clock = clock;
    }

    public ChatQueryResponse query(
            UUID ownerUserId,
            UUID correlationId,
            ChatQueryRequest request,
            RequestMetadata metadata) {
        ValidatedQuery validated = validate(request);
        conversationRepository.findActiveByOwner(validated.conversationId(), ownerUserId)
                .orElseThrow(ChatQueryService::notFound);

        ResolvedAccessFilter accessFilter = accessFilterResolver.resolve(ownerUserId);
        List<ChatMessage> history = historyAssembler.answeredPairHistory(ownerUserId, validated.conversationId());
        PythonQueryClient.PythonQueryCommand command = new PythonQueryClient.PythonQueryCommand(
                ownerUserId,
                correlationId,
                validated.conversationId(),
                validated.message(),
                accessFilter,
                history,
                new RetrievalOptions());

        FinalOutcome outcome = queryPythonWithInternalRetry(command);
        PersistedPair pair = persistPair(ownerUserId, correlationId, validated, outcome);
        audit(outcome, ownerUserId, validated.conversationId(), pair, metadata);
        throwProblemIfNeeded(outcome, validated.conversationId(), pair.assistantMessageId());
        return toResponse(validated.conversationId(), pair.assistantMessageId(), outcome);
    }

    private FinalOutcome queryPythonWithInternalRetry(PythonQueryClient.PythonQueryCommand command) {
        FinalOutcome first = mapPythonOutcome(pythonQueryClient.query(command));
        if (first.status() != AssistantMessageStatus.DEGRADED) {
            return first;
        }

        FinalOutcome second = mapPythonOutcome(pythonQueryClient.query(command));
        if (second.status() == AssistantMessageStatus.DEGRADED && second.retrievalMeta() == null) {
            return second.withRetrievalMeta(first.retrievalMeta());
        }
        return second;
    }

    private PersistedPair persistPair(
            UUID ownerUserId,
            UUID correlationId,
            ValidatedQuery query,
            FinalOutcome outcome) {
        Instant userCreatedAt = clock.instant();
        Instant assistantCreatedAt = userCreatedAt.plusMillis(1);
        UUID userMessageId = UUID.randomUUID();
        UUID assistantMessageId = outcome.assistantMessageId() == null
                ? UUID.randomUUID()
                : outcome.assistantMessageId();

        ChatMessage userMessage = new ChatMessage(
                userMessageId,
                query.conversationId(),
                ChatMessageRole.USER,
                null,
                query.message(),
                null,
                null,
                null,
                correlationId,
                userCreatedAt,
                null);
        ChatMessage assistantMessage = new ChatMessage(
                assistantMessageId,
                query.conversationId(),
                ChatMessageRole.ASSISTANT,
                outcome.status(),
                outcome.answerContent(),
                outcome.citationsForStorage(),
                outcome.retrievalMeta(),
                outcome.confidenceForStorage(),
                correlationId,
                assistantCreatedAt,
                null);

        try {
            titleService.deriveTitleFromFirstMessageIfNeeded(
                    ownerUserId,
                    query.conversationId(),
                    query.message(),
                    userCreatedAt);
            messageRepository.appendPair(ownerUserId, userMessage, assistantMessage, assistantCreatedAt);
        } catch (EmptyResultDataAccessException exception) {
            throw notFound();
        }
        return new PersistedPair(userMessageId, assistantMessageId);
    }

    private FinalOutcome mapPythonOutcome(PythonQueryClient.PythonQueryOutcome outcome) {
        return switch (outcome) {
            case PythonQueryClient.PythonQueryOutcome.Success success -> mapSuccess(success.response());
            case PythonQueryClient.PythonQueryOutcome.GuardRejected guardRejected -> FinalOutcome.problem(
                    AssistantMessageStatus.REFUSED_GUARD,
                    guardRejected.problem() == null ? null : guardRejected.problem().getErrorCode(),
                    "GUARD_REJECTED",
                    guardRejected.problem() == null ? "Query blocked by guard" : guardRejected.problem().getDetail());
            case PythonQueryClient.PythonQueryOutcome.Degraded degraded -> FinalOutcome.problem(
                    AssistantMessageStatus.DEGRADED,
                    degraded.problem() == null ? null : degraded.problem().getErrorCode(),
                    "MISSING_CITATIONS",
                    degraded.problem() == null ? "Answer could not be cited correctly" : degraded.problem().getDetail());
            case PythonQueryClient.PythonQueryOutcome.Timeout timeout -> FinalOutcome.problem(
                    AssistantMessageStatus.TIMEOUT,
                    "AI_QUERY_TIMEOUT",
                    "TIMEOUT",
                    timeout.detail());
            case PythonQueryClient.PythonQueryOutcome.Unavailable unavailable -> FinalOutcome.problem(
                    AssistantMessageStatus.AI_UNAVAILABLE,
                    unavailable.problem() == null ? null : unavailable.problem().getErrorCode(),
                    unavailable.upstreamErrorClass(),
                    unavailable.detail());
            case PythonQueryClient.PythonQueryOutcome.Problem problem -> FinalOutcome.problem(
                    AssistantMessageStatus.AI_UNAVAILABLE,
                    problem.problem() == null ? null : problem.problem().getErrorCode(),
                    "HTTP_" + problem.status(),
                    problem.problem() == null ? "AI service returned an error" : problem.problem().getDetail());
        };
    }

    private FinalOutcome mapSuccess(QueryResponse response) {
        if (response == null) {
            return FinalOutcome.problem(
                    AssistantMessageStatus.AI_UNAVAILABLE,
                    "EMPTY_AI_RESPONSE",
                    "EMPTY_RESPONSE",
                    "AI service returned an empty response");
        }

        ChatRetrievalMetaSnapshot retrievalMeta = snapshot(response.getRetrievalMeta());
        if (Boolean.TRUE.equals(response.getAnswered())) {
            if (!hasValidAnswerAndCitations(response)) {
                return FinalOutcome.degraded(
                        response.getMessageId(),
                        retrievalMeta,
                        "MISSING_CITATIONS",
                        "Answered response did not include valid displayable citations");
            }
            return FinalOutcome.answered(
                    response.getMessageId(),
                    response.getAnswer(),
                    citations(response.getCitations()),
                    retrievalMeta,
                    toBigDecimal(response.getConfidence()),
                    response.getGuardVerdict());
        }

        return FinalOutcome.noEvidence(response.getMessageId(), retrievalMeta, response.getGuardVerdict());
    }

    private static boolean hasValidAnswerAndCitations(QueryResponse response) {
        if (response.getAnswer() == null || response.getAnswer().isBlank()) {
            return false;
        }
        List<com.corprag.contracts.ai.v1.model.Citation> citations = response.getCitations();
        return citations != null
                && !citations.isEmpty()
                && citations.stream().allMatch(ChatQueryService::isValidCitation);
    }

    private static boolean isValidCitation(com.corprag.contracts.ai.v1.model.Citation citation) {
        return citation.getDocumentId() != null
                && citation.getChunkId() != null
                && citation.getDocumentTitle() != null
                && !citation.getDocumentTitle().isBlank()
                && citation.getSectionPath() != null
                && !citation.getSectionPath().isBlank()
                && citation.getQuote() != null
                && !citation.getQuote().isBlank()
                && citation.getScore() != null
                && citation.getAccessLevel() != null;
    }

    private ChatQueryResponse toResponse(UUID conversationId, UUID assistantMessageId, FinalOutcome outcome) {
        return new ChatQueryResponse()
                .conversationId(conversationId)
                .messageId(assistantMessageId)
                .answered(outcome.status() == AssistantMessageStatus.ANSWERED)
                .status(com.corprag.contracts.api.v1.model.AssistantMessageStatus.fromValue(outcome.status().name()))
                .answer(outcome.answerContent())
                .citations(messageMapper.toContractCitations(outcome.citationsForStorage()))
                .confidence(outcome.confidenceForStorage() == null ? null : outcome.confidenceForStorage().floatValue())
                .guardVerdict(toContractGuardVerdict(outcome.guardVerdict()))
                .retrievalMeta(messageMapper.toContractRetrievalMeta(outcome.retrievalMeta()))
                .links(Map.of(
                        "self", link("/api/v1/chat/query"),
                        "conversation", link("/api/v1/chat/conversations/" + conversationId),
                        "messages", link("/api/v1/chat/conversations/" + conversationId + "/messages")));
    }

    private void audit(
            FinalOutcome outcome,
            UUID ownerUserId,
            UUID conversationId,
            PersistedPair pair,
            RequestMetadata metadata) {
        ChatQueryAuditService.ChatQueryAuditDetails details = new ChatQueryAuditService.ChatQueryAuditDetails(
                ownerUserId,
                conversationId,
                pair.userMessageId(),
                pair.assistantMessageId(),
                outcome.status(),
                outcome.retrievalMeta(),
                outcome.citationsForStorage() == null ? null : outcome.citationsForStorage().size(),
                outcome.upstreamErrorCode(),
                outcome.upstreamErrorClass(),
                metadata == null ? null : metadata.ipAddress(),
                metadata == null ? null : metadata.userAgent());
        switch (outcome.status()) {
            case ANSWERED -> auditService.answered(details);
            case REFUSED_GUARD -> auditService.refusedGuard(details);
            case NO_EVIDENCE -> auditService.noEvidence(details);
            case DEGRADED -> auditService.degraded(details);
            case TIMEOUT -> auditService.timeout(details);
            case AI_UNAVAILABLE -> auditService.aiUnavailable(details);
        }
    }

    private static void throwProblemIfNeeded(
            FinalOutcome outcome,
            UUID conversationId,
            UUID assistantMessageId) {
        if (outcome.status() == AssistantMessageStatus.REFUSED_GUARD) {
            throw new ApiProblemException(
                    ErrorCodes.QUERY_BLOCKED_BY_GUARD,
                    nullSafe(outcome.problemDetail(), "Query blocked by guard"),
                    problemDetails(conversationId, assistantMessageId, outcome));
        }
        if (outcome.status() == AssistantMessageStatus.TIMEOUT) {
            throw new ApiProblemException(
                    ErrorCodes.AI_SERVICE_UNAVAILABLE,
                    nullSafe(outcome.problemDetail(), "AI service timed out"),
                    problemDetails(conversationId, assistantMessageId, outcome));
        }
        if (outcome.status() == AssistantMessageStatus.AI_UNAVAILABLE) {
            throw new ApiProblemException(
                    ErrorCodes.AI_SERVICE_UNAVAILABLE,
                    nullSafe(outcome.problemDetail(), "AI service unavailable"),
                    problemDetails(conversationId, assistantMessageId, outcome));
        }
    }

    private static Map<String, Object> problemDetails(
            UUID conversationId,
            UUID assistantMessageId,
            FinalOutcome outcome) {
        Map<String, Object> details = new LinkedHashMap<>();
        put(details, "conversationId", conversationId);
        put(details, "messageId", assistantMessageId);
        put(details, "status", outcome.status().name());
        put(details, "upstreamErrorCode", outcome.upstreamErrorCode());
        put(details, "upstreamErrorClass", outcome.upstreamErrorClass());
        return details;
    }

    private static ValidatedQuery validate(ChatQueryRequest request) {
        if (request == null) {
            throw validation("Chat query request is required");
        }
        if (request.getConversationId() == null) {
            throw validation("conversationId is required");
        }
        String message = request.getMessage();
        if (message == null || message.isBlank() || message.length() > 2000) {
            throw validation("Message is invalid");
        }
        return new ValidatedQuery(request.getConversationId(), message.trim());
    }

    private static ApiProblemException validation(String detail) {
        return new ApiProblemException(ErrorCodes.VALIDATION_FAILED, detail);
    }

    private static ApiProblemException notFound() {
        return new ApiProblemException(ErrorCodes.CONVERSATION_NOT_FOUND, "Conversation not found");
    }

    private static List<ChatCitationSnapshot> citations(
            List<com.corprag.contracts.ai.v1.model.Citation> citations) {
        return citations.stream()
                .map(ChatQueryService::citation)
                .toList();
    }

    private static ChatCitationSnapshot citation(com.corprag.contracts.ai.v1.model.Citation citation) {
        return new ChatCitationSnapshot(
                citation.getDocumentId(),
                citation.getDocumentTitle(),
                citation.getChunkId(),
                citation.getSectionPath(),
                citation.getQuote(),
                citation.getSnippet(),
                citation.getPageNumber(),
                toBigDecimal(citation.getScore()),
                AccessLevel.valueOf(citation.getAccessLevel().getValue()));
    }

    private static ChatRetrievalMetaSnapshot snapshot(com.corprag.contracts.ai.v1.model.RetrievalMeta meta) {
        if (meta == null) {
            return null;
        }
        return new ChatRetrievalMetaSnapshot(
                meta.getRoute() == null ? null : meta.getRoute().getValue(),
                retrieverValues(meta.getRetrieversAttempted()),
                retrieverValues(meta.getRetrieversUsed()),
                meta.getDegradationWarnings() == null ? List.of() : meta.getDegradationWarnings(),
                meta.getLatencyMs(),
                meta.getChunksConsidered(),
                meta.getChunksReturned(),
                meta.getRerankerUsed(),
                meta.getModelId());
    }

    private static List<String> retrieverValues(List<com.corprag.contracts.ai.v1.model.RetrieverType> retrievers) {
        if (retrievers == null) {
            return List.of();
        }
        return retrievers.stream()
                .filter(Objects::nonNull)
                .map(com.corprag.contracts.ai.v1.model.RetrieverType::getValue)
                .toList();
    }

    private static com.corprag.contracts.api.v1.model.GuardVerdict toContractGuardVerdict(
            com.corprag.contracts.ai.v1.model.GuardVerdict guardVerdict) {
        if (guardVerdict == null) {
            return null;
        }
        return new com.corprag.contracts.api.v1.model.GuardVerdict()
                .safe(guardVerdict.getSafe())
                .reason(guardVerdict.getReason())
                .tier(guardVerdict.getTier() == null
                        ? null
                        : com.corprag.contracts.api.v1.model.GuardVerdict.TierEnum.fromValue(
                                guardVerdict.getTier().getValue()))
                .confidence(guardVerdict.getConfidence());
    }

    private static BigDecimal toBigDecimal(Float value) {
        return value == null ? null : BigDecimal.valueOf(value.doubleValue());
    }

    private static HateoasLink link(String href) {
        return new HateoasLink().href(href);
    }

    private static void put(Map<String, Object> values, String key, Object value) {
        if (value != null) {
            values.put(key, value);
        }
    }

    private static String nullSafe(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    private record ValidatedQuery(UUID conversationId, String message) {
    }

    private record PersistedPair(UUID userMessageId, UUID assistantMessageId) {
    }

    private record FinalOutcome(
            AssistantMessageStatus status,
            UUID assistantMessageId,
            String answer,
            List<ChatCitationSnapshot> citations,
            ChatRetrievalMetaSnapshot retrievalMeta,
            BigDecimal confidence,
            com.corprag.contracts.ai.v1.model.GuardVerdict guardVerdict,
            String upstreamErrorCode,
            String upstreamErrorClass,
            String problemDetail) {

        static FinalOutcome answered(
                UUID assistantMessageId,
                String answer,
                List<ChatCitationSnapshot> citations,
                ChatRetrievalMetaSnapshot retrievalMeta,
                BigDecimal confidence,
                com.corprag.contracts.ai.v1.model.GuardVerdict guardVerdict) {
            return new FinalOutcome(
                    AssistantMessageStatus.ANSWERED,
                    assistantMessageId,
                    answer,
                    citations,
                    retrievalMeta,
                    confidence,
                    guardVerdict,
                    null,
                    null,
                    null);
        }

        static FinalOutcome noEvidence(
                UUID assistantMessageId,
                ChatRetrievalMetaSnapshot retrievalMeta,
                com.corprag.contracts.ai.v1.model.GuardVerdict guardVerdict) {
            return new FinalOutcome(
                    AssistantMessageStatus.NO_EVIDENCE,
                    assistantMessageId,
                    null,
                    null,
                    retrievalMeta,
                    null,
                    guardVerdict,
                    null,
                    null,
                    null);
        }

        static FinalOutcome degraded(
                UUID assistantMessageId,
                ChatRetrievalMetaSnapshot retrievalMeta,
                String upstreamErrorCode,
                String problemDetail) {
            return new FinalOutcome(
                    AssistantMessageStatus.DEGRADED,
                    assistantMessageId,
                    null,
                    null,
                    retrievalMeta,
                    null,
                    null,
                    upstreamErrorCode,
                    "MISSING_CITATIONS",
                    problemDetail);
        }

        static FinalOutcome problem(
                AssistantMessageStatus status,
                String upstreamErrorCode,
                String upstreamErrorClass,
                String problemDetail) {
            return new FinalOutcome(
                    status,
                    null,
                    null,
                    null,
                    null,
                    null,
                    null,
                    upstreamErrorCode,
                    upstreamErrorClass,
                    problemDetail);
        }

        FinalOutcome withRetrievalMeta(ChatRetrievalMetaSnapshot fallbackRetrievalMeta) {
            if (retrievalMeta != null || fallbackRetrievalMeta == null) {
                return this;
            }
            return new FinalOutcome(
                    status,
                    assistantMessageId,
                    answer,
                    citations,
                    fallbackRetrievalMeta,
                    confidence,
                    guardVerdict,
                    upstreamErrorCode,
                    upstreamErrorClass,
                    problemDetail);
        }

        String answerContent() {
            return status == AssistantMessageStatus.ANSWERED ? answer : null;
        }

        List<ChatCitationSnapshot> citationsForStorage() {
            return status == AssistantMessageStatus.ANSWERED ? citations : null;
        }

        BigDecimal confidenceForStorage() {
            return status == AssistantMessageStatus.ANSWERED ? confidence : null;
        }
    }
}
