---
phase: "02-identity-users-access-control"
plan: "06"
subsystem: auth
tags: [roles, permissions, rbac, etag, spring-security, audit]
requires:
  - phase: "02-identity-users-access-control"
    provides: "Authenticated cookie/JWT session boundary and identity repositories from Plans 02-03 and 02-04"
provides:
  - "Authoritative Java permission enum matching the exact 16 Phase 2 dotted permission codes"
  - "Repository-backed permission evaluator and system role matrix coverage"
  - "Role CRUD APIs with ETag-protected full replacement and system-role protection"
  - "User role replace-set API with ADMIN double gate, self-modification block, last-admin protection, and audit event"
affects: ["02-identity-users-access-control", "java-backend", "auth", "roles", "permissions", "access-policies"]
tech-stack:
  added: []
  patterns: ["JWT permission checks in controllers", "ETag parser using role-v{version}", "Service-owned RBAC mutation rules with repository-backed permission checks"]
key-files:
  created:
    - "backend/corp-rag-app/src/main/java/com/corprag/security/Permission.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/security/PermissionEvaluator.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/role/RoleService.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/RoleController.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/UserRoleController.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/security/RolePermissionMatrixTest.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/RoleControllerTest.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/UserRoleControllerTest.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/service/role/RoleServiceTest.java"
  modified:
    - "backend/corp-rag-app/src/main/java/com/corprag/repository/RoleRepository.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/audit/AuditEventWriter.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/ProblemDetailsExceptionHandler.java"
key-decisions:
  - "Moved the permission enum from domain to security so the authorization surface owns the single Java permission list."
  - "Role ETags use the contract example format `\"role-v{version}\"` and stale/malformed values return PRECONDITION_FAILED."
  - "User-role assignment uses JWT permissions for the caller gate and repository state for last-admin protection."
patterns-established:
  - "Role mutations validate permissions through PermissionEvaluator before repository writes."
  - "Generated enum parse failures for PermissionCode are mapped to INVALID_PERMISSION_CODE."
  - "Business-rule-heavy controller flows use service unit tests plus focused controller mapping tests to avoid extra Testcontainers context churn."
requirements-completed: ["AUTH-02", "AUTH-03"]
duration: "28 min"
completed: "2026-05-12"
---

# Phase 02 Plan 06: Roles, Permissions, And User Role Assignment Summary

**RBAC administration with exact permission constants, ETag-protected role replacement, and safe replace-set user role assignment**

## Performance

- **Duration:** 28 min
- **Started:** 2026-05-12T05:38:00Z
- **Completed:** 2026-05-12T06:06:00Z
- **Tasks:** 3
- **Files modified:** 15

## Accomplishments

- Added `Permission` constants and `PermissionEvaluator` for the exact Phase 2 permission surface and repository-backed effective permission checks.
- Added role list/create/get/update/delete APIs, including full replacement, response ETags, missing/stale If-Match handling, system-role protection, assigned-role delete protection, and invalid permission mapping.
- Added `POST /users/{userId}/roles` replace-set assignment with `users.update`, ADMIN `roles.update` double gate, self-modification block, last-admin protection, and one audit event per successful diff.
- Added matrix, service, and controller coverage for seeded role permissions, permission union, role ETags, invalid permission codes, and user-role safety rules.

## Task Commits

1. **Task 1: Permission constants and route authorization helpers** - `33efb32` (feat)
2. **Task 2: Role CRUD with ETag full replacement** - `6a640d0` (feat)
3. **Task 3: User role replace-set assignment rules** - `1cfc76c` (feat)

**Plan metadata:** this summary commit

## Deviations from Plan

### Auto-fixed Issues

**1. Test role names violated the OpenAPI role-name pattern**
- **Found during:** Task 2 verification
- **Issue:** Random test suffixes included digits, while role names are constrained to `^[A-Z_]+$`.
- **Fix:** Adjusted test suffix generation to emit letter-only role names.
- **Verification:** `cd backend; mvn -q -pl corp-rag-app -am test` passed.
- **Committed in:** `6a640d0`

**2. Extra Spring/Testcontainers controller class reused a stopped container-backed context**
- **Found during:** Task 3 targeted verification
- **Issue:** Adding a second Spring controller integration class with the same context signature caused Hikari to reuse a dead Testcontainers JDBC URL.
- **Fix:** Kept `RoleControllerTest` as the database-backed route test, converted `UserRoleControllerTest` to a direct controller test, and expanded `RoleServiceTest` for replace-set business rules.
- **Verification:** Targeted role tests, full `mvn test`, and full `mvn verify` passed.
- **Committed in:** `1cfc76c`

---

**Total deviations:** 2 auto-fixed (test data contract, test context isolation)
**Impact on plan:** No product scope change; fixes kept the planned behaviors covered without adding new runtime dependencies.

## Issues Encountered

- Generated `PermissionCode` deserialization throws before controller code for unknown strings; `ProblemDetailsExceptionHandler` now maps those parse failures to `INVALID_PERMISSION_CODE`.
- Spring context caching with inherited Testcontainers requires care when adding multiple similar `@SpringBootTest` classes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Role membership and permission checks are ready for access policy resolution and document visibility filters.
- Access policy work can reuse `RoleRepository.findPermissionsForUser`, `findRolesForUser`, and role-based user lookup patterns for cache invalidation.

---
*Phase: 02-identity-users-access-control*
*Completed: 2026-05-12*
