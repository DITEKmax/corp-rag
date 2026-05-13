package com.corprag.adapter.amqp;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.corprag.contracts.constants.ErrorCodes;
import com.corprag.contracts.constants.EventRoutingKeys;
import com.corprag.security.CorrelationIdFilter;
import com.corprag.service.document.DocumentIndexingFailedEvent;
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

class DocumentIndexingFailedConsumerTest {

    private static final UUID EVENT_ID = UUID.fromString("550e8400-e29b-41d4-a716-446655440004");
    private static final UUID DOCUMENT_ID = UUID.fromString("d8f3a1c2-e89b-42d3-a456-426614174000");
    private static final UUID ENVELOPE_CORRELATION_ID = UUID.fromString("22222222-2222-4222-8222-222222222222");
    private static final Instant FAILED_AT = Instant.parse("2026-05-13T12:02:00Z");

    private final IdempotentEventProcessor processor = mock(IdempotentEventProcessor.class);
    private final DocumentIndexingResultService service = mock(DocumentIndexingResultService.class);
    private final DocumentIndexingFailedConsumer consumer =
            new DocumentIndexingFailedConsumer(objectMapper(), processor, service);

    @AfterEach
    void clearMdc() {
        MDC.clear();
    }

    @Test
    void invalidCorrelationHeaderFallsBackToEnvelopeMetadata() throws Exception {
        when(processor.process(any(), any())).thenAnswer(invocation -> {
            InboundEventMetadata metadata = invocation.getArgument(0);
            IdempotentEventHandler handler = invocation.getArgument(1);
            assertThat(metadata.eventType()).isEqualTo(EventRoutingKeys.DOCUMENT_INDEXING_FAILED);
            assertThat(metadata.correlationId()).isEqualTo(ENVELOPE_CORRELATION_ID);
            assertThat(MDC.get(CorrelationIdFilter.MDC_KEY)).isEqualTo(ENVELOPE_CORRELATION_ID.toString());
            handler.handle();
            return IdempotentEventResult.processed(metadata.eventId());
        });

        consumer.handle(message(failedEnvelope(), "not-a-uuid"));

        ArgumentCaptor<DocumentIndexingFailedEvent> event = ArgumentCaptor.forClass(DocumentIndexingFailedEvent.class);
        verify(service).handleFailed(event.capture());
        assertThat(event.getValue().documentId()).isEqualTo(DOCUMENT_ID);
        assertThat(event.getValue().stage()).isEqualTo("PARSING");
        assertThat(event.getValue().errorCode()).isEqualTo(ErrorCodes.INVALID_FILE_FORMAT.code());
        assertThat(event.getValue().errorMessage()).isEqualTo("No extractable text");
        assertThat(event.getValue().failedAt()).isEqualTo(FAILED_AT);
        assertThat(event.getValue().retryable()).isFalse();
        assertThat(event.getValue().retryCount()).isZero();
        assertThat(MDC.get(CorrelationIdFilter.MDC_KEY)).isNull();
    }

    @Test
    void mdcIsClearedWhenProcessingThrows() throws Exception {
        when(processor.process(any(), any())).thenThrow(new IllegalStateException("retry me"));

        assertThatThrownBy(() -> consumer.handle(message(failedEnvelope(), ENVELOPE_CORRELATION_ID.toString())))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("retry me");

        assertThat(MDC.get(CorrelationIdFilter.MDC_KEY)).isNull();
    }

    private static Message message(String json, String correlationHeader) {
        return MessageBuilder.withBody(json.getBytes(StandardCharsets.UTF_8))
                .setHeader(AmqpHeaderNames.CORRELATION_ID, correlationHeader)
                .build();
    }

    private static String failedEnvelope() {
        return """
                {
                  "metadata": {
                    "eventId": "%s",
                    "eventType": "%s",
                    "eventVersion": "1.0.0",
                    "occurredAt": "2026-05-13T12:00:00Z",
                    "correlationId": "%s",
                    "sourceService": "corp-rag-ai"
                  },
                  "payload": {
                    "documentId": "%s",
                    "stage": "PARSING",
                    "errorCode": "%s",
                    "errorMessage": "No extractable text",
                    "failedAt": "%s",
                    "retryable": false,
                    "retryCount": 0
                  }
                }
                """.formatted(
                EVENT_ID,
                EventRoutingKeys.DOCUMENT_INDEXING_FAILED,
                ENVELOPE_CORRELATION_ID,
                DOCUMENT_ID,
                ErrorCodes.INVALID_FILE_FORMAT.code(),
                FAILED_AT);
    }

    private static ObjectMapper objectMapper() {
        return new ObjectMapper()
                .registerModule(new JavaTimeModule())
                .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    }
}
