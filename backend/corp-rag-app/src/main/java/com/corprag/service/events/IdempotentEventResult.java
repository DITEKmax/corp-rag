package com.corprag.service.events;

import java.util.UUID;

public record IdempotentEventResult(UUID eventId, Status status) {

    public static IdempotentEventResult processed(UUID eventId) {
        return new IdempotentEventResult(eventId, Status.PROCESSED);
    }

    public static IdempotentEventResult duplicate(UUID eventId) {
        return new IdempotentEventResult(eventId, Status.DUPLICATE);
    }

    public boolean processed() {
        return status == Status.PROCESSED;
    }

    public boolean duplicate() {
        return status == Status.DUPLICATE;
    }

    public enum Status {
        PROCESSED,
        DUPLICATE
    }
}
