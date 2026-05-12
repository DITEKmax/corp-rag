---
phase: "02-identity-users-access-control"
plan: "04"
subsystem: auth
tags: [spring-security, jwt, cookies, refresh-rotation, csrf-origin, testcontainers]
requires:
  - phase: "02-identity-users-access-control"
    provides: "PostgreSQL identity repositories and seed data from Plan 02-03"
provides:
  - "Spring Security resource-server wiring with JWT-from-cookie authentication"
  - "HS256 JWT issuing/validation with configured secret handling"
  - "Origin/Referer validation for unsafe cookie-authenticated API requests"
  - "Database-backed login, refresh rotation, refresh-token reuse detection, /me, and logout"
  - "Auth flow coverage across unit tests and PostgreSQL integration tests"
affects: ["02-identity-users-access-control", "java-backend", "auth", "security"]
tech-stack:
  added: []
  patterns: ["CookieBearerTokenResolver for corp_rag_session", "ProblemDetail writer reused by filters and MVC advice", "Refresh-token family revocation on reuse"]
key-files:
  created:
    - "backend/corp-rag-app/src/main/java/com/corprag/config/SecurityConfig.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/security"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/auth"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/audit/AuditEventWriter.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/AuthController.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/service/auth/AuthFlowIT.java"
  modified:
    - "backend/corp-rag-app/src/main/resources/application.yml"
    - "backend/corp-rag-app/src/main/resources/application-prod.yml"
    - "backend/corp-rag-app/src/main/java/com/corprag/repository/RefreshTokenRepository.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/repository/RoleRepository.java"
key-decisions:
  - "Used NimbusJwtEncoder and NimbusJwtDecoder.withSecretKey for self-issued HS256 tokens; no issuer-location discovery is used."
  - "Kept Spring CsrfFilter disabled and enforced unsafe cookie-authenticated requests through Origin/Referer validation."
  - "Preserved refresh-token family revocation on reuse by preventing transactional rollback for ApiProblemException in refresh paths."
patterns-established:
  - "Auth/security failures return generated ProblemDetail bodies with contract error codes."
  - "Auth integration tests seed users directly through repositories and run only under Failsafe/Testcontainers."
requirements-completed: ["AUTH-01", "AUTH-03"]
duration: "13 min"
completed: "2026-05-12"
---

# Phase 02 Plan 04: Authentication Session Summary

**Cookie-based JWT sessions with opaque refresh-token rotation, reuse revocation, and Origin/Referer request guards**

## Performance

- **Duration:** 13 min
- **Started:** 2026-05-12T05:13:00Z
- **Completed:** 2026-05-12T05:26:30Z
- **Tasks:** 3
- **Files modified:** 23

## Accomplishments

- Added Spring Security configuration for stateless resource-server JWT validation from `corp_rag_session`.
- Added HS256 JWT issuing with configured secret validation, random dev secret fallback, and prod fail-fast behavior.
- Added `OriginRefererValidationFilter` for unsafe `/api/v1/**` cookie-authenticated requests while keeping Spring CSRF disabled.
- Implemented login, refresh rotation, `/me`, logout, cookie set/clear behavior, session limit eviction, refresh reuse detection, and auth audit writes.
- Added unit tests for JWT, cookie resolution, origin guard behavior, and integration tests for full auth flows against PostgreSQL.

## Task Commits

1. **Task 1: Configure Spring Security, JWT, cookies, and request guards** - `0253572` (feat)
2. **Task 2: Implement login, refresh rotation, `/me`, and logout** - `4dbc7cd` (feat)
3. **Task 3: Cover auth security behavior with tests** - `42f3b6e` (test)

**Plan metadata:** this summary commit

## Files Created/Modified

- `backend/corp-rag-app/src/main/java/com/corprag/config/SecurityConfig.java` - Stateless security chain, JWT beans, BCrypt, CSRF disabled, ProblemDetail handlers.
- `backend/corp-rag-app/src/main/java/com/corprag/security` - Cookie bearer resolver, Origin/Referer filter, JWT issuer.
- `backend/corp-rag-app/src/main/java/com/corprag/service/auth` - Login, refresh, logout, session limit, and refresh-token rotation services.
- `backend/corp-rag-app/src/main/java/com/corprag/service/audit/AuditEventWriter.java` - Auth audit event abstraction.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/AuthController.java` - `/auth/login`, `/auth/refresh`, `/me`, and `/auth/logout`.
- `backend/corp-rag-app/src/test/java/com/corprag/service/auth/AuthFlowIT.java` - End-to-end auth flow with Testcontainers PostgreSQL.

## Deviations from Plan

### Auto-fixed Issues

**1. Refresh reuse revocation rollback**
- **Found during:** Task 3 (AuthFlowIT)
- **Issue:** Reuse detection revoked the token family and then threw `ApiProblemException`; the transaction rolled the revocation back.
- **Fix:** Marked refresh transactions with `noRollbackFor = ApiProblemException.class`.
- **Files modified:** `AuthService.java`, `RefreshTokenService.java`
- **Verification:** `cd backend; mvn -q -pl corp-rag-app -am verify` passed.
- **Committed in:** `42f3b6e`

---

**Total deviations:** 1 auto-fixed correctness issue
**Impact on plan:** Required to satisfy the planned reuse-detection security behavior.

## Issues Encountered

- JWT expiration values are second-precision after encode/decode, so `JwtService` now truncates issued timestamps to seconds.

## Verification

- `cd backend; mvn -q -pl corp-rag-app -am test` - passed.
- `cd backend; mvn -q -pl corp-rag-app -am verify` - passed.

## User Setup Required

None - no external service configuration required. `JWT_SECRET` is required in prod and can be omitted in dev, where a random startup secret is generated.

## Next Phase Readiness

Plan 02-05 can build user, role, and password administration on the authenticated principal, persisted roles/permissions, BCrypt password verification, and the existing ProblemDetail/security infrastructure.

---
*Phase: 02-identity-users-access-control*
*Completed: 2026-05-12*
