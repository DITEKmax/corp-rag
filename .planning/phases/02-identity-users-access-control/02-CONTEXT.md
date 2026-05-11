# Phase 2: Identity, Users & Access Control - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 delivers Java-owned identity and authorization: login, logout, refresh, password change, current profile, admin-managed users, roles, permissions, role-linked access policies, and Java-resolved access filters for downstream document retrieval. It does not implement document upload, retrieval, frontend screens, email invitations, MFA, or full observability.

</domain>

<decisions>
## Implementation Decisions

### Session Lifecycle
- **D-01:** Use short-lived access JWT plus refresh token. Access TTL is 15 minutes; refresh TTL is 7 days.
- **D-02:** Store both tokens in httpOnly cookies: `corp_rag_session` at `Path=/api/v1` and `corp_rag_refresh` at `Path=/api/v1/auth`.
- **D-03:** Refresh tokens are persisted in `refresh_tokens` so Java can revoke them server-side.
- **D-04:** `POST /auth/refresh` rotates the access+refresh pair and invalidates the previous refresh token.
- **D-05:** Reuse of an already-rotated refresh token is a security event; invalidate the whole refresh-token chain.
- **D-06:** `POST /auth/logout` invalidates all active refresh tokens for the user.
- **D-07:** Limit active refresh tokens to `MAX_ACTIVE_SESSIONS_PER_USER`, default `5`. On login above the limit, evict the least-recently-used refresh token by `last_used_at` and record a session-evicted audit event.
- **D-08:** Update `last_used_at` on every successful `/auth/refresh`.
- **D-09:** Cookie `Secure` is false in local/dev HTTP, true in prod/non-local. Configure via `cookies.secure`, default false in `application.yml`, true in `application-prod.yml`.
- **D-10:** Use `SameSite=Strict` cookies as the primary CSRF defense. Additionally, implement an explicit `OriginRefererValidationFilter` for all non-safe HTTP methods (`POST`, `PUT`, `PATCH`, `DELETE`) on `/api/v1/**` requests that use cookie auth, not only `/api/v1/auth/**`.
  Filter logic:
  - If the method is `GET`, `HEAD`, or `OPTIONS`, skip validation.
  - If the request does not carry cookie auth and uses a bearer token instead, skip validation.
  - Otherwise require an `Origin` header matching one of the allowed origins configured through `app.security.cors.allowed-origins`; dev profile defaults are `http://localhost` and `http://localhost:80`.
  - If `Origin` is absent, which can happen when corporate proxies strip it, fall back to `Referer` with the same allowed-origin matching.
  - If neither `Origin` nor `Referer` is valid, return `403` ProblemDetail with `error_code=ORIGIN_VALIDATION_FAILED`.
- **D-11:** Do not use Spring Security's default CSRF filter (`CsrfFilter`) in Phase 2. Do not introduce a frontend-readable CSRF token cookie in Phase 2. Browser CSRF defense consists of two layers:
  1. `SameSite=Strict` cookies so browsers block cross-origin cookie transmission.
  2. `OriginRefererValidationFilter` as server-side defense-in-depth for cases where SameSite is ineffective, including same-origin XSS pressure, subdomain confusion, older browsers, or intermediary behavior.
  Phase 7 upgrade path: if security review raises the issue, add a CSRF token cookie as a third layer without replacing the D-10/D-11 behavior.
- **D-12:** Existing access JWTs may keep stale permissions for up to 15 minutes after role changes. Force-refresh via `user.force_refresh_at` is deferred.

### Contract-First Additions
- **D-13:** Extend `contracts/openapi/api-v1.yaml` before Java implementation with additive endpoints: `POST /auth/refresh`, `POST /auth/password`, and `POST /users/{userId}/reset-password`.
- **D-14:** Keep existing flat API namespace. Use `/users`, `/roles`, `/access-policies`; do not introduce `/admin/*` API paths. Frontend routes may still use `#/admin/...` later.
- **D-15:** Extend `contracts/constants.yaml` before Java implementation with Phase 2 error codes:
  - `PASSWORD_CHANGE_REQUIRED` (401)
  - `PASSWORD_POLICY_VIOLATION` (400)
  - `REFRESH_TOKEN_INVALID` (401)
  - `REFRESH_TOKEN_REUSED` (401)
  - `AUDIT_WRITE_FAILED` (500)
  - `INVALID_PERMISSION_CODE` (400)
  - `SYSTEM_ROLE_PROTECTED` (409)
  - `LAST_ADMIN_PROTECTED` (409)
  - `SELF_MODIFICATION_FORBIDDEN` (403)
  - `ORIGIN_VALIDATION_FAILED` (403): `https://corp-rag.local/problems/origin-validation-failed`, title "Запрос отклонён по политике безопасности cross-origin"
  - `ROLE_POLICY_ALREADY_EXISTS` (409)
  - `LAST_ADMIN_VISIBILITY_LOST` (409)
