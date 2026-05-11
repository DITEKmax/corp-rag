# Phase 2: Identity, Users & Access Control - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-05-12
**Phase:** 2-Identity, Users & Access Control
**Areas discussed:** Session lifecycle, First admin and passwords, Role and permission baseline, Access-filter semantics

---

## Session lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| Single JWT cookie, 30 min | Match current OpenAPI with one httpOnly cookie and no refresh endpoint. | |
| JWT cookie + refresh cookie | Add refresh behavior and server-side revocation. | yes |
| Longer single JWT cookie | Simpler but higher risk if stolen. | |

**User's choice:** Access JWT 15 minutes plus refresh token 7 days, both in httpOnly cookies.
**Notes:** Refresh tokens are stored in DB, rotated on `/auth/refresh`, revoked on logout, and reuse of an already-rotated refresh invalidates the whole chain. `api-v1.yaml` must add `/auth/refresh` before execution.

| Option | Description | Selected |
|--------|-------------|----------|
| Several active devices | No hard cap beyond normal token expiry. | |
| One active session per user | New login invalidates old sessions. | |
| Active session limit | Cap active refresh tokens and evict by LRU. | yes |

**User's choice:** Limit to 5 active refresh tokens per user, configurable with default 5.
**Notes:** `last_used_at` updates on refresh. Login above the limit evicts the least-recently-used refresh token and writes an audit event.

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal auth/security event table | Narrow table for auth events. | |
| Structured logs only | No durable DB audit yet. | |
| General audit_events baseline | Extendable audit table for future phases. | yes |

**User's choice:** Create `audit_events` in Phase 2, but write only Phase 2 categories initially.
**Notes:** This is not Phase 3 audit scope creep. It is the durable substrate needed for security-critical auth/session/role/policy behavior. Transaction mode is per event type: consistency-critical events join business transaction; auth/security events may use separate transaction.

| Option | Description | Selected |
|--------|-------------|----------|
| Strict same-site internal SPA | Strict cookies plus origin checks. | yes |
| Simpler SameSite=Strict only | No explicit origin checks. | |
| CSRF token cookie/header | Add frontend-managed CSRF token. | |

**User's choice:** `corp_rag_session` and `corp_rag_refresh` are httpOnly Strict cookies; auth endpoints validate Origin/Referer.
**Notes:** Do not globally disable CSRF. `Secure` is false in dev HTTP and true in prod. No separate non-httpOnly CSRF token cookie for MVP.

---

## First admin and passwords

| Option | Description | Selected |
|--------|-------------|----------|
| Seeded from env on startup | App creates first admin if none exists. | yes |
| Flyway seed migration | Put first user into DB migration. | |
| CLI/bootstrap command | Separate operational bootstrap. | |

**User's choice:** Startup bootstrap from config/env.
**Notes:** If no `ADMIN` user exists, create one from env/config. Bootstrap admin gets `must_change_password=true`. In dev, missing password may generate a one-time password; in prod, missing required values fail fast.

| Option | Description | Selected |
|--------|-------------|----------|
| Admin sets temporary password | Admin supplies temp password. | |
| Generated one-time password | Backend generates password and returns once. | yes |
| Invite/reset flow | Email/token invitation. | |

**User's choice:** Backend-generated temporary password.
**Notes:** `POST /users` has no password field. Java generates a 16-character `SecureRandom` password, stores only BCrypt hash, returns plaintext once, and sets `must_change_password=true`. Invitation flow is deferred.

| Option | Description | Selected |
|--------|-------------|----------|
| Keep existing flat REST URLs | `/users`, `/roles`, `/access-policies`. | yes |
| Move admin APIs to `/admin/*` | Breaking URL change. | |
| Hybrid | Canonical flat API plus frontend admin routes. | |

**User's choice:** Keep flat API URLs.
**Notes:** Admin-only behavior is enforced by permissions and method security. Frontend routes may still be `#/admin/users` later.

| Option | Description | Selected |
|--------|-------------|----------|
| Pragmatic strong policy | Min 12 and 3-of-4 classes with weak-word checks. | yes |
| MVP simple policy | Min 8 only. | |
| Strict enterprise policy | History/expiry/extra rules. | |

**User's choice:** Strong but pragmatic password policy.
**Notes:** Return all violations at once. Use `PASSWORD_POLICY_VIOLATION`. Prepare `CompromisedPasswordChecker`; HIBP, history, expiry, and MFA are deferred.

