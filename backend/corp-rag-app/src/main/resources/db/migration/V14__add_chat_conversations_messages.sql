CREATE TABLE chat_conversations (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users (id),
    title VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CHECK (length(trim(title)) > 0),
    CHECK (updated_at >= created_at),
    CHECK (deleted_at IS NULL OR deleted_at >= created_at)
);

CREATE TABLE chat_messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES chat_conversations (id),
    role VARCHAR(16) NOT NULL,
    status VARCHAR(32),
    content TEXT,
    citations JSONB,
    retrieval_meta JSONB,
    confidence NUMERIC(4,3),
    correlation_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT chat_messages_role_check
        CHECK (role IN ('USER', 'ASSISTANT')),
    CONSTRAINT chat_messages_status_check
        CHECK (
            (role = 'USER' AND status IS NULL)
            OR (
                role = 'ASSISTANT'
                AND status IN ('ANSWERED', 'REFUSED_GUARD', 'NO_EVIDENCE', 'DEGRADED', 'TIMEOUT', 'AI_UNAVAILABLE')
            )
        ),
    CONSTRAINT chat_messages_content_check
        CHECK (
            (role = 'USER' AND content IS NOT NULL)
            OR (role = 'ASSISTANT' AND (status <> 'ANSWERED' OR content IS NOT NULL))
        ),
    CONSTRAINT chat_messages_citations_check
        CHECK (citations IS NULL OR (role = 'ASSISTANT' AND status = 'ANSWERED')),
    CONSTRAINT chat_messages_retrieval_meta_check
        CHECK (retrieval_meta IS NULL OR role = 'ASSISTANT'),
    CONSTRAINT chat_messages_confidence_check
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CHECK (deleted_at IS NULL OR deleted_at >= created_at)
);

CREATE INDEX idx_chat_conversations_user_activity
    ON chat_conversations (user_id, deleted_at, updated_at DESC);

CREATE INDEX idx_chat_messages_conversation_created
    ON chat_messages (conversation_id, deleted_at, created_at ASC);

CREATE INDEX idx_chat_messages_correlation_id
    ON chat_messages (correlation_id);
