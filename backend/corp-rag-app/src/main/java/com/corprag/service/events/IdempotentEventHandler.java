package com.corprag.service.events;

@FunctionalInterface
public interface IdempotentEventHandler {

    void handle();
}
