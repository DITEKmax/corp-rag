CREATE TABLE role_permissions (
    role_id UUID NOT NULL REFERENCES roles (id) ON DELETE CASCADE,
    permission_code VARCHAR(64) NOT NULL REFERENCES permissions (code) ON DELETE RESTRICT,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (role_id, permission_code)
);

CREATE INDEX idx_role_permissions_permission ON role_permissions (permission_code);
