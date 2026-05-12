CREATE TABLE permissions (
    code VARCHAR(64) PRIMARY KEY,
    description VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (code ~ '^[a-z]+(_[a-z]+)?\.[a-z]+$')
);
