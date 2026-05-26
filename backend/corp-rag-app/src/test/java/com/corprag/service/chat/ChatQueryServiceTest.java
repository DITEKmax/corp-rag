package com.corprag.service.chat;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.corprag.adapter.ai.PythonQueryClient;
import com.corprag.adapter.rest.ApiProblemException;
import com.corprag.contracts.ai.v1.model.Citation;
import com.corprag.contracts.ai.v1.model.ProblemDetail;
import com.corprag.contracts.ai.v1.model.QueryResponse;
import com.corprag.contracts.ai.v1.model.RetrievalMeta;
import com.corprag.contracts.ai.v1.model.RetrieverType;
import com.corprag.contracts.api.v1.model.AssistantMessageStatus;
import com.corprag.contracts.api.v1.model.ChatQueryRequest;
import com.corprag.contracts.api.v1.model.ChatQueryResponse;
import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.domain.AccessLevel;
import com.corprag.domain.DocType;
import com.corprag.domain.ResolvedAccessFilter;
import com.corprag.domain.chat.ChatConversation;
import com.corprag.domain.chat.ChatMessage;
import com.corprag.domain.chat.ChatMessageRole;
import com.corprag.repository.ChatConversationRepository;
import com.corprag.repository.ChatMessageRepository;
import com.corprag.service.access.AccessFilterResolver;
import com.corprag.service.auth.RequestMetadata;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class ChatQueryServiceTest {

    private static final UUID OWNER_ID = UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final UUID CONVERSATION_ID = UUID.fromString("c1234567-e89b-12d3-a456-426614174000");
    private static final UUID CORRELATION_ID = UUID.fromString("550e8400-e29b-41d4-a716-446655440000");
    private static final UUID PYTHON_MESSAGE_ID = UUID.fromString("22222222-2222-4222-8222-222222222222");
    private static final UUID DOCUMENT_ID = UUID.fromString("d8f3a1c2-e89b-42d3-a456-426614174000");
    private static final UUID CHUNK_ID = UUID.fromString("11111111-1111-4111-8111-111111111042");
    private static final Instant NOW = Instant.parse("2026-05-21T10:00:00Z");
    private static final ResolvedAccessFilter FILTER = new ResolvedAccessFilter(
            List.of(AccessLevel.PUBLIC, AccessLevel.INTERNAL),
            List.of("HR"),
            List.of(DocType.POLICY));
    private static final RequestMetadata METADATA = new RequestMetadata("127.0.0.1", "JUnit");

    private final ChatConversationRepository conversationRepository = mock(ChatConversationRepository.class);
    private final ChatMessageRepository messageRepository = mock(ChatMessageRepository.class);
    private final AccessFilterResolver accessFilterResolver = mock(AccessFilterResolver.class);
    private final PythonQueryClient pythonQueryClient = mock(PythonQueryClient.class);
    private final ChatHistoryAssembler historyAssembler = mock(ChatHistoryAssembler.class);
    private final ChatTitleService titleService = mock(ChatTitleService.class);
    private final ChatQueryAuditService auditService = mock(ChatQueryAuditService.class);
    private final ChatQueryService service = new ChatQueryService(
            conversationRepository,
            messageRepository,
            accessFilterResolver,
            pythonQueryClient,
            historyAssembler,
            titleService,
            new ChatMessageMapper(),
            auditService,
            Clock.fixed(NOW, ZoneOffset.UTC));

    @Test
    void answeredQuerySendsAnsweredPairHistoryPersistsPairAndAudits() {
        givenActiveConversation();
        List<ChatMessage> history = List.of(historyUser(), historyAssistant());
        when(historyAssembler.answeredPairHistory(OWNER_ID, CONVERSATION_ID)).thenReturn(history);
        when(pythonQueryClient.query(any())).thenReturn(new PythonQueryClient.PythonQueryOutcome.Success(answeredResponse()));

        ChatQueryResponse response = service.query(OWNER_ID, CORRELATION_ID, request(), METADATA);

        assertThat(response.getStatus()).isEqualTo(AssistantMessageStatus.ANSWERED);
        assertThat(response.getAnswered()).isTrue();
        assertThat(response.getMessageId()).isEqualTo(PYTHON_MESSAGE_ID);
        assertThat(response.getCitations()).hasSize(1);
        assertThat(response.getRetrievalMeta().getRoute().getValue()).isEqualTo("FACTUAL");

        ArgumentCaptor<PythonQueryClient.PythonQueryCommand> commandCaptor =
                ArgumentCaptor.forClass(PythonQueryClient.PythonQueryCommand.class);
        verify(pythonQueryClient).query(commandCaptor.capture());
        assertThat(commandCaptor.getValue().conversationId()).isEqualTo(CONVERSATION_ID);
        assertThat(commandCaptor.getValue().correlationId()).isEqualTo(CORRELATION_ID);
        assertThat(commandCaptor.getValue().conversationHistory()).isEqualTo(history);
        assertThat(commandCaptor.getValue().accessFilter()).isEqualTo(FILTER);

        CapturedPair pair = capturePersistedPair();
        assertThat(pair.user().role()).isEqualTo(ChatMessageRole.USER);
        assertThat(pair.user().correlationId()).isEqualTo(CORRELATION_ID);
        assertThat(pair.assistant().id()).isEqualTo(PYTHON_MESSAGE_ID);
        assertThat(pair.assistant().status()).isEqualTo(com.corprag.domain.chat.AssistantMessageStatus.ANSWERED);
        assertThat(pair.assistant().content()).isEqualTo("Answer [1].");
        assertThat(pair.assistant().citations()).hasSize(1);
        assertThat(pair.assistant().retrievalMeta().route()).isEqualTo("FACTUAL");
        assertThat(pair.updatedAt()).isEqualTo(NOW.plusMillis(1));
        verify(titleService).deriveTitleFromFirstMessageIfNeeded(OWNER_ID, CONVERSATION_ID, "Question?", NOW);
        verify(auditService).answered(any());
    }

    @Test
    void noEvidencePersistsStatusWithoutAnswerTextOrCitations() {
        givenActiveConversation();
        when(pythonQueryClient.query(any())).thenReturn(new PythonQueryClient.PythonQueryOutcome.Success(noEvidenceResponse()));

        ChatQueryResponse response = service.query(OWNER_ID, CORRELATION_ID, request(), METADATA);

        assertThat(response.getStatus()).isEqualTo(AssistantMessageStatus.NO_EVIDENCE);
        assertThat(response.getAnswered()).isFalse();
        assertThat(response.getAnswer()).isNull();
        assertThat(response.getCitations()).isNull();

        ChatMessage assistant = capturePersistedPair().assistant();
        assertThat(assistant.status()).isEqualTo(com.corprag.domain.chat.AssistantMessageStatus.NO_EVIDENCE);
        assertThat(assistant.content()).isNull();
        assertThat(assistant.citations()).isNull();
        assertThat(assistant.retrievalMeta()).isNotNull();
        verify(auditService).noEvidence(any());
    }

    @Test
    void degradedAutoRetryCanRecoverAndStillPersistsOnePair() {
        givenActiveConversation();
        when(pythonQueryClient.query(any()))
                .thenReturn(new PythonQueryClient.PythonQueryOutcome.Degraded(problem("MISSING_CITATIONS")))
                .thenReturn(new PythonQueryClient.PythonQueryOutcome.Success(answeredResponse()));

        ChatQueryResponse response = service.query(OWNER_ID, CORRELATION_ID, request(), METADATA);

        assertThat(response.getStatus()).isEqualTo(AssistantMessageStatus.ANSWERED);
        verify(pythonQueryClient, times(2)).query(any());
        verify(messageRepository).appendPair(eq(OWNER_ID), any(), any(), any());
        assertThat(capturePersistedPair().assistant().status())
                .isEqualTo(com.corprag.domain.chat.AssistantMessageStatus.ANSWERED);
    }

    @Test
    void degradedAfterAutoRetryPersistsCompactDegradedOutcome() {
        givenActiveConversation();
        when(pythonQueryClient.query(any()))
                .thenReturn(new PythonQueryClient.PythonQueryOutcome.Degraded(problem("MISSING_CITATIONS")))
                .thenReturn(new PythonQueryClient.PythonQueryOutcome.Degraded(problem("MISSING_CITATIONS")));

        ChatQueryResponse response = service.query(OWNER_ID, CORRELATION_ID, request(), METADATA);

        assertThat(response.getStatus()).isEqualTo(AssistantMessageStatus.DEGRADED);
        assertThat(response.getAnswered()).isFalse();
        assertThat(response.getAnswer()).isNull();
        assertThat(response.getCitations()).isNull();

        ChatMessage assistant = capturePersistedPair().assistant();
        assertThat(assistant.status()).isEqualTo(com.corprag.domain.chat.AssistantMessageStatus.DEGRADED);
        assertThat(assistant.content()).isNull();
        assertThat(assistant.citations()).isNull();
        verify(auditService).degraded(any());
    }

    @Test
    void guardRejectionPersistsRefusedRowThenThrowsProblemDetails() {
        givenActiveConversation();
        when(pythonQueryClient.query(any()))
                .thenReturn(new PythonQueryClient.PythonQueryOutcome.GuardRejected(problem("QUERY_BLOCKED_BY_GUARD")));

        assertThatThrownBy(() -> service.query(OWNER_ID, CORRELATION_ID, request(), METADATA))
                .isInstanceOf(ApiProblemException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCodes.QUERY_BLOCKED_BY_GUARD);

        assertThat(capturePersistedPair().assistant().status())
                .isEqualTo(com.corprag.domain.chat.AssistantMessageStatus.REFUSED_GUARD);
        verify(auditService).refusedGuard(any());
    }

    @Test
    void timeoutPersistsTimeoutRowThenThrowsServiceUnavailable() {
        givenActiveConversation();
        when(pythonQueryClient.query(any()))
                .thenReturn(new PythonQueryClient.PythonQueryOutcome.Timeout("timed out"));

        assertThatThrownBy(() -> service.query(OWNER_ID, CORRELATION_ID, request(), METADATA))
                .isInstanceOf(ApiProblemException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCodes.AI_SERVICE_UNAVAILABLE);

        assertThat(capturePersistedPair().assistant().status())
                .isEqualTo(com.corprag.domain.chat.AssistantMessageStatus.TIMEOUT);
        verify(auditService).timeout(any());
    }

    @Test
    void missingConversationShortCircuitsBeforeAccessFilterOrPython() {
        when(conversationRepository.findActiveByOwner(CONVERSATION_ID, OWNER_ID)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.query(OWNER_ID, CORRELATION_ID, request(), METADATA))
                .isInstanceOf(ApiProblemException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCodes.CONVERSATION_NOT_FOUND);

        verifyNoInteractions(accessFilterResolver, pythonQueryClient, messageRepository);
    }

    private void givenActiveConversation() {
        when(conversationRepository.findActiveByOwner(CONVERSATION_ID, OWNER_ID))
                .thenReturn(Optional.of(new ChatConversation(
                        CONVERSATION_ID,
                        OWNER_ID,
                        "Question?",
                        NOW.minusSeconds(60),
                        NOW.minusSeconds(60),
                        null)));
        when(accessFilterResolver.resolve(OWNER_ID)).thenReturn(FILTER);
        when(historyAssembler.answeredPairHistory(OWNER_ID, CONVERSATION_ID)).thenReturn(List.of());
    }

    private CapturedPair capturePersistedPair() {
        ArgumentCaptor<ChatMessage> userCaptor = ArgumentCaptor.forClass(ChatMessage.class);
        ArgumentCaptor<ChatMessage> assistantCaptor = ArgumentCaptor.forClass(ChatMessage.class);
        ArgumentCaptor<Instant> updatedAtCaptor = ArgumentCaptor.forClass(Instant.class);
        verify(messageRepository).appendPair(eq(OWNER_ID), userCaptor.capture(), assistantCaptor.capture(), updatedAtCaptor.capture());
        return new CapturedPair(userCaptor.getValue(), assistantCaptor.getValue(), updatedAtCaptor.getValue());
    }

    private static ChatQueryRequest request() {
        return new ChatQueryRequest()
                .conversationId(CONVERSATION_ID)
                .message("Question?");
    }

    private static QueryResponse answeredResponse() {
        return new QueryResponse()
                .answered(true)
                .answer("Answer [1].")
                .citations(List.of(citation()))
                .confidence(0.88f)
                .conversationId(CONVERSATION_ID)
                .messageId(PYTHON_MESSAGE_ID)
                .retrievalMeta(retrievalMeta());
    }

    private static QueryResponse noEvidenceResponse() {
        return new QueryResponse()
                .answered(false)
                .answer("No evidence")
                .citations(List.of())
                .confidence(0.0f)
                .conversationId(CONVERSATION_ID)
                .messageId(PYTHON_MESSAGE_ID)
                .retrievalMeta(retrievalMeta());
    }

    private static Citation citation() {
        return new Citation()
                .documentId(DOCUMENT_ID)
                .documentTitle("HR policy")
                .chunkId(CHUNK_ID)
                .sectionPath("HR > Leave")
                .quote("Employees receive annual leave.")
                .snippet("Employees receive annual leave.")
                .pageNumber(4)
                .score(0.92f)
                .accessLevel(com.corprag.contracts.ai.v1.model.AccessLevel.INTERNAL);
    }

    private static RetrievalMeta retrievalMeta() {
        return new RetrievalMeta()
                .route(com.corprag.contracts.ai.v1.model.QueryRoute.FACTUAL)
                .retrieversAttempted(List.of(RetrieverType.HYBRID))
                .retrieversUsed(List.of(RetrieverType.HYBRID))
                .degradationWarnings(List.of())
                .latencyMs(100L)
                .chunksConsidered(3)
                .chunksReturned(1)
                .rerankerUsed(true)
                .modelId("deepseek/deepseek-v4-flash:free");
    }

    private static ProblemDetail problem(String errorCode) {
        return new ProblemDetail()
                .errorCode(errorCode)
                .detail(errorCode.toLowerCase());
    }

    private static ChatMessage historyUser() {
        return new ChatMessage(
                UUID.randomUUID(),
                CONVERSATION_ID,
                ChatMessageRole.USER,
                null,
                "Previous question",
                null,
                null,
                null,
                UUID.randomUUID(),
                NOW.minusSeconds(30),
                null);
    }

    private static ChatMessage historyAssistant() {
        return new ChatMessage(
                UUID.randomUUID(),
                CONVERSATION_ID,
                ChatMessageRole.ASSISTANT,
                com.corprag.domain.chat.AssistantMessageStatus.ANSWERED,
                "Previous answer",
                null,
                null,
                null,
                UUID.randomUUID(),
                NOW.minusSeconds(29),
                null);
    }

    private record CapturedPair(ChatMessage user, ChatMessage assistant, Instant updatedAt) {
    }
}
