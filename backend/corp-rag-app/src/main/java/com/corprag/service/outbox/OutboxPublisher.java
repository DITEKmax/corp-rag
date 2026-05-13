package com.corprag.service.outbox;

import com.corprag.adapter.amqp.AmqpHeaderNames;
import com.corprag.config.OutboxPublisherProperties;
import com.corprag.domain.OutboxEventRecord;
import com.corprag.repository.OutboxEventRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Collections;
import java.util.Map;
import org.springframework.amqp.AmqpException;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@ConditionalOnProperty(prefix = "app.outbox-publisher", name = "enabled", havingValue = "true")
public class OutboxPublisher {

    private static final int MAX_LAST_ERROR_LENGTH = 2048;
    private static final TypeReference<Map<String, Object>> HEADER_MAP = new TypeReference<>() {
    };

    private final OutboxEventRepository outboxEventRepository;
    private final RabbitTemplate rabbitTemplate;
    private final ObjectMapper objectMapper;
    private final OutboxPublisherProperties properties;
    private final Clock clock;

    public OutboxPublisher(
            OutboxEventRepository outboxEventRepository,
            RabbitTemplate rabbitTemplate,
            ObjectMapper objectMapper,
            OutboxPublisherProperties properties) {
        this(outboxEventRepository, rabbitTemplate, objectMapper, properties, Clock.systemUTC());
    }

    OutboxPublisher(
            OutboxEventRepository outboxEventRepository,
            RabbitTemplate rabbitTemplate,
            ObjectMapper objectMapper,
            OutboxPublisherProperties properties,
            Clock clock) {
        this.outboxEventRepository = outboxEventRepository;
        this.rabbitTemplate = rabbitTemplate;
        this.objectMapper = objectMapper;
        this.properties = properties;
        this.clock = clock;
    }

    @Scheduled(
            initialDelayString = "${app.outbox-publisher.initial-delay-ms:5000}",
            fixedDelayString = "${app.outbox-publisher.poll-delay-ms:5000}")
    @Transactional
    public void publishReady() {
        Instant now = clock.instant();
        int batchSize = Math.max(1, properties.getBatchSize());
        for (OutboxEventRecord event : outboxEventRepository.pollReadyUnpublished(now, batchSize)) {
            publishOne(event, now);
        }
    }

    @Scheduled(
            initialDelayString = "${app.outbox-publisher.cleanup-initial-delay-ms:60000}",
            fixedDelayString = "${app.outbox-publisher.cleanup-delay-ms:3600000}")
    @Transactional
    public void cleanupPublished() {
        if (!properties.isCleanupEnabled()) {
            return;
        }
        outboxEventRepository.cleanupPublishedBefore(clock.instant().minus(properties.getRetention()));
    }

    private void publishOne(OutboxEventRecord event, Instant now) {
        try {
            Map<String, Object> headers = readHeaders(event.headersJson());
            rabbitTemplate.convertAndSend(
                    event.exchangeName(),
                    event.routingKey(),
                    event.payloadJson().getBytes(StandardCharsets.UTF_8),
                    message -> {
                        MessageProperties messageProperties = message.getMessageProperties();
                        messageProperties.setContentType(MessageProperties.CONTENT_TYPE_JSON);
                        messageProperties.setDeliveryMode(MessageDeliveryMode.PERSISTENT);
                        headers.forEach(messageProperties::setHeader);
                        messageProperties.setHeader(
                                AmqpHeaderNames.CORRELATION_ID,
                                header(headers, AmqpHeaderNames.CORRELATION_ID, "correlation_id",
                                        event.correlationId() == null ? null : event.correlationId().toString()));
                        messageProperties.setHeader(
                                AmqpHeaderNames.EVENT_TYPE,
                                header(headers, AmqpHeaderNames.EVENT_TYPE, "event_type", event.eventType()));
                        messageProperties.setHeader(
                                AmqpHeaderNames.EVENT_VERSION,
                                header(headers, AmqpHeaderNames.EVENT_VERSION, "event_version",
                                        EventEnvelopeFactory.EVENT_VERSION));
                        return message;
                    });
            outboxEventRepository.markPublished(event.id(), now);
        } catch (RuntimeException exception) {
            outboxEventRepository.markFailure(event.id(), boundedError(exception), nextAttemptAt(event, now));
        }
    }

    private Map<String, Object> readHeaders(String headersJson) {
        if (headersJson == null || headersJson.isBlank()) {
            return Collections.emptyMap();
        }
        try {
            return objectMapper.readValue(headersJson, HEADER_MAP);
        } catch (Exception exception) {
            throw new AmqpException("Could not parse outbox headers for AMQP publish", exception);
        }
    }

    private Instant nextAttemptAt(OutboxEventRecord event, Instant now) {
        int attemptsAfterFailure = event.publishAttempts() + 1;
        Duration delay = properties.getInitialBackoff();
        for (int i = 1; i < attemptsAfterFailure && delay.compareTo(properties.getMaxBackoff()) < 0; i++) {
            delay = doubled(delay, properties.getMaxBackoff());
        }
        return now.plus(delay);
    }

    private static Duration doubled(Duration delay, Duration cap) {
        if (delay.compareTo(cap.dividedBy(2)) >= 0) {
            return cap;
        }
        return delay.multipliedBy(2);
    }

    private static String header(Map<String, Object> headers, String canonical, String legacy, String fallback) {
        Object value = headers.get(canonical);
        if (value == null) {
            value = headers.get(legacy);
        }
        if (value == null) {
            return fallback;
        }
        return value.toString();
    }

    private static String boundedError(RuntimeException exception) {
        String message = exception.getClass().getSimpleName() + ": " + exception.getMessage();
        if (message.length() <= MAX_LAST_ERROR_LENGTH) {
            return message;
        }
        return message.substring(0, MAX_LAST_ERROR_LENGTH);
    }
}