- **D-16:** Do not add `SESSION_LIMIT_EXCEEDED` as an API error code; session eviction is an audit/info event, not a client error.

### Audit Baseline
- **D-17:** Create a durable `audit_events` table in Phase 2, not a temporary auth-only table.
- **D-18:** Schema includes `id`, `occurred_at`, `event_category`, `event_type`, `outcome`, nullable actor/target/entity fields, `ip_address`, `user_agent`, `details JSONB`, and nullable `correlation_id`.
- **D-19:** Add indexes on `(actor_user_id, occurred_at DESC)`, `(target_user_id, occurred_at DESC)`, `(event_category, event_type, occurred_at DESC)`, and `(entity_type, entity_id, occurred_at DESC)`.
- **D-20:** Phase 2 writes `AUTH`, `ROLE`, and `ACCESS_POLICY` events needed by identity/access behavior. Later phases add document, guard, and indexing events without replacing the table.
- **D-21:** Provide an `AuditEventWriter` abstraction. Some events write in the same business transaction; auth/security events that must survive rollback may write in a separate transaction. Decide per event type.

### First Admin And Passwords
- **D-22:** Bootstrap the first admin from config/env on startup when no user with `ADMIN` role exists. Use `CommandLineRunner` or equivalent startup hook.
- **D-23:** Bootstrap inputs are `ADMIN_USERNAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD`. In prod, required values fail fast when bootstrap is enabled.
- **D-24:** In dev, if `ADMIN_PASSWORD` is missing, generate a random 16-character password and log it once at WARN. Do not ship a reusable default password.
- **D-25:** Hash all passwords with BCrypt cost factor `12`. Never log plaintext passwords except the one-time generated dev bootstrap warning.
- **D-26:** Seeded admin has `must_change_password=true` and receives `ADMIN` role.
- **D-27:** Admin-created users are created by `POST /users` without a password field. Backend generates a one-time temporary password and returns it exactly once in the response.
- **D-28:** Temporary password generation uses `SecureRandom`, 16 characters, alphanumeric alphabet excluding visually similar characters such as `0/O` and `1/l/I`.
- **D-29:** First login, or login after admin password reset, issues a normal access+refresh token pair, both carrying `must_change_password=true`. Middleware, such as a Spring Security filter or aspect, blocks all endpoints except:
  - `POST /auth/password` - change the password.
  - `POST /auth/refresh` - rotate the pair; the new pair keeps the same flag until password change succeeds.
  - `POST /auth/logout` - abort the flow.
  - `GET /me` - fetch current user state for the password-change UI.
  Once `POST /auth/password` succeeds, `users.must_change_password` is cleared in the database and a new access+refresh pair is issued without the claim. All previously active refresh tokens for that user are invalidated, like logout-all, to prevent stale flagged sessions.
- **D-30:** `POST /auth/password` validates current/new password, clears `must_change_password`, invalidates old refresh state as needed, and issues a new token pair without the flag.
- **D-31:** `POST /users/{userId}/reset-password` requires admin permission, generates a new temporary password, invalidates active refresh tokens, and returns the temporary password once.
- **D-32:** Password policy: minimum 12 chars; at least 3 of 4 character classes; reject username, email local-part, weak words, current year, and top-100 common passwords.
- **D-33:** Implement `PasswordPolicyValidator.validate(plain, context)` returning all violations. Return violations in ProblemDetail details.
- **D-34:** Prepare `CompromisedPasswordChecker` with in-memory top-100 default; HIBP k-anonymity checker is deferred behind a disabled property.

### Roles And Permissions
- **D-35:** Seed three system roles: `ADMIN`, `EMPLOYEE`, `VIEWER`.
- **D-36:** Permission wire/DB format is lower dotted strings from current OpenAPI, e.g. `users.read`. Java enum names may be uppercase but must carry explicit wire values via `@JsonValue`.
- **D-37:** Phase 2 permission list is exactly:
  `users.create`, `users.read`, `users.update`, `users.delete`,
  `roles.create`, `roles.read`, `roles.update`, `roles.delete`,
  `access_policies.create`, `access_policies.read`, `access_policies.update`, `access_policies.delete`,
  `documents.read`, `documents.upload`, `documents.delete`, `chat.query`.
