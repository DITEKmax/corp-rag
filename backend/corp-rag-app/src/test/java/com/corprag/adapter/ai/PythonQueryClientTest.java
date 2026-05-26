package com.corprag.adapter.ai;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.corprag.adapter.ai.PythonQueryClient.PythonQueryCommand;
import com.corprag.adapter.ai.PythonQueryClient.PythonQueryOutcome;
import com.corprag.adapter.rest.QueryAccessFilterMapper;
import com.corprag.domain.AccessLevel;
import com.corprag.domain.DocType;
import com.corprag.domain.ResolvedAccessFilter;
import com.corprag.domain.chat.ChatMessage;
import com.corprag.domain.chat.ChatMessageRole;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.math.BigDecimal;
import java.net.InetSocketAddress;
import java.net.SocketTimeoutException;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

class PythonQueryClientTest {

    private HttpServer server;

    @AfterEach
    void tearDown() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    void postsRequiredFieldsToQueryEndpointOnly() throws Exception {
        AtomicReference<String> path = new AtomicReference<>();
        AtomicReference<String> body = new AtomicReference<>();
        server = server(exchange -> {
            path.set(exchange.getRequestURI().getPath());
            body.set(new String(exchange.getRequestBody().readAllBytes()));
            respond(exchange, 200, queryResponseJson(commandConversationId(), commandCorrelationId()));
        });

        PythonQueryOutcome outcome = client(Duration.ofSeconds(2)).query(command());

        assertThat(outcome).isInstanceOf(PythonQueryOutcome.Success.class);
        assertThat(path.get()).isEqualTo("/v1/query");
        assertThat(body.get())
                .contains("\"userId\":\"" + commandUserId() + "\"")
                .contains("\"correlationId\":\"" + commandCorrelationId() + "\"")
                .contains("\"conversationId\":\"" + commandConversationId() + "\"")
                .contains("\"message\":\"What is the policy?\"")
                .contains("\"conversationHistory\"")
                .contains("\"role\":\"user\"")
                .contains("\"role\":\"assistant\"")
                .doesNotContain("chunks", "chunkDetail");
    }

    @Test
    void requiresConversationIdBeforeCallingPython() {
        PythonQueryCommand invalid = new PythonQueryCommand(
                commandUserId(),
                commandCorrelationId(),
                null,
                "What is the policy?",
                accessFilter(),
                List.of(),
                null);

        assertThatThrownBy(() -> client("http://127.0.0.1:1", Duration.ofSeconds(2)).query(invalid))
                .isInstanceOf(NullPointerException.class)
                .hasMessageContaining("conversationId");
    }

    @Test
    void mapsGuardAndDegradedProblemsSeparately() throws Exception {
        server = server(exchange -> respond(exchange, 422, problemJson(422, "QUERY_BLOCKED_BY_GUARD", "blocked")));
        assertThat(client(Duration.ofSeconds(2)).query(command()))
                .isInstanceOf(PythonQueryOutcome.GuardRejected.class);
        server.stop(0);

        server = server(exchange -> respond(exchange, 500, problemJson(500, "OUTPUT_GUARD_FAILED", "missing_citations")));
        assertThat(client(Duration.ofSeconds(2)).query(command()))
                .isInstanceOf(PythonQueryOutcome.Degraded.class);
    }

    @Test
    void mapsServiceUnavailableAndTransportTimeoutSeparately() throws Exception {
        server = server(exchange -> respond(exchange, 503, problemJson(503, "AI_SERVICE_UNAVAILABLE", "query service down")));
        assertThat(client(Duration.ofSeconds(2)).query(command()))
                .isInstanceOf(PythonQueryOutcome.Unavailable.class);
        server.stop(0);

        RestClient timeoutRestClient = RestClient.builder()
                .requestFactory((uri, method) -> {
                    throw new SocketTimeoutException("Read timed out");
                })
                .build();
        assertThat(client(timeoutRestClient).query(command()))
                .isInstanceOf(PythonQueryOutcome.Timeout.class);
    }

