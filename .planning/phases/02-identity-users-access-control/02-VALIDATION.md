---
phase: 02
slug: identity-users-access-control
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| 02-W0-01 | 01 | 1 | AUTH-01, AUTH-02, AUTH-03, AUTH-04 | T-02-01 / T-02-02 / T-02-03 | Test dependencies, Surefire/Failsafe split, and generated contract verification exist before feature code. | build/smoke | `cd backend; mvn -q -pl corp-rag-app -am test` | no | pending |
| 02-W0-02 | 02 | 2 | AUTH-01, AUTH-02, AUTH-03, AUTH-04 | T-02-04 / T-02-05 | PostgreSQL schema, constraints, indexes, and seed data are verified against PostgreSQL, not H2. | integration | `cd backend; mvn -q -pl corp-rag-app -am verify` | no | pending |
| 02-01-01 | 03 | 3 | AUTH-01, AUTH-03 | T-02-06 / T-02-07 / T-02-08 | Login, refresh, logout, cookie flags, JWT claims, and CSRF defense reject unsafe requests. | unit + slice + integration | `cd backend; mvn -q -pl corp-rag-app -am test` and `cd backend; mvn -q -pl corp-rag-app -am verify` | no | pending |
| 02-02-01 | 04 | 4 | AUTH-01, AUTH-02, AUTH-03 | T-02-09 / T-02-10 | Password policy, temporary passwords, first-admin bootstrap, password reset, and `must_change_password` gate work without plaintext leakage. | unit + slice + integration | `cd backend; mvn -q -pl corp-rag-app -am test` and `cd backend; mvn -q -pl corp-rag-app -am verify` | no | pending |
| 02-03-01 | 05 | 4 | AUTH-02, AUTH-03 | T-02-11 / T-02-12 / T-02-13 | Role permissions, role replacement, ETag/If-Match, system-role protection, self-modification block, and last-admin protection work. | unit + slice + integration | `cd backend; mvn -q -pl corp-rag-app -am test` and `cd backend; mvn -q -pl corp-rag-app -am verify` | no | pending |
| 02-04-01 | 06 | 5 | AUTH-02, AUTH-03, AUTH-04 | T-02-14 / T-02-15 | Access policies resolve additive visibility, enforce last-admin visibility, and evict cached filters after mutations. | unit + slice + integration | `cd backend; mvn -q -pl corp-rag-app -am test` and `cd backend; mvn -q -pl corp-rag-app -am verify` | no | pending |
| 02-05-01 | 07 | 6 | AUTH-01, AUTH-02, AUTH-03, AUTH-04 | T-02-16 / T-02-17 | Durable audit rows are written for AUTH, ROLE, and ACCESS_POLICY outcomes and full auth/user/access workflows pass. | integration | `cd backend; mvn -q -pl corp-rag-app -am verify` | no | pending |

## Wave 0 Requirements

- [ ] `backend/corp-rag-app/src/test/java/com/corprag/security/PasswordPolicyValidatorTest.java` - covers AUTH-01 password policy and temporary-password constraints.
- [ ] `backend/corp-rag-app/src/test/java/com/corprag/security/JwtServiceTest.java` - covers AUTH-01 JWT issue/verify claims and expiry.
- [ ] `backend/corp-rag-app/src/test/java/com/corprag/security/AccessFilterResolverTest.java` - covers AUTH-04 effective policy union, PUBLIC visibility, no-role fail-safe, and cache eviction.
- [ ] `backend/corp-rag-app/src/test/java/com/corprag/security/RolePermissionMatrixTest.java` - covers AUTH-02/AUTH-03 seeded roles, permissions, and dotted wire values.
- [ ] `backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/AuthControllerTest.java` - covers AUTH-01 login, `/me`, refresh, logout, password change, cookie flags, and ProblemDetail errors.
- [ ] `backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/UserRoleAccessPolicyControllerTest.java` - covers AUTH-02/AUTH-03 user, role, and access-policy admin flows.
- [ ] `backend/corp-rag-app/src/test/java/com/corprag/AuthFlowIT.java` - covers AUTH-01/AUTH-03 end-to-end auth flow against PostgreSQL with Testcontainers.
- [ ] `backend/corp-rag-app/src/test/java/com/corprag/AuthSchemaIT.java` - covers Flyway schema, seed permissions/roles/policies, indexes, constraints, and refresh-token fields against PostgreSQL.
- [ ] Maven dependencies for Spring Security, Resource Server JWT, Spring Security Test, Spring Boot Testcontainers, Testcontainers JUnit Jupiter, and Testcontainers PostgreSQL.
- [ ] Maven Failsafe binding so `mvn test` stays Docker-free and `mvn verify` runs `*IT` PostgreSQL/Testcontainers tests.

## Manual-Only Verifications

All Phase 2 behaviors have automated verification. Manual inspection is limited to reviewing generated one-time dev admin password logs when `ADMIN_PASSWORD` is intentionally absent in the dev profile.

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s for quick checks
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
