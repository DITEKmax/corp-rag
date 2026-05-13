package com.corprag.service.events;

import com.corprag.repository.ProcessedEventRepository;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class IdempotentEventProcessor {

    private static final Duration DEFAULT_RETENTION = Duration.ofDays(30);

    private final ProcessedEventRepository processedEventRepository;
    private final Clock clock;
    private final Duration retention;

    @Autowired
    public IdempotentEventProcessor(
            ProcessedEventRepository processedEventRepository,
            @Value("${app.processed-events.retention-days:30}") long retentionDays) {
        this(processedEventRepository, Clock.systemUTC(), Duration.ofDays(retentionDays));
    }

    IdempotentEventProcessor(ProcessedEventRepository processedEventRepository, Clock clock, Duration retention) {
        this.processedEventRepository = processedEventRepository;
        this.clock = clock;
        this.retention = retention == null ? DEFAULT_RETENTION : retention;
    }

    @Transactional
    public IdempotentEventResult process(InboundEventMetadata metadata, IdempotentEventHandler handler) {
        boolean inserted = processedEventRepository.insertIfAbsent(
                metadata.eventId(),
                metadata.eventType(),
                metadata.correlationId(),
                clock.instant());
        if (!inserted) {
            return IdempotentEventResult.duplicate(metadata.eventId());
        }

        handler.handle();
        return IdempotentEventResult.processed(metadata.eventId());
    }

    @Scheduled(
            initialDelayString = "${app.processed-events.cleanup-initial-delay-ms:60000}",
            fixedDelayString = "${app.processed-events.cleanup-delay-ms:3600000}")
    public void cleanupProcessedEvents() {
        cleanupProcessedEventsBefore(clock.instant().minus(retention));
    }

    @Transactional
    public int cleanupProcessedEventsBefore(Instant cutoff) {
        return processedEventRepository.cleanupProcessedBefore(cutoff);
    }
}
