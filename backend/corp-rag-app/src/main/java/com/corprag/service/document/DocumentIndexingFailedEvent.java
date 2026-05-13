package com.corprag.service.document;

import java.time.Instant;
import java.util.UUID;

public record DocumentIndexingFailedEvent(
        UUID eventId,
        UUID correlationId,
        UUID documentId,
        String stage,
        String errorCode,
        String errorMessage,
        Instant failedAt,
        boolean retryable,
        int retryCount) {
}
