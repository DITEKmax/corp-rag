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
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.amqp.AmqpRejectAndDontRequeueException;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(name = "app.document-indexing-consumers.enabled", havingValue = "true")
public class DocumentIndexedConsumer {

    private static final Logger log = LoggerFactory.getLogger(DocumentIndexedConsumer.class);

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
    public void handle(Message message) {
        ParsedDocumentIndexedMessage parsed = parseMessage(message);

        try {
            MDC.put(CorrelationIdFilter.MDC_KEY, parsed.correlationId().toString());
            idempotentEventProcessor.process(
                    new InboundEventMetadata(
                            parsed.metadata().eventId(),
                            parsed.metadata().eventType(),
                            parsed.correlationId()),
                    () -> indexingResultService.handleIndexed(parsed.event()));
        } finally {
            MDC.remove(CorrelationIdFilter.MDC_KEY);
        }
    }

    private ParsedDocumentIndexedMessage parseMessage(Message message) {
        try {
            DocumentIndexedEnvelope envelope = AmqpConsumerSupport.requireNonNull(
                    objectMapper.readValue(message.getBody(), DocumentIndexedEnvelope.class),
                    "event envelope");
            EventEnvelopeMetadata metadata = AmqpConsumerSupport.requireMetadata(
                    envelope.metadata(),
                    EventRoutingKeys.DOCUMENT_INDEXED);
            DocumentIndexedPayload payload = AmqpConsumerSupport.requirePayload(envelope.payload());
            UUID correlationId = AmqpConsumerSupport.resolveCorrelationId(message, metadata);
            DocumentIndexedEvent event = new DocumentIndexedEvent(
                    metadata.eventId(),
                    correlationId,
                    AmqpConsumerSupport.requireNonNull(payload.documentId(), "documentId"),
                    AmqpConsumerSupport.requireNonNegative(payload.chunkCount(), "chunkCount"),
                    AmqpConsumerSupport.requireNonNull(payload.indexedAt(), "indexedAt"),
                    AmqpConsumerSupport.requireText(payload.qdrantCollection(), "qdrantCollection"),
                    AmqpConsumerSupport.requireNonNegative(payload.neo4jEntityCount(), "neo4jEntityCount"),
                    AmqpConsumerSupport.requireNonNegative(payload.durationMs(), "durationMs"));
            return new ParsedDocumentIndexedMessage(metadata, correlationId, event);
        } catch (IOException | IllegalArgumentException ex) {
            log.warn("Rejecting invalid {} message without requeue", QueueNames.BACKEND_DOCUMENT_INDEXED, ex);
            throw new AmqpRejectAndDontRequeueException(
                    "Invalid " + QueueNames.BACKEND_DOCUMENT_INDEXED + " message",
                    ex);
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

    private record ParsedDocumentIndexedMessage(
            EventEnvelopeMetadata metadata,
            UUID correlationId,
            DocumentIndexedEvent event) {
    }
}
