---
phase: 02
slug: identity-users-access-control
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-12
---

# Phase 02 - Validation Strategy

Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | JUnit Jupiter, Spring Boot Test, Spring Security Test, Maven Surefire, Maven Failsafe, Testcontainers PostgreSQL |
| **Config file** | `backend/pom.xml`, `backend/corp-rag-app/pom.xml` |
| **Quick run command** | `cd backend; mvn -q -pl corp-rag-app -am test` |
| **Full suite command** | `cd backend; mvn -q -pl corp-rag-app -am verify` |
| **Estimated runtime** | Quick suite under 30 seconds after dependencies resolve; full suite depends on Docker/Testcontainers startup |

## Sampling Rate

- **After every task commit:** Run `cd backend; mvn -q -pl corp-rag-app -am test`
- **After every plan wave:** Run `cd backend; mvn -q -pl corp-rag-app -am verify`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds for quick unit/slice checks; integration feedback is wave-gated

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-prereq | 01 | 1 | AUTH-01, AUTH-02, AUTH-03, AUTH-04 | T-02-01-01 / T-02-01-02 / T-02-01-03 | Contract, constants, and AccessFilter schemas are verified before Java implementation. | contract/build | `python scripts/verify-contracts.py` | planned | ready |
| 02-02-prereq | 02 | 2 | AUTH-01, AUTH-02, AUTH-03, AUTH-04 | T-02-02-01 / T-02-02-02 / T-02-02-03 | Security dependencies, Surefire/Failsafe split, security fixtures, and Testcontainers support exist before behavior tests depend on them. | build/smoke | `cd backend; mvn -q -pl corp-rag-app -am test` | planned | ready |
| 02-03-01 | 03 | 3 | AUTH-01, AUTH-02, AUTH-03, AUTH-04 | T-02-03-01 / T-02-03-02 / T-02-03-03 | PostgreSQL schema, constraints, indexes, repositories, and seed data are verified against PostgreSQL, not H2. | integration | `cd backend; mvn -q -pl corp-rag-app -am verify` | planned | ready |
| 02-04-01 | 04 | 4 | AUTH-01, AUTH-03 | T-02-04-01 / T-02-04-02 / T-02-04-03 / T-02-04-04 | Login, refresh, logout, cookie flags, JWT claims, refresh reuse detection, and Origin/Referer defense reject unsafe requests. | unit + slice + integration | `cd backend; mvn -q -pl corp-rag-app -am test` and `cd backend; mvn -q -pl corp-rag-app -am verify` | planned | ready |
| 02-05-01 | 05 | 5 | AUTH-01, AUTH-02, AUTH-03 | T-02-05-01 / T-02-05-02 / T-02-05-03 | Password policy, temporary passwords, first-admin bootstrap, password reset, and `must_change_password` gate work without plaintext leakage. | unit + slice + integration | `cd backend; mvn -q -pl corp-rag-app -am test` and `cd backend; mvn -q -pl corp-rag-app -am verify` | planned | ready |
| 02-06-01 | 06 | 5 | AUTH-02, AUTH-03 | T-02-06-01 / T-02-06-02 / T-02-06-03 | Role permissions, role replacement, ETag/If-Match, system-role protection, self-modification block, and last-admin protection work. | unit + slice + integration | `cd backend; mvn -q -pl corp-rag-app -am test` and `cd backend; mvn -q -pl corp-rag-app -am verify` | planned | ready |
| 02-07-01 | 07 | 6 | AUTH-01, AUTH-02, AUTH-03, AUTH-04 | T-02-07-01 / T-02-07-02 / T-02-07-03 / T-02-07-04 | Access policies resolve additive visibility, enforce last-admin visibility, evict cached filters after mutations, and write durable audit rows. | unit + slice + integration | `python scripts/verify-contracts.py` and `cd backend; mvn -q -pl corp-rag-app -am verify` | planned | ready |

## Prerequisites (delivered by plan 02-02 Wave 2)

- [x] Maven dependencies for Spring Security, Resource Server JWT, Spring Security Test, Spring Boot Testcontainers, Testcontainers JUnit Jupiter, and Testcontainers PostgreSQL are planned in `02-02-PLAN.md`.
- [x] Maven Failsafe binding is planned so `mvn test` stays Docker-free and `mvn verify` runs `*IT` PostgreSQL/Testcontainers tests.
- [x] Shared auth/security fixtures and PostgreSQL integration-test support are planned before behavior tests depend on them.

## Planned Automated Test Files

- [x] `backend/corp-rag-app/src/test/java/com/corprag/SecurityDependencySmokeTest.java` - plan 02-02 dependency and fixture smoke coverage.
- [x] `backend/corp-rag-app/src/test/java/com/corprag/repository/IdentitySchemaIT.java` - plan 02-03 Flyway schema, seed permissions/roles/policies, indexes, constraints, and refresh-token fields against PostgreSQL.
- [x] `backend/corp-rag-app/src/test/java/com/corprag/security/JwtServiceTest.java` - plan 02-04 JWT issue/verify claims, expiry, and secret handling.
- [x] `backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/AuthControllerTest.java` - plan 02-04 login, `/me`, refresh, logout, cookie flags, and ProblemDetail errors.
- [x] `backend/corp-rag-app/src/test/java/com/corprag/service/auth/AuthFlowIT.java` - plan 02-04 end-to-end auth flow against PostgreSQL with Testcontainers.
- [x] `backend/corp-rag-app/src/test/java/com/corprag/security/PasswordPolicyValidatorTest.java` - plan 02-05 password policy and temporary-password constraints.
- [x] `backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/UserControllerTest.java` - plan 02-05 user create, reset password, password-change-required, and self-profile rules.
- [x] `backend/corp-rag-app/src/test/java/com/corprag/security/RolePermissionMatrixTest.java` - plan 02-06 seeded roles, permissions, and dotted wire values.
- [x] `backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/UserRoleControllerTest.java` - plan 02-06 user-role replace-set, ADMIN double gate, self-modification block, and last-admin protection.
- [x] `backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/AccessPolicyControllerTest.java` - plan 02-07 access-policy admin flows and ETag/If-Match behavior.
- [x] `backend/corp-rag-app/src/test/java/com/corprag/service/access/AccessFilterResolverTest.java` - plan 02-07 effective policy union, PUBLIC visibility, no-role fail-safe, and cache eviction.
- [x] `backend/corp-rag-app/src/test/java/com/corprag/service/audit/AuditEventWriterTest.java` - plan 02-07 audit writer behavior.
- [x] `backend/corp-rag-app/src/test/java/com/corprag/IdentityAccessFlowIT.java` - plan 02-07 full auth/user/role/access-policy flow.

## Manual-Only Verifications

All Phase 2 behaviors have automated verification. Manual inspection is limited to reviewing generated one-time dev admin password logs when `ADMIN_PASSWORD` is intentionally absent in the dev profile; this is not required for normal CI or prod-profile verification.

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands or plan 02-02 prerequisites.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Prerequisites cover all previously missing validation references.
- [x] No watch-mode flags.
- [x] Feedback latency < 30s for quick checks after dependencies resolve.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** complete
