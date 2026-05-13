package com.corprag.adapter.amqp;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.corprag.contracts.constants.EventRoutingKeys;
import com.corprag.security.CorrelationIdFilter;
import com.corprag.service.document.DocumentIndexedEvent;
import com.corprag.service.document.DocumentIndexingResultService;
import com.corprag.service.events.IdempotentEventHandler;
import com.corprag.service.events.IdempotentEventProcessor;
import com.corprag.service.events.IdempotentEventResult;
import com.corprag.service.events.InboundEventMetadata;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.slf4j.MDC;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageBuilder;

class DocumentIndexedConsumerTest {

    private static final UUID EVENT_ID = UUID.fromString("550e8400-e29b-41d4-a716-446655440003");
    private static final UUID DOCUMENT_ID = UUID.fromString("d8f3a1c2-e89b-42d3-a456-426614174000");
    private static final UUID ENVELOPE_CORRELATION_ID = UUID.fromString("22222222-2222-4222-8222-222222222222");
    private static final UUID HEADER_CORRELATION_ID = UUID.fromString("33333333-3333-4333-8333-333333333333");
    private static final Instant INDEXED_AT = Instant.parse("2026-05-13T12:01:00Z");

    private final IdempotentEventProcessor processor = mock(IdempotentEventProcessor.class);
    private final DocumentIndexingResultService service = mock(DocumentIndexingResultService.class);
    private final DocumentIndexedConsumer consumer = new DocumentIndexedConsumer(objectMapper(), processor, service);

    @AfterEach
    void clearMdc() {
        MDC.clear();
    }

    @Test
    void validCorrelationHeaderWinsAndMdcIsClearedAfterProcessing() throws Exception {
        when(processor.process(any(), any())).thenAnswer(invocation -> {
            InboundEventMetadata metadata = invocation.getArgument(0);
            IdempotentEventHandler handler = invocation.getArgument(1);
            assertThat(metadata.eventId()).isEqualTo(EVENT_ID);
            assertThat(metadata.eventType()).isEqualTo(EventRoutingKeys.DOCUMENT_INDEXED);
            assertThat(metadata.correlationId()).isEqualTo(HEADER_CORRELATION_ID);
            assertThat(MDC.get(CorrelationIdFilter.MDC_KEY)).isEqualTo(HEADER_CORRELATION_ID.toString());
            handler.handle();
            return IdempotentEventResult.processed(metadata.eventId());
        });

        consumer.handle(message(indexedEnvelope(ENVELOPE_CORRELATION_ID), HEADER_CORRELATION_ID.toString()));

        ArgumentCaptor<DocumentIndexedEvent> event = ArgumentCaptor.forClass(DocumentIndexedEvent.class);
        verify(service).handleIndexed(event.capture());
        assertThat(event.getValue().correlationId()).isEqualTo(HEADER_CORRELATION_ID);
        assertThat(event.getValue().documentId()).isEqualTo(DOCUMENT_ID);
        assertThat(event.getValue().chunkCount()).isEqualTo(42);
        assertThat(event.getValue().indexedAt()).isEqualTo(INDEXED_AT);
        assertThat(event.getValue().qdrantCollection()).isEqualTo("documents_chunks");
        assertThat(event.getValue().neo4jEntityCount()).isEqualTo(18);
        assertThat(event.getValue().durationMs()).isEqualTo(87520);
        assertThat(MDC.get(CorrelationIdFilter.MDC_KEY)).isNull();
    }

    @Test
    void generatedCorrelationIsLastResortWhenHeaderAndEnvelopeAreMissing() throws Exception {
        when(processor.process(any(), any())).thenAnswer(invocation -> {
            InboundEventMetadata metadata = invocation.getArgument(0);
            IdempotentEventHandler handler = invocation.getArgument(1);
            assertThat(metadata.correlationId()).isNotNull();
            assertThat(UUID.fromString(MDC.get(CorrelationIdFilter.MDC_KEY))).isEqualTo(metadata.correlationId());
            handler.handle();
            return IdempotentEventResult.processed(metadata.eventId());
        });

        consumer.handle(message(indexedEnvelope(null), null));

        ArgumentCaptor<DocumentIndexedEvent> event = ArgumentCaptor.forClass(DocumentIndexedEvent.class);
        verify(service).handleIndexed(event.capture());
        assertThat(event.getValue().correlationId()).isNotNull();
        assertThat(MDC.get(CorrelationIdFilter.MDC_KEY)).isNull();
    }

    @Test
    void duplicateResultDoesNotInvokeStatusOrAuditHandler() throws Exception {
        when(processor.process(any(), any())).thenAnswer(invocation -> {
            InboundEventMetadata metadata = invocation.getArgument(0);
            return IdempotentEventResult.duplicate(metadata.eventId());
        });

        consumer.handle(message(indexedEnvelope(ENVELOPE_CORRELATION_ID), ENVELOPE_CORRELATION_ID.toString()));

        verify(service, never()).handleIndexed(any());
        assertThat(MDC.get(CorrelationIdFilter.MDC_KEY)).isNull();
    }

    @Test
    void unexpectedEventTypeIsRejectedBeforeIdempotentProcessing() {
        Message message = message(indexedEnvelope(ENVELOPE_CORRELATION_ID)
                .replace(EventRoutingKeys.DOCUMENT_INDEXED, EventRoutingKeys.DOCUMENT_INDEXING_FAILED), null);

        assertThatThrownBy(() -> consumer.handle(message))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining(EventRoutingKeys.DOCUMENT_INDEXED);

        verify(processor, never()).process(any(), any());
        verify(service, never()).handleIndexed(any());
    }

    private static Message message(String json, String correlationHeader) {
        MessageBuilder builder = MessageBuilder.withBody(json.getBytes(StandardCharsets.UTF_8));
        if (correlationHeader != null) {
            builder.setHeader(AmqpHeaderNames.CORRELATION_ID, correlationHeader);
        }
        return builder.build();
    }

    private static String indexedEnvelope(UUID correlationId) {
        String correlationJson = correlationId == null ? "null" : "\"" + correlationId + "\"";
        return """
                {
                  "metadata": {
                    "eventId": "%s",
                    "eventType": "%s",
                    "eventVersion": "1.0.0",
                    "occurredAt": "2026-05-13T12:00:00Z",
                    "correlationId": %s,
                    "sourceService": "corp-rag-ai"
                  },
                  "payload": {
                    "documentId": "%s",
                    "chunkCount": 42,
                    "indexedAt": "%s",
                    "qdrantCollection": "documents_chunks",
                    "neo4jEntityCount": 18,
                    "durationMs": 87520
                  }
                }
                """.formatted(EVENT_ID, EventRoutingKeys.DOCUMENT_INDEXED, correlationJson, DOCUMENT_ID, INDEXED_AT);
    }

    private static ObjectMapper objectMapper() {
        return new ObjectMapper()
                .registerModule(new JavaTimeModule())
                .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    }
}