- **D-38:** There is no `documents.update`; document changes are modeled as later upload/version behavior.
- **D-39:** `ADMIN` gets all 16 permissions. `EMPLOYEE` gets `chat.query`, `documents.read`, `documents.upload`, `users.read`. `VIEWER` gets `chat.query`, `documents.read`.
- **D-40:** Use `permissions`, `roles`, `role_permissions`, and `user_roles` tables. `user_roles` records `assigned_by` and `assigned_at`.
- **D-41:** Multiple roles per user are allowed. Effective permissions are the union of role permissions.
- **D-42:** Default role for a newly created user is `EMPLOYEE` when roles are omitted.
- **D-43:** Assigning the seeded `ADMIN` role to a user requires the caller to hold both `users.update` and `roles.update`. The endpoint remains `POST /users/{userId}/roles` with primary permission `users.update` declared in `x-required-permissions`; the additional `roles.update` requirement applies only when the request body contains `"ADMIN"` in the roles array. If the caller lacks `roles.update` while attempting to grant `ADMIN`, respond `403 INSUFFICIENT_PERMISSIONS` with details `{ "required_additional": "roles.update", "reason": "admin_grant" }`. This double gate does not apply to assigning `EMPLOYEE`, `VIEWER`, or custom roles; those require only `users.update`.
- **D-44:** System roles cannot be updated or deleted. Roles currently assigned to users cannot be deleted.
- **D-45:** Custom roles can be created at runtime, but only with existing seeded permission codes.
- **D-46:** `PUT /roles/{roleId}` is full replacement and uses ETag/`If-Match`. Missing `If-Match` returns 428; mismatch returns 412; success increments `roles.version`.
- **D-47:** `POST /users/{userId}/roles` keeps baseline semantics: body has role names, replaces all roles atomically, rejects an empty role list, audits one diff event, and does not use ETag.
- **D-48:** An admin cannot change their own roles through `POST /users/{self}/roles`; return `SELF_MODIFICATION_FORBIDDEN`.
- **D-49:** Last-admin protection blocks role, user, or permission mutations that would leave zero users with effective `users.update` authority.
- **D-50:** Auth endpoints such as login, logout, refresh, password change, and `/me` depend on authentication/session rules rather than `x-required-permissions`.
- **D-51:** Self access to `GET/PUT /users/{id}` is allowed without `users.read`/`users.update` when `id` is the authenticated user's id. Other-user access requires permissions.

