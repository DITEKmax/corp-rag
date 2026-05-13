package com.corprag.adapter.amqp;

import com.corprag.service.events.EventEnvelopeMetadata;
import java.util.Objects;
import java.util.UUID;
import org.springframework.amqp.core.Message;

final class AmqpConsumerSupport {

    private AmqpConsumerSupport() {
    }

    static EventEnvelopeMetadata requireMetadata(EventEnvelopeMetadata metadata, String expectedEventType) {
        Objects.requireNonNull(metadata, "event metadata must not be null");
        requireNonNull(metadata.eventId(), "eventId");
        requireText(metadata.eventType(), "eventType");
        if (!expectedEventType.equals(metadata.eventType())) {
            throw new IllegalArgumentException(
                    "Expected event type " + expectedEventType + " but received " + metadata.eventType());
        }
        return metadata;
    }

    static <T> T requirePayload(T payload) {
        return Objects.requireNonNull(payload, "event payload must not be null");
    }

    static UUID resolveCorrelationId(Message message, EventEnvelopeMetadata metadata) {
        UUID headerCorrelationId = parseUuid(message.getMessageProperties().getHeader(AmqpHeaderNames.CORRELATION_ID));
        if (headerCorrelationId != null) {
            return headerCorrelationId;
        }
        if (metadata != null && metadata.correlationId() != null) {
            return metadata.correlationId();
        }
        return UUID.randomUUID();
    }

    static <T> T requireNonNull(T value, String fieldName) {
        if (value == null) {
            throw new IllegalArgumentException(fieldName + " must not be null");
        }
        return value;
    }

    static String requireText(String value, String fieldName) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(fieldName + " must not be blank");
        }
        return value;
    }

    static int requireNonNegative(Integer value, String fieldName) {
        if (value == null || value < 0) {
            throw new IllegalArgumentException(fieldName + " must be non-negative");
        }
        return value;
    }

    static long requireNonNegative(Long value, String fieldName) {
        if (value == null || value < 0) {
            throw new IllegalArgumentException(fieldName + " must be non-negative");
        }
        return value;
    }

    private static UUID parseUuid(Object value) {
        if (value instanceof UUID uuid) {
            return uuid;
        }
        if (value instanceof String text && !text.isBlank()) {
            try {
                return UUID.fromString(text);
            } catch (IllegalArgumentException ignored) {
                return null;
            }
        }
        return null;
    }
}
