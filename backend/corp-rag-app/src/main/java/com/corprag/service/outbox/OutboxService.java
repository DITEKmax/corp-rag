package com.corprag.service.outbox;

import com.corprag.contracts.constants.EventRoutingKeys;
import com.corprag.domain.DocumentRecord;
import com.corprag.domain.OutboxEventRecord;
import com.corprag.repository.OutboxEventRepository;
import java.time.Instant;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class OutboxService {

    private final OutboxEventRepository outboxEventRepository;
    private final EventEnvelopeFactory eventEnvelopeFactory;

    public OutboxService(OutboxEventRepository outboxEventRepository, EventEnvelopeFactory eventEnvelopeFactory) {
        this.outboxEventRepository = outboxEventRepository;
        this.eventEnvelopeFactory = eventEnvelopeFactory;
    }

    public OutboxEventRecord createDocumentUploaded(DocumentRecord document, UUID correlationId, Instant occurredAt) {
        OutboxEventRecord event = toOutboxRecord(
                document.id(),
                correlationId,
                occurredAt,
                eventEnvelopeFactory.documentUploaded(document, correlationId, occurredAt));
        outboxEventRepository.insert(event);
        return event;
    }

    public OutboxEventRecord createDocumentDeleted(
            DocumentRecord document,
            UUID deletedBy,
            UUID correlationId,
            Instant deletedAt) {
        OutboxEventRecord event = toOutboxRecord(
                document.id(),
                correlationId,
                deletedAt,
                eventEnvelopeFactory.documentDeleted(document, deletedBy, correlationId, deletedAt));
        outboxEventRepository.insert(event);
        return event;
    }

    private static OutboxEventRecord toOutboxRecord(
            UUID documentId,
            UUID correlationId,
            Instant occurredAt,
            EventEnvelopeFactory.EventEnvelope envelope) {
        return new OutboxEventRecord(
                envelope.eventId(),
                "DOCUMENT",
                documentId,
                envelope.eventType(),
                envelope.routingKey(),
                envelope.exchangeName(),
                envelope.payloadJson(),
                envelope.headersJson(),
                correlationId,
                occurredAt,
                null,
                0,
                null,
                occurredAt);
    }
}
