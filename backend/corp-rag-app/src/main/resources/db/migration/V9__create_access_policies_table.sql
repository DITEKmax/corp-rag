CREATE TABLE access_policies (
    id UUID PRIMARY KEY,
    role_id UUID NOT NULL UNIQUE REFERENCES roles (id) ON DELETE CASCADE,
    access_levels TEXT[] NOT NULL,
    departments TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    doc_types TEXT[] NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version BIGINT NOT NULL DEFAULT 0,
    CHECK (cardinality(access_levels) > 0),
    CHECK (access_levels <@ ARRAY['PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED']::TEXT[]),
    CHECK (cardinality(doc_types) > 0),
    CHECK (doc_types <@ ARRAY['POLICY', 'REGULATION', 'GUIDE', 'REPORT', 'MANUAL', 'OTHER']::TEXT[])
);

CREATE INDEX idx_access_policies_role ON access_policies (role_id);
