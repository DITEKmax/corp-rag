INSERT INTO permissions (code, description) VALUES
    ('users.create', 'Create users'),
    ('users.read', 'Read users'),
    ('users.update', 'Update users'),
    ('users.delete', 'Delete users'),
    ('roles.create', 'Create roles'),
    ('roles.read', 'Read roles'),
    ('roles.update', 'Update roles'),
    ('roles.delete', 'Delete roles'),
    ('access_policies.create', 'Create access policies'),
    ('access_policies.read', 'Read access policies'),
    ('access_policies.update', 'Update access policies'),
    ('access_policies.delete', 'Delete access policies'),
    ('documents.read', 'Read documents'),
    ('documents.upload', 'Upload documents'),
    ('documents.delete', 'Delete documents'),
    ('chat.query', 'Run chat queries')
ON CONFLICT (code) DO NOTHING;

INSERT INTO roles (id, code, description, is_system) VALUES
    ('00000000-0000-4000-8000-000000000001', 'ADMIN', 'System administrator', TRUE),
    ('00000000-0000-4000-8000-000000000002', 'EMPLOYEE', 'Default employee role', TRUE),
    ('00000000-0000-4000-8000-000000000003', 'VIEWER', 'Read-only viewer role', TRUE)
ON CONFLICT (code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM roles r
CROSS JOIN permissions p
WHERE r.code = 'ADMIN'
ON CONFLICT (role_id, permission_code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM roles r
JOIN permissions p ON p.code IN ('chat.query', 'documents.read', 'documents.upload', 'users.read')
WHERE r.code = 'EMPLOYEE'
ON CONFLICT (role_id, permission_code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_code)
SELECT r.id, p.code
FROM roles r
JOIN permissions p ON p.code IN ('chat.query', 'documents.read')
WHERE r.code = 'VIEWER'
ON CONFLICT (role_id, permission_code) DO NOTHING;

INSERT INTO access_policies (id, role_id, access_levels, departments, doc_types)
SELECT
    '00000000-0000-4000-9000-000000000001',
    r.id,
    ARRAY['PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'RESTRICTED']::TEXT[],
    ARRAY[]::TEXT[],
    ARRAY['POLICY', 'REGULATION', 'GUIDE', 'REPORT', 'MANUAL', 'OTHER']::TEXT[]
FROM roles r
WHERE r.code = 'ADMIN'
ON CONFLICT (role_id) DO NOTHING;

INSERT INTO access_policies (id, role_id, access_levels, departments, doc_types)
SELECT
    '00000000-0000-4000-9000-000000000002',
    r.id,
    ARRAY['PUBLIC', 'INTERNAL']::TEXT[],
    ARRAY[]::TEXT[],
    ARRAY['POLICY', 'REGULATION', 'GUIDE', 'REPORT', 'MANUAL', 'OTHER']::TEXT[]
FROM roles r
WHERE r.code = 'EMPLOYEE'
ON CONFLICT (role_id) DO NOTHING;

INSERT INTO access_policies (id, role_id, access_levels, departments, doc_types)
SELECT
    '00000000-0000-4000-9000-000000000003',
    r.id,
    ARRAY['PUBLIC']::TEXT[],
    ARRAY[]::TEXT[],
    ARRAY['POLICY', 'REGULATION', 'GUIDE', 'MANUAL', 'OTHER']::TEXT[]
FROM roles r
WHERE r.code = 'VIEWER'
ON CONFLICT (role_id) DO NOTHING;
