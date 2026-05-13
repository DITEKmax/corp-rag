package com.corprag.service.outbox;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.corprag.adapter.amqp.AmqpHeaderNames;
import com.corprag.config.OutboxPublisherProperties;
import com.corprag.contracts.constants.EventRoutingKeys;
import com.corprag.contracts.constants.ExchangeNames;
import com.corprag.domain.OutboxEventRecord;
import com.corprag.repository.OutboxEventRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.amqp.AmqpException;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageBuilder;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.amqp.rabbit.core.RabbitTemplate;

class OutboxPublisherTest {

    private static final Instant NOW = Instant.parse("2026-05-13T12:00:00Z");
    private static final UUID EVENT_ID = UUID.fromString("550e8400-e29b-41d4-a716-446655440001");
    private static final UUID DOCUMENT_ID = UUID.fromString("d8f3a1c2-e89b-42d3-a456-426614174000");
    private static final UUID CORRELATION_ID = UUID.fromString("22222222-2222-4222-8222-222222222222");

    private final OutboxEventRepository repository = mock(OutboxEventRepository.class);
    private final RabbitTemplate rabbitTemplate = mock(RabbitTemplate.class);
    private final OutboxPublisherProperties properties = properties();
    private final OutboxPublisher publisher = new OutboxPublisher(
            repository,
            rabbitTemplate,
            new ObjectMapper(),
            properties,
            Clock.fixed(NOW, ZoneOffset.UTC));

    @Test
    void successfulPublishSendsPersistentMessageHeadersAndMarksPublished() throws Exception {
        OutboxEventRecord event = event(0, headersJson());
        when(repository.pollReadyUnpublished(NOW, 50)).thenReturn(List.of(event));

        publisher.publishReady();

        ArgumentCaptor<Object> body = ArgumentCaptor.forClass(Object.class);
        ArgumentCaptor<MessagePostProcessor> processor = ArgumentCaptor.forClass(MessagePostProcessor.class);
        verify(rabbitTemplate).convertAndSend(
                eq(ExchangeNames.DOCUMENTS_TOPIC),
                eq(EventRoutingKeys.DOCUMENT_UPLOADED),
                body.capture(),
                processor.capture());
        assertThat(new String((byte[]) body.getValue(), StandardCharsets.UTF_8)).isEqualTo(event.payloadJson());

        Message processed = processor.getValue()
                .postProcessMessage(MessageBuilder.withBody("{}".getBytes(StandardCharsets.UTF_8)).build());
        assertThat(processed.getMessageProperties().getDeliveryMode()).isEqualTo(MessageDeliveryMode.PERSISTENT);
        assertThat(processed.getMessageProperties().getContentType()).isEqualTo("application/json");
        assertThat((String) processed.getMessageProperties().getHeader(AmqpHeaderNames.CORRELATION_ID))
                .isEqualTo(CORRELATION_ID.toString());
        assertThat((String) processed.getMessageProperties().getHeader(AmqpHeaderNames.EVENT_TYPE))
                .isEqualTo(EventRoutingKeys.DOCUMENT_UPLOADED);
        assertThat((String) processed.getMessageProperties().getHeader(AmqpHeaderNames.EVENT_VERSION))
                .isEqualTo("1.0.0");
        assertThat((String) processed.getMessageProperties().getHeader("custom-header")).isEqualTo("custom-value");

        verify(repository).markPublished(EVENT_ID, NOW);
        verify(repository, never()).markFailure(eq(EVENT_ID), any(), any());
    }

    @Test
    void failedPublishStoresBoundedErrorAndSchedulesInitialBackoff() {
        OutboxEventRecord event = event(0, headersJson());
        when(repository.pollReadyUnpublished(NOW, 50)).thenReturn(List.of(event));
        doThrow(new AmqpException("broker down")).when(rabbitTemplate)
                .convertAndSend(eq(ExchangeNames.DOCUMENTS_TOPIC), eq(EventRoutingKeys.DOCUMENT_UPLOADED),
                        any(Object.class), any(MessagePostProcessor.class));

        publisher.publishReady();

        ArgumentCaptor<String> error = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<Instant> nextAttempt = ArgumentCaptor.forClass(Instant.class);
        verify(repository).markFailure(eq(EVENT_ID), error.capture(), nextAttempt.capture());
        assertThat(error.getValue()).contains("AmqpException").contains("broker down");
        assertThat(nextAttempt.getValue()).isEqualTo(NOW.plusSeconds(1));
        verify(repository, never()).markPublished(eq(EVENT_ID), any());
    }

    @Test
    void repeatedFailedPublishCapsBackoffAtFiveMinutes() {
        OutboxEventRecord event = event(20, headersJson());
        when(repository.pollReadyUnpublished(NOW, 50)).thenReturn(List.of(event));
        doThrow(new AmqpException("still down")).when(rabbitTemplate)
                .convertAndSend(eq(ExchangeNames.DOCUMENTS_TOPIC), eq(EventRoutingKeys.DOCUMENT_UPLOADED),
                        any(Object.class), any(MessagePostProcessor.class));

        publisher.publishReady();

        ArgumentCaptor<Instant> nextAttempt = ArgumentCaptor.forClass(Instant.class);
        verify(repository).markFailure(eq(EVENT_ID), any(), nextAttempt.capture());
        assertThat(nextAttempt.getValue()).isEqualTo(NOW.plus(Duration.ofMinutes(5)));
    }

    @Test
    void batchSizeIsConfigurable() {
        properties.setBatchSize(7);
        when(repository.pollReadyUnpublished(NOW, 7)).thenReturn(List.of());

        publisher.publishReady();

        verify(repository).pollReadyUnpublished(NOW, 7);
    }

    @Test
    void cleanupDeletesPublishedRowsPastRetentionCutoff() {
        properties.setRetention(Duration.ofDays(7));

        publisher.cleanupPublished();

        verify(repository).cleanupPublishedBefore(NOW.minus(Duration.ofDays(7)));
    }

    @Test
    void cleanupCanBeDisabled() {
        properties.setCleanupEnabled(false);

        publisher.cleanupPublished();

        verify(repository, never()).cleanupPublishedBefore(any());
    }

    private static OutboxPublisherProperties properties() {
        OutboxPublisherProperties properties = new OutboxPublisherProperties();
        properties.setEnabled(true);
        properties.setBatchSize(50);
        properties.setInitialBackoff(Duration.ofSeconds(1));
        properties.setMaxBackoff(Duration.ofMinutes(5));
        properties.setRetention(Duration.ofDays(7));
        return properties;
    }

    private static OutboxEventRecord event(int publishAttempts, String headersJson) {
        return new OutboxEventRecord(
                EVENT_ID,
                "DOCUMENT",
                DOCUMENT_ID,
                EventRoutingKeys.DOCUMENT_UPLOADED,
                EventRoutingKeys.DOCUMENT_UPLOADED,
                ExchangeNames.DOCUMENTS_TOPIC,
                "{\"metadata\":{\"eventId\":\"" + EVENT_ID + "\"}}",
                headersJson,
                CORRELATION_ID,
                NOW.minusSeconds(30),
                null,
                publishAttempts,
                null,
                NOW.minusSeconds(1));
    }

    private static String headersJson() {
        return """
                {
                  "x-correlation-id": "%s",
                  "x-event-type": "%s",
                  "x-event-version": "1.0.0",
                  "custom-header": "custom-value"
                }
                """.formatted(CORRELATION_ID, EventRoutingKeys.DOCUMENT_UPLOADED);
    }
}
