package com.corprag.adapter.amqp;

import com.corprag.contracts.constants.EventRoutingKeys;
import com.corprag.contracts.constants.QueueNames;
import com.corprag.security.CorrelationIdFilter;
import com.corprag.service.document.DocumentIndexedEvent;
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
public class DocumentIndexedConsumer {

    private final ObjectMapper objectMapper;
    private final IdempotentEventProcessor idempotentEventProcessor;
    private final DocumentIndexingResultService indexingResultService;

    public DocumentIndexedConsumer(
            ObjectMapper objectMapper,
            IdempotentEventProcessor idempotentEventProcessor,
            DocumentIndexingResultService indexingResultService) {
        this.objectMapper = objectMapper;
        this.idempotentEventProcessor = idempotentEventProcessor;
        this.indexingResultService = indexingResultService;
    }

    @RabbitListener(queues = QueueNames.BACKEND_DOCUMENT_INDEXED)
    public void handle(Message message) throws IOException {
        DocumentIndexedEnvelope envelope = objectMapper.readValue(message.getBody(), DocumentIndexedEnvelope.class);
        EventEnvelopeMetadata metadata = AmqpConsumerSupport.requireMetadata(
                envelope.metadata(),
                EventRoutingKeys.DOCUMENT_INDEXED);
        DocumentIndexedPayload payload = AmqpConsumerSupport.requirePayload(envelope.payload());
        UUID correlationId = AmqpConsumerSupport.resolveCorrelationId(message, metadata);

        try {
            MDC.put(CorrelationIdFilter.MDC_KEY, correlationId.toString());
            idempotentEventProcessor.process(
                    new InboundEventMetadata(metadata.eventId(), metadata.eventType(), correlationId),
                    () -> indexingResultService.handleIndexed(new DocumentIndexedEvent(
                            metadata.eventId(),
                            correlationId,
                            AmqpConsumerSupport.requireNonNull(payload.documentId(), "documentId"),
                            AmqpConsumerSupport.requireNonNegative(payload.chunkCount(), "chunkCount"),
                            AmqpConsumerSupport.requireNonNull(payload.indexedAt(), "indexedAt"),
                            AmqpConsumerSupport.requireText(payload.qdrantCollection(), "qdrantCollection"),
                            AmqpConsumerSupport.requireNonNegative(payload.neo4jEntityCount(), "neo4jEntityCount"),
                            AmqpConsumerSupport.requireNonNegative(payload.durationMs(), "durationMs"))));
        } finally {
            MDC.remove(CorrelationIdFilter.MDC_KEY);
        }
    }

    public record DocumentIndexedEnvelope(EventEnvelopeMetadata metadata, DocumentIndexedPayload payload) {
    }

    public record DocumentIndexedPayload(
            UUID documentId,
            Integer chunkCount,
            Instant indexedAt,
            String qdrantCollection,
            Integer neo4jEntityCount,
            Long durationMs) {
    }
}
