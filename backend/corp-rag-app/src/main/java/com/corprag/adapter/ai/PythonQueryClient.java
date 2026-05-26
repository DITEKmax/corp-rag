package com.corprag.adapter.ai;

import com.corprag.adapter.rest.QueryAccessFilterMapper;
import com.corprag.contracts.ai.v1.model.ConversationMessage;
import com.corprag.contracts.ai.v1.model.ConversationRole;
import com.corprag.contracts.ai.v1.model.ProblemDetail;
import com.corprag.contracts.ai.v1.model.QueryRequest;
import com.corprag.contracts.ai.v1.model.QueryResponse;
import com.corprag.contracts.ai.v1.model.RetrievalOptions;
import com.corprag.domain.ResolvedAccessFilter;
import com.corprag.domain.chat.ChatMessage;
import com.corprag.domain.chat.ChatMessageRole;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.SocketTimeoutException;
import java.net.URI;
import java.net.http.HttpTimeoutException;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

@Component
public class PythonQueryClient {

    private static final String QUERY_PATH = "/v1/query";

    private final RestClient restClient;
    private final QueryAccessFilterMapper accessFilterMapper;
    private final ObjectMapper objectMapper;

    public PythonQueryClient(
            @Qualifier("pythonAiRestClient") RestClient restClient,
            QueryAccessFilterMapper accessFilterMapper,
            ObjectMapper objectMapper) {
        this.restClient = restClient;
        this.accessFilterMapper = accessFilterMapper;
        this.objectMapper = objectMapper;
    }

    public PythonQueryOutcome query(PythonQueryCommand command) {
        QueryRequest request = toContract(command);
        try {
            ResponseEntity<QueryResponse> response = restClient.post()
                    .uri(QUERY_PATH)
                    .body(request)
                    .retrieve()
                    .toEntity(QueryResponse.class);
            return new PythonQueryOutcome.Success(response.getBody());
        } catch (RestClientResponseException exception) {
            return mapProblem(exception);
        } catch (ResourceAccessException exception) {
            if (hasTimeoutCause(exception)) {
                return new PythonQueryOutcome.Timeout("Python query timed out before returning a response");
            }
            return new PythonQueryOutcome.Unavailable(null, exception.getClass().getSimpleName(), exception.getMessage());
        } catch (RestClientException exception) {
            return new PythonQueryOutcome.Unavailable(null, exception.getClass().getSimpleName(), exception.getMessage());
        }
    }

    QueryRequest toContract(PythonQueryCommand command) {
        Objects.requireNonNull(command.userId(), "userId is required");
        Objects.requireNonNull(command.correlationId(), "correlationId is required");
        Objects.requireNonNull(command.conversationId(), "conversationId is required");
        Objects.requireNonNull(command.message(), "message is required");
        Objects.requireNonNull(command.accessFilter(), "accessFilter is required");

        return new QueryRequest()
                .userId(command.userId())
                .correlationId(command.correlationId())
                .conversationId(command.conversationId())
                .message(command.message())
                .conversationHistory(toHistory(command.conversationHistory()))
                .accessFilter(accessFilterMapper.toContract(command.accessFilter()))
                .retrievalOptions(command.retrievalOptions());
    }

    private PythonQueryOutcome mapProblem(RestClientResponseException exception) {
        ProblemDetail problem = readProblem(exception);
        int status = exception.getStatusCode().value();
        if (status == 503) {
            return new PythonQueryOutcome.Unavailable(problem, "HTTP_503", problem.getDetail());
        }
        if (status == 422 || "QUERY_BLOCKED_BY_GUARD".equals(problem.getErrorCode())) {
            return new PythonQueryOutcome.GuardRejected(problem);
        }
        if (isDegradedProblem(problem)) {
            return new PythonQueryOutcome.Degraded(problem);
        }
        return new PythonQueryOutcome.Problem(status, problem);
    }

    private ProblemDetail readProblem(RestClientResponseException exception) {
        String body = exception.getResponseBodyAsString();
        if (body != null && !body.isBlank()) {
            try {
                return objectMapper.readValue(body, ProblemDetail.class);
            } catch (JsonProcessingException ignored) {
                // Fall through to a minimal problem from transport metadata.
            }
        }
        return new ProblemDetail()
                .type(URI.create("https://corp-rag.local/problems/ai-service-error"))
                .title("AI service error")
                .status(exception.getStatusCode().value())
                .detail(body == null || body.isBlank() ? exception.getMessage() : body);
    }

    private static List<ConversationMessage> toHistory(List<ChatMessage> history) {
        if (history == null || history.isEmpty()) {
            return List.of();
        }
        return history.stream()
                .filter(message -> message.content() != null)
                .map(message -> new ConversationMessage(toContractRole(message.role()), message.content()))
                .toList();
    }

    private static ConversationRole toContractRole(ChatMessageRole role) {
        return role == ChatMessageRole.USER ? ConversationRole.USER : ConversationRole.ASSISTANT;
    }

    private static boolean isDegradedProblem(ProblemDetail problem) {
        String haystack = String.join(
                        " ",
                        nullSafe(problem.getErrorCode()),
                        nullSafe(problem.getDetail()),
                        problem.getType() == null ? "" : problem.getType().toString())
                .toLowerCase(Locale.ROOT);
        return haystack.contains("missing_citations")
                || haystack.contains("missing-citations")
                || haystack.contains("invalid_citations")
                || haystack.contains("invalid-citations");
    }

    private static String nullSafe(String value) {
        return value == null ? "" : value;
    }

    private static boolean hasTimeoutCause(Throwable throwable) {
        Throwable current = throwable;
        while (current != null) {
            if (current instanceof SocketTimeoutException || current instanceof HttpTimeoutException) {
                return true;
            }
            String name = current.getClass().getSimpleName().toLowerCase(Locale.ROOT);
            if (name.contains("timeout") || name.contains("timedout")) {
                return true;
            }
            current = current.getCause();
        }
        return false;
    }

    public record PythonQueryCommand(
            UUID userId,
            UUID correlationId,
            UUID conversationId,
            String message,
            ResolvedAccessFilter accessFilter,
            List<ChatMessage> conversationHistory,
            RetrievalOptions retrievalOptions) {
    }

    public sealed interface PythonQueryOutcome {
        record Success(QueryResponse response) implements PythonQueryOutcome {
        }

        record GuardRejected(ProblemDetail problem) implements PythonQueryOutcome {
        }

        record Degraded(ProblemDetail problem) implements PythonQueryOutcome {
        }

        record Timeout(String detail) implements PythonQueryOutcome {
        }

        record Unavailable(ProblemDetail problem, String upstreamErrorClass, String detail) implements PythonQueryOutcome {
        }

        record Problem(int status, ProblemDetail problem) implements PythonQueryOutcome {
        }
    }
}
