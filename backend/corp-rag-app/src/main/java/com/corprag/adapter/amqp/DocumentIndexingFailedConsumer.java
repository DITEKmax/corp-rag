package com.corprag.adapter.amqp;

import com.corprag.contracts.constants.EventRoutingKeys;
import com.corprag.contracts.constants.QueueNames;
import com.corprag.security.CorrelationIdFilter;
import com.corprag.service.document.DocumentIndexingFailedEvent;
import com.corprag.service.document.DocumentIndexingResultService;
import com.corprag.service.events.EventEnvelopeMetadata;
import com.corprag.service.events.IdempotentEventProcessor;
import com.corprag.service.events.InboundEventMetadata;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.time.Instant;
import java.util.UUID;
import org.slf4j.MDC;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(name = "app.document-indexing-consumers.enabled", havingValue = "true")
public class DocumentIndexingFailedConsumer {

    private final ObjectMapper objectMapper;
    private final IdempotentEventProcessor idempotentEventProcessor;
    private final DocumentIndexingResultService indexingResultService;

    public DocumentIndexingFailedConsumer(
            ObjectMapper objectMapper,
            IdempotentEventProcessor idempotentEventProcessor,
            DocumentIndexingResultService indexingResultService) {
        this.objectMapper = objectMapper;
        this.idempotentEventProcessor = idempotentEventProcessor;
        this.indexingResultService = indexingResultService;
    }

    @RabbitListener(queues = QueueNames.BACKEND_DOCUMENT_FAILED)
    public void handle(Message message) throws IOException {
        DocumentIndexingFailedEnvelope envelope =
                objectMapper.readValue(message.getBody(), DocumentIndexingFailedEnvelope.class);
        EventEnvelopeMetadata metadata = AmqpConsumerSupport.requireMetadata(
                envelope.metadata(),
                EventRoutingKeys.DOCUMENT_INDEXING_FAILED);
        DocumentIndexingFailedPayload payload = AmqpConsumerSupport.requirePayload(envelope.payload());
        UUID correlationId = AmqpConsumerSupport.resolveCorrelationId(message, metadata);

        try {
            MDC.put(CorrelationIdFilter.MDC_KEY, correlationId.toString());
            idempotentEventProcessor.process(
                    new InboundEventMetadata(metadata.eventId(), metadata.eventType(), correlationId),
                    () -> indexingResultService.handleFailed(new DocumentIndexingFailedEvent(
                            metadata.eventId(),
                            correlationId,
                            AmqpConsumerSupport.requireNonNull(payload.documentId(), "documentId"),
                            AmqpConsumerSupport.requireText(payload.stage(), "stage"),
                            AmqpConsumerSupport.requireText(payload.errorCode(), "errorCode"),
                            AmqpConsumerSupport.requireText(payload.errorMessage(), "errorMessage"),
                            AmqpConsumerSupport.requireNonNull(payload.failedAt(), "failedAt"),
                            AmqpConsumerSupport.requireNonNull(payload.retryable(), "retryable"),
                            AmqpConsumerSupport.requireNonNegative(payload.retryCount(), "retryCount"))));
        } finally {
            MDC.remove(CorrelationIdFilter.MDC_KEY);
        }
    }

    public record DocumentIndexingFailedEnvelope(
            EventEnvelopeMetadata metadata,
            DocumentIndexingFailedPayload payload) {
    }

    public record DocumentIndexingFailedPayload(
            UUID documentId,
            String stage,
            String errorCode,
            String errorMessage,
            Instant failedAt,
            Boolean retryable,
            Integer retryCount) {
    }
}
