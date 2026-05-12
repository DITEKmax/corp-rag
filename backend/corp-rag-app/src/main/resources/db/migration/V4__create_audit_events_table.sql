CREATE TABLE audit_events (
    id UUID PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_category VARCHAR(64) NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    outcome VARCHAR(16) NOT NULL CHECK (outcome IN ('SUCCESS', 'FAILURE', 'ERROR')),
    actor_user_id UUID REFERENCES users (id) ON DELETE SET NULL,
    target_user_id UUID REFERENCES users (id) ON DELETE SET NULL,
    entity_type VARCHAR(64),
    entity_id UUID,
    ip_address VARCHAR(45),
    user_agent VARCHAR(512),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    correlation_id UUID
);

CREATE INDEX idx_audit_events_actor_time ON audit_events (actor_user_id, occurred_at DESC);
CREATE INDEX idx_audit_events_target_time ON audit_events (target_user_id, occurred_at DESC);
CREATE INDEX idx_audit_events_category_type_time ON audit_events (event_category, event_type, occurred_at DESC);
CREATE INDEX idx_audit_events_entity_time ON audit_events (entity_type, entity_id, occurred_at DESC);
