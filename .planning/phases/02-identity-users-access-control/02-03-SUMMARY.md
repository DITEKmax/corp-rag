---
phase: "02-identity-users-access-control"
plan: "03"
subsystem: database
tags: [postgres, flyway, jdbc, identity, access-control, testcontainers]
requires:
  - phase: "02-identity-users-access-control"
    provides: "Phase 2 backend test harness and PostgreSQL Testcontainers support from Plan 02-02"
provides:
  - "PostgreSQL identity schema for users, refresh tokens, audit events, roles, permissions, role assignments, and access policies"
  - "Idempotent seed data for the exact Phase 2 permission and system-role matrix"
  - "Domain records/enums and JDBC repositories for later auth, user, role, policy, and audit services"
  - "Migration-backed PostgreSQL integration coverage for schema, seed data, constraints, and repository behavior"
affects: ["02-identity-users-access-control", "java-backend", "database", "auth", "authorization"]
tech-stack:
  added: []
  patterns: ["Flyway V2-V10 identity migrations", "JdbcClient repositories with explicit Optional results", "PostgreSQL-backed *IT verification"]
key-files:
  created:
    - "backend/corp-rag-app/src/main/resources/db/migration/V2__create_users_table.sql"
    - "backend/corp-rag-app/src/main/resources/db/migration/V10__seed_identity_defaults.sql"
    - "backend/corp-rag-app/src/main/java/com/corprag/domain"
    - "backend/corp-rag-app/src/main/java/com/corprag/repository"
    - "backend/corp-rag-app/src/test/java/com/corprag/repository/IdentitySchemaIT.java"
  modified:
    - "backend/pom.xml"
key-decisions:
  - "Persisted access policy scopes as PostgreSQL TEXT[] arrays with database checks for access-level and doc-type enums."
  - "Kept empty departments as the wildcard/all-departments representation required by Phase 2 decisions."
  - "Converted Instant values to Timestamp at repository write boundaries for PostgreSQL driver compatibility."
patterns-established:
  - "Repository writes must preserve optimistic version columns and return boolean results for version-checked updates."
  - "Migration-backed persistence tests should assert seed invariants and repository behavior against PostgreSQL, not H2."
requirements-completed: ["AUTH-01", "AUTH-02", "AUTH-03", "AUTH-04"]
duration: "13 min"
completed: "2026-05-12"
---

# Phase 02 Plan 03: Identity Persistence Summary

**PostgreSQL identity schema with seeded RBAC/access policies and JDBC repositories verified through Testcontainers**

## Performance

- **Duration:** 13 min
- **Started:** 2026-05-12T04:59:20Z
- **Completed:** 2026-05-12T05:12:54Z
- **Tasks:** 3
- **Files modified:** 30

## Accomplishments

- Added Flyway migrations V2-V10 for users, refresh tokens, audit events, permissions, roles, role permissions, user roles, access policies, and identity seed data.
- Seeded the exact 16 permission strings, ADMIN/EMPLOYEE/VIEWER system roles, the Phase 2 role-permission matrix, and default role access policies.
- Added domain records/enums and JDBC repositories for identity, refresh-token, audit, role, user-role, and access-policy persistence.
- Added `IdentitySchemaIT` to verify schema existence, seed correctness, uniqueness/check constraints, version checks, refresh-token rotation/revocation, audit outcomes, and access-policy resolution against PostgreSQL.

## Task Commits

1. **Task 1: Add Phase 2 Flyway migrations and seed data** - `f73ab0f` (feat)
2. **Task 2: Implement domain records and JDBC repositories** - `4912ea0` (feat)
3. **Task 3: Verify schema and repository behavior with PostgreSQL** - `0d75b23` (test)

**Plan metadata:** this summary commit

## Files Created/Modified

- `backend/corp-rag-app/src/main/resources/db/migration/V2__create_users_table.sql` through `V10__seed_identity_defaults.sql` - Defines identity schema and idempotent seeds.
- `backend/corp-rag-app/src/main/java/com/corprag/domain` - Adds identity/access-control domain records and enums.
- `backend/corp-rag-app/src/main/java/com/corprag/repository` - Adds JDBC repositories for users, refresh tokens, audit events, roles, user roles, and access policies.
- `backend/corp-rag-app/src/test/java/com/corprag/repository/IdentitySchemaIT.java` - Verifies migrations and repositories against PostgreSQL.
- `backend/pom.xml` - Pins Failsafe to `target/classes` so Spring Boot repackaging does not hide app classes from integration-test discovery.

## Decisions Made

- Used database-level checks for access-level and doc-type arrays so invalid policy scopes fail before service logic.
- Modeled department wildcard as an empty persisted array, matching the OpenAPI/AI-service contract semantics.
- Kept repositories small and domain-specific, returning `Optional` for nullable reads and boolean results for optimistic concurrency failures.

## Deviations from Plan

### Auto-fixed Issues

**1. Failsafe classpath after Spring Boot repackage**
- **Found during:** Task 3 (PostgreSQL integration verification)
- **Issue:** Failsafe could not discover `IdentitySchemaIT` because main classes were not visible after Spring Boot repackaging.
- **Fix:** Set `maven-failsafe-plugin` `classesDirectory` to `${project.build.outputDirectory}`.
- **Files modified:** `backend/pom.xml`
- **Verification:** `cd backend; mvn -q -pl corp-rag-app -am verify` passed.
- **Committed in:** `0d75b23`

**2. PostgreSQL Instant parameter binding**
- **Found during:** Task 3 (repository round-trip test)
- **Issue:** PostgreSQL JDBC could not infer SQL types for `java.time.Instant` named parameters.
- **Fix:** Added `JdbcRowSupport.timestamp` and converted repository timestamp writes to `java.sql.Timestamp`.
- **Files modified:** `backend/corp-rag-app/src/main/java/com/corprag/repository`
- **Verification:** `cd backend; mvn -q -pl corp-rag-app -am verify` passed.
- **Committed in:** `0d75b23`

---

**Total deviations:** 2 auto-fixed blocking issues
**Impact on plan:** Both fixes were required for the planned PostgreSQL integration verification. No scope expansion.

## Issues Encountered

- Testcontainers pulled `testcontainers/ryuk:0.7.0` on first run, then successfully started `postgres:16-alpine`.
- PostgreSQL migrations validated and applied cleanly through V10.

## Verification

- `cd backend; mvn -q -pl corp-rag-app -am test` - passed after repository implementation.
- `cd backend; mvn -q -pl corp-rag-app -am verify` - passed after integration test and repository write fixes.

## User Setup Required

None - no external service configuration required beyond Docker for local `mvn verify`.

## Next Phase Readiness

Plan 02-04 can build auth services on persisted users, refresh-token sessions, versioned role/policy repositories, and audit-event insertion. Later access-filter logic can consume the role policy data already validated by `IdentitySchemaIT`.

---
*Phase: 02-identity-users-access-control*
*Completed: 2026-05-12*
