CREATE TABLE processed_events (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(128) NOT NULL,
    correlation_id UUID,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_processed_events_processed_at
    ON processed_events (processed_at);

CREATE INDEX idx_processed_events_type_processed_at
    ON processed_events (event_type, processed_at);
