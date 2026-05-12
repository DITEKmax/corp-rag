---
phase: "02-identity-users-access-control"
plan: "07"
subsystem: auth
tags: [access-policies, access-filter, audit, rbac, spring-security, testcontainers]
requires:
  - phase: "02-identity-users-access-control"
    provides: "User lifecycle, password lifecycle, roles, permissions, and user-role assignment from Plans 02-05 and 02-06"
provides:
  - "Access policy administration API with role uniqueness, ETag replacement, validation, and last-admin visibility safeguards"
  - "Resolved user AccessFilter values with PUBLIC visibility, hierarchy expansion, wildcard department semantics, and cache eviction"
  - "Java-to-Python QueryRequest AccessFilter mapper compatible with the generated AI service contract"
  - "Audit integration for Phase 2 auth, user, role, and access-policy changes"
  - "Full Phase 2 identity/access-control flow coverage under Maven verify"
affects: ["02-identity-users-access-control", "03-documents-events-audit", "java-backend", "auth", "audit", "retrieval-access"]
tech-stack:
  added: []
  patterns: ["Service-owned access policy rules", "Resolved access filters cached by user/security version", "Singleton PostgreSQL Testcontainer for Spring context cache compatibility"]
key-files:
  created:
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/AccessPolicyController.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/QueryAccessFilterMapper.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/access/AccessFilterCache.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/access/AccessFilterCacheInvalidator.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/access/AccessFilterResolver.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/access/AccessPolicyService.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/IdentityAccessFlowIT.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/AccessPolicyControllerTest.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/QueryAccessFilterMapperTest.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/service/access/AccessFilterResolverTest.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/service/access/AccessPolicyServiceTest.java"
  modified:
    - "backend/corp-rag-app/src/main/java/com/corprag/repository/AccessPolicyRepository.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/repository/AuditEventRepository.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/audit/AuditEventWriter.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/role/RoleService.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/user/UserService.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/testsupport/PostgresIntegrationTestSupport.java"
key-decisions:
  - "Access policy business rules live in AccessPolicyService; controllers authorize and map contract models."
  - "ResolvedAccessFilter always includes PUBLIC and fails closed for non-public visibility when no role policy applies."
  - "Generic mutation audit events join the caller transaction; auth audit remains independent where required."
  - "PostgreSQL Testcontainers use a JVM-lifetime singleton to stay compatible with Spring context caching."
patterns-established:
  - "Policy mutations evict resolved access filters after role or policy state changes."
  - "Access level hierarchy expands downward for downstream retrieval filters."
  - "Missing audit actor/target users are nulled at insert time to preserve nullable FK semantics."
requirements-completed: ["AUTH-01", "AUTH-02", "AUTH-03", "AUTH-04"]
duration: "29 min active execution plus resumed verification"
completed: "2026-05-12"
---

# Phase 02 Plan 07: Access Policies, Access Filters, Audit, And Full Flow Summary

**Role-scoped document visibility policies with cached Java AccessFilter resolution and Phase 2 audit-backed end-to-end validation**

## Performance

- **Duration:** 29 min active execution plus resumed verification
- **Started:** 2026-05-12T06:07:00Z
- **Completed:** 2026-05-12T09:17:46Z
- **Tasks:** 3
- **Files modified:** 22 code/test files plus planning docs

## Accomplishments

- Added `/api/v1/access-policies` administration with one-policy-per-role enforcement, full replacement through ETag/If-Match, system-role edit safeguards, validation, cache eviction, and audit events.
- Added `AccessFilterResolver`, cache support, and the generated-contract mapper for Python `QueryRequest.accessFilter`.
- Integrated audit events across Phase 2 auth, user, role, access-policy, and password flows while preserving transaction semantics.
- Added focused service/controller/mapper/audit tests plus `IdentityAccessFlowIT` for the complete Phase 2 admin and access-control path.
- Stabilized PostgreSQL Testcontainers so full `mvn verify` runs integration tests under Spring context caching instead of reusing stopped container URLs.

## Task Commits

1. **Task 1: Implement access-policy administration** - `90b2dd5` (feat)
2. **Task 2: Resolve and cache user AccessFilter values** - `90b2dd5` (feat)
3. **Task 3: Integrate audit logging and full Phase 2 flow tests** - `70ed818` (test)
4. **Verification fix: Stabilize PostgreSQL integration tests** - `9c03197` (test)

**Pause handoff:** `aa29d8c` documented the interrupted final verification.
**Plan metadata:** this summary commit.

## Deviations from Plan

### Auto-fixed Issues

**1. Spring context cache reused a stopped Testcontainers JDBC URL**
- **Found during:** Final `mvn verify` with Docker access.
- **Issue:** The shared `PostgresIntegrationTestSupport` used a static `@Container`. Testcontainers stopped the container between classes while Spring reused a cached context with the old JDBC URL.
- **Fix:** Started the PostgreSQL container from `DynamicPropertySource` as a JVM-lifetime singleton and let Spring contexts reuse a stable JDBC URL.
- **Files modified:** `backend/corp-rag-app/src/test/java/com/corprag/testsupport/PostgresIntegrationTestSupport.java`
- **Verification:** `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am verify` passed with Failsafe ITs executed and skipped count 0.
- **Committed in:** `9c03197`

---

**Total deviations:** 1 auto-fixed test infrastructure issue.
**Impact on plan:** No product scope change. The fix made the planned final verification meaningful and repeatable.

## Issues Encountered

- Running Maven inside the restricted sandbox made Testcontainers unable to see Docker, causing integration tests to be skipped while Maven still exited 0. The final accepted verification was rerun with Docker access and all Failsafe tests executed.

## User Setup Required

None for application configuration. Full backend verification requires Docker Desktop/Testcontainers access.

## Next Phase Readiness

- Phase 3 can rely on Java-owned users, roles, permissions, access policies, access-filter resolution, and the durable `audit_events` table.
- Later document and retrieval work should pass the resolved AccessFilter downstream before exposing document chunks or citations.
- Later audit work can extend the existing audit table and writer with document, indexing, chat, and guard event categories.

---
*Phase: 02-identity-users-access-control*
*Completed: 2026-05-12*
