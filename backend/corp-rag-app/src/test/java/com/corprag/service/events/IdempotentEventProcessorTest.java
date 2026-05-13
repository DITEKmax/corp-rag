package com.corprag.service.events;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.corprag.contracts.constants.EventRoutingKeys;
import com.corprag.repository.ProcessedEventRepository;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

class IdempotentEventProcessorTest {

    private static final Instant NOW = Instant.parse("2026-05-13T12:00:00Z");

    private final ProcessedEventRepository repository = mock(ProcessedEventRepository.class);
    private final IdempotentEventProcessor processor = new IdempotentEventProcessor(
            repository,
            Clock.fixed(NOW, ZoneOffset.UTC),
            Duration.ofDays(30));

    @Test
    void firstEventExecutesBusinessHandler() {
        UUID eventId = UUID.randomUUID();
        UUID correlationId = UUID.randomUUID();
        InboundEventMetadata metadata = metadata(eventId, correlationId);
        when(repository.insertIfAbsent(eventId, EventRoutingKeys.DOCUMENT_INDEXED, correlationId, NOW)).thenReturn(true);
        AtomicInteger handlerCalls = new AtomicInteger();

        IdempotentEventResult result = processor.process(metadata, handlerCalls::incrementAndGet);

        assertThat(result.processed()).isTrue();
        assertThat(handlerCalls).hasValue(1);
    }

    @Test
    void duplicateEventDoesNotExecuteBusinessHandler() {
        UUID eventId = UUID.randomUUID();
        UUID correlationId = UUID.randomUUID();
        InboundEventMetadata metadata = metadata(eventId, correlationId);
        when(repository.insertIfAbsent(eventId, EventRoutingKeys.DOCUMENT_INDEXED, correlationId, NOW)).thenReturn(false);
        IdempotentEventHandler handler = mock(IdempotentEventHandler.class);

        IdempotentEventResult result = processor.process(metadata, handler);

        assertThat(result.duplicate()).isTrue();
        verify(handler, never()).handle();
    }

    @Test
    void scheduledCleanupUsesThirtyDayRetentionCutoff() {
        processor.cleanupProcessedEvents();

        verify(repository).cleanupProcessedBefore(NOW.minus(Duration.ofDays(30)));
    }

    private static InboundEventMetadata metadata(UUID eventId, UUID correlationId) {
        return new InboundEventMetadata(eventId, EventRoutingKeys.DOCUMENT_INDEXED, correlationId);
    }
}
