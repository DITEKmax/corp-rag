CREATE TABLE documents (
    id UUID PRIMARY KEY,
    title VARCHAR(512) NOT NULL,
    description VARCHAR(1000),
    original_filename VARCHAR(512) NOT NULL,
    mime_type VARCHAR(128) NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    access_level VARCHAR(32) NOT NULL CHECK (access_level IN ('PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED')),
    department VARCHAR(64) NOT NULL CHECK (department ~ '^[A-Z][A-Z0-9_]{0,63}$'),
    doc_type VARCHAR(32) NOT NULL CHECK (doc_type IN ('POLICY', 'REGULATION', 'GUIDE', 'REPORT', 'MANUAL', 'OTHER')),
    language VARCHAR(8) NOT NULL CHECK (language IN ('ru', 'en')),
    status VARCHAR(32) NOT NULL CHECK (status IN ('UPLOADED', 'INDEXING', 'INDEXED', 'INDEXING_FAILED')),
    owner_user_id UUID REFERENCES users (id) ON DELETE SET NULL,
    storage_bucket VARCHAR(128) NOT NULL,
    storage_key VARCHAR(512) NOT NULL,
    content_sha256 CHAR(64) NOT NULL CHECK (content_sha256 ~ '^[a-f0-9]{64}$'),
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    indexed_at TIMESTAMPTZ,
    chunk_count INTEGER CHECK (chunk_count IS NULL OR chunk_count >= 0),
    failure_stage VARCHAR(64),
    failure_error_code VARCHAR(128),
    failure_message TEXT,
    failure_retryable BOOLEAN,
    failure_retry_count INTEGER CHECK (failure_retry_count IS NULL OR failure_retry_count >= 0),
    qdrant_collection VARCHAR(128),
    neo4j_entity_count INTEGER CHECK (neo4j_entity_count IS NULL OR neo4j_entity_count >= 0),
    indexing_duration_ms BIGINT CHECK (indexing_duration_ms IS NULL OR indexing_duration_ms >= 0),
    deleted_at TIMESTAMPTZ,
    deleted_by UUID REFERENCES users (id) ON DELETE SET NULL,
    CHECK ((deleted_at IS NULL AND deleted_by IS NULL) OR deleted_at IS NOT NULL)
);

CREATE UNIQUE INDEX idx_documents_sha_department_active
    ON documents (content_sha256, department)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_documents_visibility_active
    ON documents (doc_type, department, access_level)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_documents_uploaded_at_active
    ON documents (uploaded_at DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_documents_status_active
    ON documents (status)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_documents_owner_uploaded
    ON documents (owner_user_id, uploaded_at DESC)
    WHERE deleted_at IS NULL;
