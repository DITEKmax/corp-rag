---
phase: "02-identity-users-access-control"
plan: "02"
subsystem: testing
tags: [spring-security, oauth2-resource-server, testcontainers, postgres, maven]
requires:
  - phase: "02-identity-users-access-control"
    provides: "Phase 2 contract-first identity surface from Plan 02-01"
provides:
  - "Spring Security and OAuth2 resource-server dependency surface"
  - "Surefire/Failsafe split for Docker-free quick tests and Testcontainers integration tests"
  - "Reusable auth fixtures and PostgreSQL integration-test support"
affects: ["02-identity-users-access-control", "java-backend", "testing"]
tech-stack:
  added:
    - "spring-boot-starter-security"
    - "spring-boot-starter-oauth2-resource-server"
    - "spring-security-test"
    - "spring-boot-testcontainers"
    - "testcontainers-junit-jupiter"
    - "testcontainers-postgresql"
  patterns: ["Docker-free mvn test with *IT integration tests under mvn verify"]
key-files:
  created:
    - "backend/corp-rag-app/src/test/java/com/corprag/SecurityDependencySmokeTest.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/testsupport/AuthTestFixtures.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/testsupport/PostgresIntegrationTestSupport.java"
  modified:
    - "backend/pom.xml"
    - "backend/corp-rag-app/pom.xml"
key-decisions:
  - "Used Spring Security OAuth2 Resource Server primitives for Phase 2 JWT support."
  - "Kept PostgreSQL/Testcontainers tests on the Failsafe verify path so mvn test remains Docker-free."
patterns-established:
  - "Phase 2 auth tests reuse deterministic test-only fixtures rather than production defaults."
  - "Migration-backed PostgreSQL integration tests should subclass PostgresIntegrationTestSupport."
requirements-completed: ["AUTH-01", "AUTH-02", "AUTH-03", "AUTH-04"]
duration: "5 min"
completed: "2026-05-12"
---

# Phase 02 Plan 02: Backend Test Harness Summary

**Spring Security JWT dependencies, Failsafe integration-test wiring, and reusable Phase 2 auth/PostgreSQL test fixtures**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-12T04:54:10Z
- **Completed:** 2026-05-12T04:59:19Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added Spring Security, OAuth2 resource-server, Spring Security Test, Spring Boot Testcontainers, and PostgreSQL Testcontainers support.
- Added Maven Failsafe configuration so `*IT` tests run during `mvn verify` while quick unit/slice tests stay in `mvn test`.
- Added deterministic test-only auth fixtures for users, roles, permission strings, cookies, access levels, departments, and doc types.
- Added PostgreSQL Testcontainers wiring with `DynamicPropertySource`.
- Added a smoke test proving Spring Security JWT classes, security-test support, Testcontainers, and fixtures are available.

## Task Commits

1. **Task 1: Add Phase 2 security and integration-test dependencies** - `5fdcb92` (build)
2. **Task 2: Add reusable Phase 2 test support** - `ed2e647` (test)

**Plan metadata:** this summary commit

## Files Created/Modified

- `backend/pom.xml` - Adds Failsafe plugin management and integration-test binding.
- `backend/corp-rag-app/pom.xml` - Adds Phase 2 security/JWT/test dependencies and Failsafe plugin.
- `backend/corp-rag-app/src/test/java/com/corprag/testsupport/AuthTestFixtures.java` - Provides deterministic test-only auth and access-control constants.
- `backend/corp-rag-app/src/test/java/com/corprag/testsupport/PostgresIntegrationTestSupport.java` - Provides shared PostgreSQL Testcontainers property wiring.
- `backend/corp-rag-app/src/test/java/com/corprag/SecurityDependencySmokeTest.java` - Verifies dependency and fixture availability.

## Decisions Made

- Used managed Spring Boot dependency versions wherever possible.
- Did not add auth endpoints, domain schema, migrations, or business behavior in this setup plan.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Initial smoke assertion expected Testcontainers' canonical image name to include `docker.io/library`; the API returned `postgres:16-alpine`. The assertion was corrected before the task commit.

## Verification

- `cd backend; mvn -q -pl corp-rag-app -am test` - passed after Task 1.
- `cd backend; mvn -q -pl corp-rag-app -am test` - passed after Task 2.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 02-03 can add migration-backed repository/integration tests using the shared PostgreSQL Testcontainers base, and later auth plans can reuse the security fixtures without duplicating secrets or permission constants.

---
*Phase: 02-identity-users-access-control*
*Completed: 2026-05-12*
