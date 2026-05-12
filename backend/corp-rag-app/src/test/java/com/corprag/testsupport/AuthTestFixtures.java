package com.corprag.testsupport;

import java.util.List;
import java.util.Set;
import java.util.UUID;

public final class AuthTestFixtures {

    public static final String SESSION_COOKIE = "corp_rag_session";
    public static final String REFRESH_COOKIE = "corp_rag_refresh";
    public static final String SESSION_COOKIE_PATH = "/api/v1";
    public static final String REFRESH_COOKIE_PATH = "/api/v1/auth";

    public static final String TEST_JWT_ISSUER = "corp-rag-test";
    public static final String TEST_JWT_SECRET =
            "test-only-phase-two-hs256-secret-never-use-in-runtime";

    public static final UUID ADMIN_USER_ID = UUID.fromString("11111111-1111-4111-8111-111111111111");
    public static final UUID EMPLOYEE_USER_ID = UUID.fromString("22222222-2222-4222-8222-222222222222");
    public static final UUID VIEWER_USER_ID = UUID.fromString("33333333-3333-4333-8333-333333333333");

    public static final String ROLE_ADMIN = "ADMIN";
    public static final String ROLE_EMPLOYEE = "EMPLOYEE";
    public static final String ROLE_VIEWER = "VIEWER";

    public static final String PERMISSION_USERS_CREATE = "users.create";
    public static final String PERMISSION_USERS_READ = "users.read";
    public static final String PERMISSION_USERS_UPDATE = "users.update";
    public static final String PERMISSION_USERS_DELETE = "users.delete";
    public static final String PERMISSION_ROLES_CREATE = "roles.create";
    public static final String PERMISSION_ROLES_READ = "roles.read";
    public static final String PERMISSION_ROLES_UPDATE = "roles.update";
    public static final String PERMISSION_ROLES_DELETE = "roles.delete";
    public static final String PERMISSION_ACCESS_POLICIES_CREATE = "access_policies.create";
    public static final String PERMISSION_ACCESS_POLICIES_READ = "access_policies.read";
    public static final String PERMISSION_ACCESS_POLICIES_UPDATE = "access_policies.update";
    public static final String PERMISSION_ACCESS_POLICIES_DELETE = "access_policies.delete";
    public static final String PERMISSION_DOCUMENTS_READ = "documents.read";
    public static final String PERMISSION_DOCUMENTS_UPLOAD = "documents.upload";
    public static final String PERMISSION_DOCUMENTS_DELETE = "documents.delete";
    public static final String PERMISSION_CHAT_QUERY = "chat.query";

    public static final List<String> ALL_PERMISSIONS = List.of(
            PERMISSION_USERS_CREATE,
            PERMISSION_USERS_READ,
            PERMISSION_USERS_UPDATE,
            PERMISSION_USERS_DELETE,
            PERMISSION_ROLES_CREATE,
            PERMISSION_ROLES_READ,
            PERMISSION_ROLES_UPDATE,
            PERMISSION_ROLES_DELETE,
            PERMISSION_ACCESS_POLICIES_CREATE,
            PERMISSION_ACCESS_POLICIES_READ,
            PERMISSION_ACCESS_POLICIES_UPDATE,
            PERMISSION_ACCESS_POLICIES_DELETE,
            PERMISSION_DOCUMENTS_READ,
            PERMISSION_DOCUMENTS_UPLOAD,
            PERMISSION_DOCUMENTS_DELETE,
            PERMISSION_CHAT_QUERY);

    public static final Set<String> ADMIN_PERMISSIONS = Set.copyOf(ALL_PERMISSIONS);
    public static final Set<String> EMPLOYEE_PERMISSIONS = Set.of(
            PERMISSION_CHAT_QUERY,
            PERMISSION_DOCUMENTS_READ,
            PERMISSION_DOCUMENTS_UPLOAD,
            PERMISSION_USERS_READ);
    public static final Set<String> VIEWER_PERMISSIONS = Set.of(PERMISSION_CHAT_QUERY, PERMISSION_DOCUMENTS_READ);

    public static final List<String> ACCESS_LEVELS =
            List.of("PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED");
    public static final List<String> DOC_TYPES =
            List.of("POLICY", "REGULATION", "GUIDE", "REPORT", "MANUAL", "OTHER");
    public static final String DEPARTMENT_HR = "HR";
    public static final String DEPARTMENT_IT = "IT";
    public static final String DEPARTMENT_FINANCE = "FINANCE";

    public static final TestUser ADMIN = new TestUser(
            ADMIN_USER_ID,
            "admin.test",
            "Admin Test",
            "admin.test@example.com",
            DEPARTMENT_IT,
            List.of(ROLE_ADMIN));
    public static final TestUser EMPLOYEE = new TestUser(
            EMPLOYEE_USER_ID,
            "employee.test",
            "Employee Test",
            "employee.test@example.com",
            DEPARTMENT_HR,
            List.of(ROLE_EMPLOYEE));
    public static final TestUser VIEWER = new TestUser(
            VIEWER_USER_ID,
            "viewer.test",
            "Viewer Test",
            "viewer.test@example.com",
            DEPARTMENT_FINANCE,
            List.of(ROLE_VIEWER));

    private AuthTestFixtures() {
    }

    public record TestUser(
            UUID id,
            String username,
            String fullName,
            String email,
            String department,
            List<String> roles) {
    }
}