### Access Policies And Filters
- **D-52:** Access policies attach to roles, not users. Cardinality is one policy per role; enforce unique `access_policies.role_id`.
- **D-53:** Duplicate policy creation for a role returns `ROLE_POLICY_ALREADY_EXISTS`; use `PUT` to change an existing policy.
- **D-54:** Policies define data visibility. Roles define actions. Both are additive: roles never subtract permissions, policies never subtract visibility.
- **D-55:** Effective access filter resolves from assigned user roles to those roles' policies.
- **D-56:** `accessLevels` use hierarchy `PUBLIC < INTERNAL < CONFIDENTIAL < RESTRICTED`; effective max is the highest level granted by any assigned role policy.
- **D-57:** `departments` are free-form strings. Empty list means wildcard/all departments.
- **D-58:** `docTypes` are enum values. Empty list is invalid; all doc types must be listed explicitly.
- **D-59:** `AccessLevel` values are `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `RESTRICTED`. `DocType` values are `POLICY`, `REGULATION`, `GUIDE`, `REPORT`, `MANUAL`, `OTHER`.
- **D-60:** Department format validation in Phase 2 is `^[A-Z][A-Z0-9_]{0,63}$`.
- **D-61:** PUBLIC documents are always visible. Retrieval semantics should include `access_level = 'PUBLIC' OR (...)`.
- **D-62:** User with no assigned roles/policies fails safe and has no useful non-public visibility. Normal APIs should prevent users from ending up with zero roles.
- **D-63:** Seed default policies:
  - `ADMIN`: all access levels, wildcard departments, all six docTypes.
  - `EMPLOYEE`: `PUBLIC`, `INTERNAL`, wildcard departments, all six docTypes.
  - `VIEWER`: `PUBLIC`, wildcard departments, `POLICY`, `REGULATION`, `GUIDE`, `MANUAL`, `OTHER`.
- **D-64:** System role policies are editable. `is_system` protects role definitions, not organizational policy scope.
- **D-65:** Access policy updates use ETag/`If-Match` like role updates.
- **D-66:** Last-admin-visibility protection blocks mutations that would leave no user with full visibility: `RESTRICTED` max level, wildcard departments, and all six docTypes.
- **D-67:** Cache resolved access filters in Java with TTL 60 seconds. A simple in-memory `Map<UserId, CachedFilter>` with TTL is acceptable for Phase 2; Caffeine metrics are deferred to Phase 7. Explicit eviction triggers, running inside the mutating transaction or as a transaction synchronization `afterCommit` hook:
  1. `POST /users/{userId}/roles` - evict `cache[userId]`.
  2. `PUT /roles/{roleId}` when permissions change - evict cache for all users with that role via `SELECT user_id FROM user_roles WHERE role_id = ?`.
  3. `DELETE /roles/{roleId}` - same role-based eviction; custom roles only because seeded roles are protected.
  4. `POST /access-policies` - evict cache for all users with the policy's role.
  5. `PUT /access-policies/{policyId}` - same role-based eviction.
  6. `DELETE /access-policies/{policyId}` - same role-based eviction.
  7. `DELETE /users/{userId}` - evict `cache[userId]`.
  Implementation hint: use a small `AccessFilterCacheInvalidator` service with `invalidate(userId)` and `invalidateForRole(roleId)` so eviction logic does not spread through controllers/services.
- **D-68:** `AccessFilter` is sent to Python in `QueryRequest.accessFilter` for chat query calls, matching `contracts/openapi/ai-service-v1.yaml`.
- **D-69:** (updated) Flyway migration order for Phase 2 schema and seed uses V2 through V10:
  - `V2__create_users_table.sql`
  - `V3__create_refresh_tokens_table.sql`
  - `V4__create_audit_events_table.sql`
  - `V5__create_permissions_table.sql`
  - `V6__create_roles_table.sql`
  - `V7__create_role_permissions_table.sql`
  - `V8__create_user_roles_table.sql`
  - `V9__create_access_policies_table.sql`
  - `V10__seed_identity_defaults.sql`
  Consolidated V10 seeds permissions (D-37), system roles (D-35), role-permission matrix (D-39), and default access policies (D-63) in one idempotent transaction. Idempotency uses `ON CONFLICT DO NOTHING`. Rationale: identity baseline is an atomic domain concept; dependent seeds should succeed or fail together for consistency. FK dependencies still enforce table creation before seed rows: `role_permissions` references permissions and roles; `user_roles` references users and roles; `access_policies` references roles. Admin bootstrap from D-22 is not a Flyway migration; it runs at application startup after Flyway completes so BCrypt hashing happens in Java, not SQL. `V1__baseline.sql` from Phase 1 remains untouched.
- **D-70:** `audit_events.outcome` is a constrained string with exactly `SUCCESS`, `FAILURE`, and `ERROR`. Database constraint: `CHECK (outcome IN ('SUCCESS', 'FAILURE', 'ERROR'))`. `SUCCESS` means the operation completed as intended; `FAILURE` means it was rejected by validation, authorization, or business rules; `ERROR` means it crashed due to unexpected exception or infrastructure failure. Examples: `LOGIN_SUCCESS` is `SUCCESS`; bad-password `LOGIN_FAILED` is `FAILURE`; `REFRESH_TOKEN_REUSED` detection is `FAILURE`; `PASSWORD_CHANGED` is `SUCCESS`; `AUDIT_WRITE_FAILED` is an `ERROR` event written by a fallback path, or logged only if even fallback fails.
- **D-71:** Phase 2 testing strategy:
  - Unit tests cover pure Java logic: `PasswordPolicyValidator`, `AccessFilterResolver`, JWT issuer, and role/permission matrix. These run through `mvn test` without infrastructure.
  - Slice tests use `@WebMvcTest` for auth, users, roles, and access-policy controllers with mocked services. They verify HTTP status codes, ProblemDetail shape, ETag headers, and error codes from `contracts/constants.yaml`.
  - Integration tests use `@SpringBootTest` plus Testcontainers with real PostgreSQL 16. They verify Flyway migrations, repository logic, and end-to-end auth flow: login, `/me`, refresh, logout.
  - Replace the current H2-backed `CorpRagApplicationTests.java` approach with Testcontainers Postgres because Phase 2 uses PostgreSQL-specific features such as `INET`, `JSONB`, and array types.
  - Security tests use `@WithMockUser` and/or `SecurityMockMvcRequestPostProcessors` for admin-only endpoints, self-vs-other user access, last-admin protection, and self-modify forbidden scenarios.
  - Coverage target is 80% line coverage for core security classes: `JwtService`, `PasswordPolicyValidator`, `AccessFilterResolver`, `AuditEventWriter`, and role/permission matrix. DTOs, mappers, and glue code do not need a hard target.
  - Testing libraries: Spring Boot Test, Testcontainers PostgreSQL module, AssertJ via `spring-boot-starter-test`, and optional REST Assured for black-box auth flow tests.
  - Run profiles: `mvn test` runs unit and slice tests without Docker; `mvn verify` adds integration tests with Testcontainers and requires a Docker daemon.
- **D-72:** JWT issuing and verification use `spring-boot-starter-oauth2-resource-server` with self-issued tokens.
  - Access JWT signing uses HS256 symmetric signing with a `SecretKey` of at least 32 bytes.
  - The signing secret is read from `JWT_SECRET`; production profile fails fast if it is missing.
  - Development profile may generate a random startup secret with a warning.
  - Use `NimbusJwtEncoder` for issuing access JWTs.
  - Use `NimbusJwtDecoder.withSecretKey()` for verifying access JWTs.
  - Do not use `NimbusJwtDecoder.withIssuerLocation()` because CVE-2026-22748 affects Spring Security 6.3.0 through 6.3.14; the current Spring Boot 3.3.6 BOM supplies Spring Security 6.3.5, which is in the affected range.
  - Refresh tokens are opaque, not JWTs. Store only their hash in PostgreSQL and use family-based reuse detection, consistent with RFC 9700 refresh-token rotation guidance.
  - Phase 7 upgrade path: migrate to RS256 asymmetric signing with key rotation through a JWKS endpoint.

### the agent's Discretion
- Choose the exact Spring Security wiring for D-10/D-11 as long as Phase 2 does not use `CsrfFilter`, preserves Strict SameSite cookies, and applies `OriginRefererValidationFilter` to all unsafe `/api/v1/**` cookie-auth requests.
- Use `@EnableMethodSecurity` plus `@PreAuthorize` for method-level security. Defer custom `PermissionEvaluator`; choose explicit controller/service checks or `@PreAuthorize` SpEL such as `#authentication.principal.id == #userId` for self-vs-other authorization.
- Choose generated ETag format: version-based ETag is preferred, but normalized representation hash is acceptable.
- Choose Postgres storage for enum arrays (`VARCHAR[]`/`TEXT[]` versus native enum arrays) if contracts and validation stay consistent.
- Reconcile unknown role names on assignment with existing `ROLE_NOT_FOUND` status in the current constants/contract while preserving the desired details payload.

### Decision Numbering Confirmation

The final Phase 2 context contains exactly D-01 through D-72. Plan artifacts are expected to reference this final numbering. Non-trivial stale wording resolved before execution:

| Stale wording/reference | Final decision reference |
|-------------------------|--------------------------|
| `D-29: password verification uses BCrypt` | `D-25: Hash all passwords with BCrypt cost factor 12` |
| `D-30: disabled users cannot authenticate` | No final D-NN; disabled-account handling is an implementation detail only if supported by the final contract/schema |
| `D-36: system roles are ADMIN, EMPLOYEE, VIEWER` | `D-35: Seed three system roles: ADMIN, EMPLOYEE, VIEWER` |
| `D-38: system role permission matrix` | `D-39: system role permission matrix` |
| `D-40: new users default to EMPLOYEE` | `D-42: default role for new users is EMPLOYEE when omitted` |
| `D-52 through D-66` old access-policy wording | Final access-policy decisions are D-52 through D-68 as written above |

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning State
- `.planning/PROJECT.md` - project value, architecture constraints, out-of-scope items, and locked decisions.
- `.planning/REQUIREMENTS.md` - Phase 2 requirements AUTH-01 through AUTH-04.
- `.planning/ROADMAP.md` - Phase 2 goal and success criteria.
- `.planning/STATE.md` - current project state and accumulated Phase 1 decisions.
- `.planning/phases/01-foundation-contracts/01-CONTEXT.md` - contract-first, root contracts, generated-code, Java skeleton, Docker Compose, and database ownership decisions carried forward.
- `.planning/phases/02-identity-users-access-control/02-RESEARCH.md` - accepted Phase 2 research findings and implementation hints for Spring Security, refresh rotation, Testcontainers, CSRF, ETag, and method security.

### Contracts
- `contracts/openapi/api-v1.yaml` - frontend-facing Java API contract; must be extended before Phase 2 Java implementation.
- `contracts/openapi/ai-service-v1.yaml` - Java-to-Python query contract and `AccessFilter` shape.
- `contracts/constants.yaml` - shared error codes and generated constants; must be extended before Phase 2 Java implementation.

### Architecture Docs
- `docs/ARCHITECTURE.md` - target Java backend structure, Spring Security/JWT/RBAC notes, schema sketches, and access-filtered retrieval flow.
- `docs/PATTERNS.md` - API update style and project patterns.
- `docs/CONTEXT.md` - project context and Java/Python responsibility split.
- `backend/README.md` - backend module layout and Java service role.
- `frontend/README.md` - future frontend route/API client context.

### ADRs
- `docs/decisions/ADR-002-vector-database.md` - Qdrant payload-filtered retrieval rationale.
- `docs/decisions/ADR-003-java-python-split.md` - Java owns auth/RBAC and Python applies passed filters.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/corp-rag-app` - Spring Boot app already has Web, JDBC, Validation, Flyway, Actuator, PostgreSQL runtime, and H2 test dependency.
- `backend/corp-rag-contracts` - generated Java contract module consumed by the app.
- `contracts/openapi/api-v1.yaml` - already defines auth, users, roles, access policies, document, and chat contract baseline with lower dotted `x-required-permissions`.
- `contracts/openapi/ai-service-v1.yaml` - already defines `AccessFilter` with `accessLevels`, `departments`, and `docTypes`.
- `contracts/constants.yaml` - generated error-code source of truth.
- `backend/corp-rag-app/src/main/resources/db/migration/V1__baseline.sql` - Flyway baseline location for Phase 2 migrations.

### Established Patterns
- Contract-first: update root contracts and constants before service behavior.
- Java remains the browser-facing service and the owner of auth, RBAC, users, roles, access policies, and access filter resolution.
- Python AI service does not own auth/RBAC; it applies the filter Java sends.
- Generated DTO/constants outputs are build artifacts and are not committed.
- Java uses `JAVA_DB_URL`, `JAVA_DB_USER`, and `JAVA_DB_PASSWORD` for the Java-owned PostgreSQL database.

### Integration Points
- Add Spring Security/JWT/auth code under `backend/corp-rag-app`.
- Add Flyway migrations for users, refresh tokens, audit, roles, permissions, role policies, and seeded data.
- Extend contract verification inputs in root `contracts/`.
- Preserve Docker Compose local contour from Phase 1; no new external infra is required for Phase 2.

</code_context>

<specifics>
## Specific Ideas

- Phase 2 migration order is locked by D-69 updated; keep `V1__baseline.sql` untouched.
- Use idempotent seed SQL with `ON CONFLICT DO NOTHING` where possible.
- Use BCrypt cost factor `12`.
- Use one audit event with diff for role replacement instead of per-role event spam.
- Include before/after effective filter in access-policy assignment/update audit details when practical.
- Include `affected_users_count` for policy updates.
- Keep response shapes for refresh/logout/password-change consistent for Phase 6, especially whether refresh returns `/me`-like state or 204.

</specifics>

<deferred>
## Deferred Ideas

- Invitation/email/SMS user onboarding flow is deferred; Phase 2 uses generated temporary passwords.
- Department dictionary and CRUD endpoints are deferred to Phase 3 with document management.
- HIBP compromised password checking is deferred behind `CompromisedPasswordChecker`.
- Password history, password expiry, and MFA are out of scope for Phase 2.
- `MANAGER` seeded role is deferred; it can be created as a custom role later.
- Force-refresh on role/policy mutation via `user.force_refresh_at` is deferred.
- Caffeine cache metrics and deeper access-filter performance work are deferred to Phase 7.

</deferred>

---

*Phase: 2-Identity, Users & Access Control*
*Context gathered: 2026-05-12*
