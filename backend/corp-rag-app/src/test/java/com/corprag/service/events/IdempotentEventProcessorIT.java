package com.corprag.service.events;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.corprag.contracts.constants.EventRoutingKeys;
import com.corprag.repository.ProcessedEventRepository;
import com.corprag.testsupport.PostgresIntegrationTestSupport;
import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.testcontainers.junit.jupiter.Testcontainers;

@SpringBootTest
@Testcontainers(disabledWithoutDocker = true)
class IdempotentEventProcessorIT extends PostgresIntegrationTestSupport {

    @Autowired
    private IdempotentEventProcessor processor;

    @Autowired
    private ProcessedEventRepository processedEventRepository;

    @Test
    void processRunsHandlerOnlyForFirstEventAndAcknowledgesDuplicates() {
        UUID eventId = UUID.randomUUID();
        UUID correlationId = UUID.randomUUID();
        InboundEventMetadata metadata = new InboundEventMetadata(
                eventId,
                EventRoutingKeys.DOCUMENT_INDEXED,
                correlationId);
        AtomicInteger handlerCalls = new AtomicInteger();

        IdempotentEventResult first = processor.process(metadata, handlerCalls::incrementAndGet);
        IdempotentEventResult duplicate = processor.process(metadata, handlerCalls::incrementAndGet);

        assertThat(first.processed()).isTrue();
        assertThat(duplicate.duplicate()).isTrue();
        assertThat(handlerCalls).hasValue(1);
        assertThat(processedEventRepository.findById(eventId))
                .hasValueSatisfying(event -> {
                    assertThat(event.eventType()).isEqualTo(EventRoutingKeys.DOCUMENT_INDEXED);
                    assertThat(event.correlationId()).isEqualTo(correlationId);
                });
    }

    @Test
    void handlerExceptionRollsBackProcessedEventInsert() {
        UUID eventId = UUID.randomUUID();
        InboundEventMetadata metadata = new InboundEventMetadata(
                eventId,
                EventRoutingKeys.DOCUMENT_INDEXED,
                UUID.randomUUID());

        assertThatThrownBy(() -> processor.process(metadata, () -> {
            throw new IllegalStateException("business failure");
        })).isInstanceOf(IllegalStateException.class);

        assertThat(processedEventRepository.findById(eventId)).isEmpty();
    }

    @Test
    void cleanupRemovesOnlyRowsBeforeCutoff() {
        Instant cutoff = Instant.parse("2026-05-13T12:00:00Z");
        UUID oldEvent = UUID.randomUUID();
        UUID recentEvent = UUID.randomUUID();
        processedEventRepository.insertIfAbsent(
                oldEvent,
                EventRoutingKeys.DOCUMENT_INDEXED,
                UUID.randomUUID(),
                cutoff.minusSeconds(1));
        processedEventRepository.insertIfAbsent(
                recentEvent,
                EventRoutingKeys.DOCUMENT_INDEXED,
                UUID.randomUUID(),
                cutoff);

        assertThat(processor.cleanupProcessedEventsBefore(cutoff)).isEqualTo(1);

        assertThat(processedEventRepository.findById(oldEvent)).isEmpty();
        assertThat(processedEventRepository.findById(recentEvent)).isPresent();
    }
}