---

## Role and permission baseline

| Option | Description | Selected |
|--------|-------------|----------|
| ADMIN + EMPLOYEE + VIEWER | Three-role MVP baseline. | yes |
| ADMIN + EMPLOYEE only | Simpler but less granular. | |
| ADMIN + MANAGER + EMPLOYEE + VIEWER | More complex seeded model. | |

**User's choice:** Seed `ADMIN`, `EMPLOYEE`, `VIEWER`.
**Notes:** Multiple roles per user are allowed. Custom roles may be created later. `MANAGER` is deferred.

| Option | Description | Selected |
|--------|-------------|----------|
| Uppercase enum everywhere | Change contract to uppercase permission strings. | |
| Keep lower dotted in OpenAPI, map internally | Translation layer. | |
| Lower dotted everywhere | Wire and DB store current contract strings. | yes |

**User's choice:** Lower dotted strings are canonical.
**Notes:** Java enum may use uppercase names with explicit wire values. This preserves current OpenAPI baseline.

| Option | Description | Selected |
|--------|-------------|----------|
| PUT full replacement | Role update replaces permissions. | yes |
| PATCH partial update | More flexible. | |
| Separate endpoints for permissions | More API surface. | |

**User's choice:** `PUT /roles/{roleId}` full replacement with ETag/If-Match.
**Notes:** Missing If-Match returns 428; mismatch returns 412. System roles are protected. Last-admin protection applies.

| Option | Description | Selected |
|--------|-------------|----------|
| PUT full replacement with protections | Replace all user roles atomically. | |
| Add/remove endpoints | Explicit grant/revoke. | |
| Both replacement and add/remove | More API surface. | |

**User's choice:** Keep existing baseline `POST /users/{userId}/roles` replace semantics.
**Notes:** Body uses role names. Empty roles are invalid. Unknown role names include details. One diff audit event is preferred. No ETag. Self role modification is forbidden.

---

## Access-filter semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Union across roles/policies | Additive model. | yes |
| Most restrictive intersection | Safer but surprising. | |
| Priority-based policies | Richer but overbuilt. | |

**User's choice:** Union semantics.
**Notes:** Roles grant actions; policies grant visibility. Both add, neither subtracts. `PUBLIC` documents are always visible.

| Option | Description | Selected |
|--------|-------------|----------|
| Policies attach to roles | Match current AccessPolicy.roleId baseline. | yes |
| Policies attach directly to users | More flexible but complex. | |
| Both role policies and user overrides | Enterprise-like but too much. | |

**User's choice:** Policies attach to roles one-to-one.
**Notes:** Unique `access_policies.role_id`. Duplicate creation returns `ROLE_POLICY_ALREADY_EXISTS`. System role policies are editable.

| Option | Description | Selected |
|--------|-------------|----------|
| Editable with guardrails | Allow policy updates while preserving full-visibility admin. | yes |
| Fully editable | Flexible but can create visibility blackout. | |
| System policies locked | Safer but too rigid. | |

**User's choice:** Policies editable with semantic guardrails.
**Notes:** Last-admin-visibility protection blocks state with no full-visibility user. Policy PUT uses ETag/If-Match. Invalidate affected users' access-filter cache.

| Option | Description | Selected |
|--------|-------------|----------|
| String enums seeded in DB + contract enum | Controlled departments and docTypes. | |
| Free departments, enum docTypes | Preserve baseline. | yes |
| Free strings for both | Weak validation. | |

**User's choice:** Preserve current baseline: free-form departments and enum docTypes.
**Notes:** Access hierarchy includes `RESTRICTED`. Department dictionary is deferred to Phase 3. Department format validation is uppercase ASCII code regex.

---

## the agent's Discretion

- Exact Spring Security CSRF configuration that preserves the security intent.
- `PermissionEvaluator` versus controller/service self-access checks.
- ETag representation, with version-based ETag preferred.
- Postgres enum-array versus string-array storage.
- Exact reconciliation of unknown role names with existing `ROLE_NOT_FOUND` status in contract/constants.

## Deferred Ideas

- Email/invitation onboarding.
- Department dictionary and CRUD endpoints.
- HIBP compromised-password checking.
- Password history, password expiry, MFA.
- Seeded `MANAGER` role.
- Force-refresh on role/policy mutation.
- Caffeine metrics and deeper access-filter performance work.