    private PythonQueryClient client(Duration readTimeout) {
        return client("http://127.0.0.1:" + server.getAddress().getPort(), readTimeout);
    }

    private PythonQueryClient client(String baseUrl, Duration readTimeout) {
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(500);
        requestFactory.setReadTimeout(Math.toIntExact(readTimeout.toMillis()));
        RestClient restClient = RestClient.builder()
                .baseUrl(baseUrl)
                .requestFactory(requestFactory)
                .build();
        return client(restClient);
    }

    private PythonQueryClient client(RestClient restClient) {
        return new PythonQueryClient(restClient, new QueryAccessFilterMapper(), new ObjectMapper());
    }

    private HttpServer server(ExchangeHandler handler) throws IOException {
        HttpServer httpServer = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        httpServer.createContext("/v1/query", exchange -> {
            try {
                handler.handle(exchange);
            } finally {
                exchange.close();
            }
        });
        httpServer.setExecutor(Executors.newSingleThreadExecutor());
        httpServer.start();
        return httpServer;
    }

    private static void respond(HttpExchange exchange, int status, String json) throws IOException {
        byte[] bytes = json.getBytes();
        exchange.getResponseHeaders().add("Content-Type", "application/json");
        exchange.sendResponseHeaders(status, bytes.length);
        exchange.getResponseBody().write(bytes);
    }

    private static PythonQueryCommand command() {
        return new PythonQueryCommand(
                commandUserId(),
                commandCorrelationId(),
                commandConversationId(),
                "What is the policy?",
                accessFilter(),
                List.of(
                        historyMessage(ChatMessageRole.USER, "Earlier question", 1),
                        historyMessage(ChatMessageRole.ASSISTANT, "Earlier answer", 2)),
                null);
    }

    private static ChatMessage historyMessage(ChatMessageRole role, String content, long second) {
        return new ChatMessage(
                UUID.randomUUID(),
                commandConversationId(),
                role,
                null,
                content,
                null,
                null,
                role == ChatMessageRole.ASSISTANT ? new BigDecimal("0.700") : null,
                commandCorrelationId(),
                Instant.parse("2026-05-21T10:00:00Z").plusSeconds(second),
                null);
    }

    private static ResolvedAccessFilter accessFilter() {
        return new ResolvedAccessFilter(
                List.of(AccessLevel.PUBLIC, AccessLevel.INTERNAL),
                List.of("HR"),
                List.of(DocType.POLICY));
    }

    private static UUID commandUserId() {
        return UUID.fromString("00000000-0000-4000-8000-00000000a001");
    }

    private static UUID commandCorrelationId() {
        return UUID.fromString("00000000-0000-4000-8000-00000000a002");
    }

    private static UUID commandConversationId() {
        return UUID.fromString("00000000-0000-4000-8000-00000000a003");
    }

    private static String queryResponseJson(UUID conversationId, UUID correlationId) {
        return """
                {
                  "answered": true,
                  "answer": "Policy answer [1]",
                  "citations": [],
                  "confidence": 0.8,
                  "conversationId": "%s",
                  "messageId": "%s",
                  "retrievalMeta": {
                    "route": "FACTUAL",
                    "retrieversAttempted": ["HYBRID"],
                    "retrieversUsed": ["HYBRID"],
                    "degradationWarnings": [],
                    "latencyMs": 123,
                    "chunksConsidered": 2,
                    "chunksReturned": 1,
                    "rerankerUsed": true,
                    "modelId": "deepseek/deepseek-v4-flash:free"
                  }
                }
                """.formatted(conversationId, correlationId);
    }

    private static String problemJson(int status, String errorCode, String detail) {
        return """
                {
                  "type": "https://corp-rag.local/problems/%s",
                  "title": "AI problem",
                  "status": %d,
                  "detail": "%s",
                  "errorCode": "%s",
                  "correlationId": "%s"
                }
                """.formatted(errorCode.toLowerCase().replace("_", "-"), status, detail, errorCode, commandCorrelationId());
    }

    @FunctionalInterface
    private interface ExchangeHandler {
        void handle(HttpExchange exchange) throws IOException;
    }
}
