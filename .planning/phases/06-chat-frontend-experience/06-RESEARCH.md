---
phase: 6
slug: chat-frontend-experience
status: complete
created: 2026-05-26
---

# Phase 6 — Technical Research

## Question

What does the executor need to know to plan Phase 6 without guessing about the greenfield Java chat layer, the vanilla frontend shell, and the cross-cutting auth/audit/contracts surfaces?

## Scope Researched

- `.planning/phases/06-chat-frontend-experience/06-CONTEXT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `contracts/openapi/api-v1.yaml`
- `contracts/openapi/ai-service-v1.yaml`
- `contracts/constants.yaml`
- `backend/corp-rag-app/src/main/java/com/corprag/**`
- `backend/corp-rag-app/src/main/resources/db/migration/**`
- `frontend/**`
- `scripts/verify-contracts.py`

## Existing Backend Anchors

The Java chat layer is genuinely greenfield. There is no `ChatController`, no `service/chat` package, and no chat persistence migration. Phase 6 must add the schema, repositories, orchestration, REST controller, query audit, and tests.

Verified security/session classes:

- `backend/corp-rag-app/src/main/java/com/corprag/security/OriginRefererValidationFilter.java`
- `backend/corp-rag-app/src/main/java/com/corprag/config/SecurityConfig.java`
- `backend/corp-rag-app/src/main/java/com/corprag/config/AppSecurityProperties.java`
- `backend/corp-rag-app/src/main/java/com/corprag/security/MustChangePasswordFilter.java`
- `backend/corp-rag-app/src/main/java/com/corprag/service/auth/RefreshTokenService.java`

`SecurityConfig` disables Spring CSRF and relies on `OriginRefererValidationFilter` for unsafe cookie-authenticated `/api/v1/**` requests. The filter allows safe methods, skips bearer-token requests, and requires the request `Origin` or `Referer` to match configured frontend origins. No double-submit CSRF-token cookie was found. Frontend code must not try to set `Origin`; it should centralize `credentials: "include"` and ensure dev/prod origins match Java config.

Verified ProblemDetails/audit classes:

- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/ProblemDetailsWriter.java`
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/ProblemDetailsExceptionHandler.java`
- `backend/corp-rag-app/src/main/java/com/corprag/service/audit/AuditEventWriter.java`
- `backend/corp-rag-app/src/main/java/com/corprag/domain/AuditEventEntry.java`
- `backend/corp-rag-app/src/main/java/com/corprag/repository/AuditEventRepository.java`

`ProblemDetailsWriter` already emits RFC7807-style JSON with project fields `errorCode`, `correlationId`, and `details`. `contracts/constants.yaml` already defines `RATE_LIMIT_EXCEEDED` with status `429`, plus chat-related errors such as `CONVERSATION_NOT_FOUND` and `AI_SERVICE_UNAVAILABLE`. The rate-limit endpoint should reuse these conventions and add `Retry-After`.

`AuditEventWriter` writes to `audit_events` through the current MDC correlation id. The Phase 6 query audit should use the existing audit table, not a second query-audit table.

Suggested chat audit event shape:

| Outcome | Category | Event Type | Outcome | Entity | Details |
|---------|----------|------------|---------|--------|---------|
| answered | `CHAT` | `CHAT_QUERY_ANSWERED` | `SUCCESS` | conversation id | message ids, route, citation count, latency, model id |
| guard refusal | `CHAT` | `CHAT_QUERY_REFUSED_GUARD` | `DENIED` | conversation id | guard reason, status, message ids |
| no evidence | `CHAT` | `CHAT_QUERY_NO_EVIDENCE` | `SUCCESS` | conversation id | route, warnings, message ids |
| degraded | `CHAT` | `CHAT_QUERY_DEGRADED` | `DEGRADED` | conversation id | retry attempted, warnings, missing citation reason |
| timeout | `CHAT` | `CHAT_QUERY_TIMEOUT` | `FAILURE` | conversation id | timeout budget, message ids |
| unavailable | `CHAT` | `CHAT_QUERY_AI_UNAVAILABLE` | `FAILURE` | conversation id | upstream status/error kind, message ids |
| rate limit | `CHAT` | `CHAT_QUERY_RATE_LIMITED` | `DENIED` | user id or none | limit, retryAfterSeconds; no chat rows |

## Persistence Findings

Existing Java migrations use versioned Flyway files under `backend/corp-rag-app/src/main/resources/db/migration`. Existing tables include `users`, `roles`, `role_permissions`, `user_roles`, `documents`, `audit_events`, `outbox_events`, and `processed_events`. The next migration number after the current migration set is `V14__...`.

The FK target for conversation ownership should be `users(id)`. The `chat_` prefix is consistent with the need to avoid overloading existing audit/document tables and is acceptable for the new chat-owned tables.

The schema should remain:

- `chat_conversations`: `id`, `user_id`, `title`, `created_at`, `updated_at`, `deleted_at`
- `chat_messages`: `id`, `conversation_id`, `role`, `status`, `content`, `citations`, `retrieval_meta`, `confidence`, `correlation_id`, `created_at`, `deleted_at`

The implementation needs a repository query for Python history that returns the last N=10 successful `ANSWERED` pairs, not the last N filtered messages. The query must drop an entire failed/degraded pair and must never send a user question to Python without its paired answered assistant text.

## Contract Findings

`contracts/openapi/api-v1.yaml` already declares chat paths, but implementation does not exist yet. Contract-first work must happen before Java:

- Add nullable `Message.retrievalMeta`.
- Add assistant outcome/status to `Message` and query responses.
- Make `Message.content` nullable/optional enough to represent non-answered assistant outcomes without placeholder answer text.
- Align citations and retrieval metadata with JSONB snapshots.
- Fix and defer `/chat/messages/{messageId}/citations` because Phase 6 does not wire Python chunk detail service or a Java proxy.
- Preserve `conversationId` as required on `ChatQueryRequest`.
- Add/confirm the `Retry-After` header and `RATE_LIMIT_EXCEEDED` ProblemDetails response for `POST /chat/query`.

`contracts/openapi/ai-service-v1.yaml` already requires Python `QueryRequest.conversationId`. It also describes the real Python chunk detail path as `/v1/documents/{documentId}/chunks/{chunkId}`. Any Java API source-viewer description that mentions Python `GET /chunks/{chunkId}` is stale.

The correct contract verification command in this repo is `scripts/verify-contracts.py`. On this Windows runner, previous successful runs used:

```powershell
$env:MAVEN_CMD='C:\dev\apache-maven-3.9.15\bin\mvn.cmd'
uv run --project ai-service --group dev python scripts/verify-contracts.py
```

## Existing Admin/API Surface

Phase 2/3 controllers exist for auth, users, roles, user-role assignment, access policies, and documents. Phase 6 admin UI should consume these; it should not add backend admin endpoints silently.

Verified files:

- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/AuthController.java`
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/UserController.java`
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/RoleController.java`
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/UserRoleController.java`
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/AccessPolicyController.java`
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/DocumentController.java`

Self-lockout is enforced server-side in the existing backend for the critical paths researched:

- `UserController.updateUser` rejects self active-status changes.
- `UserService.deleteUser` rejects self deletion.
- `RoleService.replaceUserRoles` rejects the actor changing their own roles.
- `RoleService.updateRole` protects the last `users.update` authority.

The role editor still needs a permission-code source. No obvious REST endpoint dedicated to listing all permission codes was found. The OpenAPI `PermissionCode` enum and generated contract DTOs are the available source of truth. The frontend plan should derive its role-editor permission list from the contract, or explicitly flag a missing endpoint instead of inventing a free-text or frontend-only list.

## Frontend Findings

The frontend is still a static nginx shell:

- `frontend/index.html`
- `frontend/styles/base.css`
- `frontend/nginx.conf`
- `frontend/Dockerfile`

There is no framework, no package-level frontend app, and no router/API-client modules yet. Phase 6 can add vanilla JS modules under `frontend/js/**`, BEM component styles under `frontend/styles/**`, and reuse existing tokens in `frontend/styles/base.css`.

The frontend must be built around a single API client because the backend uses httpOnly cookie sessions and rotating refresh tokens. Concurrent 401s must single-flight through one `/auth/refresh` request; a burst of independent refresh calls can invalidate the refresh-token family.

## Source Viewer Findings

The Phase 6 source viewer can be implemented without any Python call because `Citation.quote` is required and carries document text. Full chunk detail remains deferred because `app.state.chunk_detail_service` is not wired on the Python side and the full-content path would need a Java proxy plus live message-ownership and document-access checks.

The UI should treat graph-route citations exactly like hybrid citations: render returned `quote`/`snippet` only, never internal `entity:X` markers.

## Validation Architecture

Recommended validation layers:

- Contract: `uv run --project ai-service --group dev python scripts/verify-contracts.py` with `MAVEN_CMD` set on Windows.
- Java unit/slice: `cd backend; mvn -q -pl corp-rag-app -am test` or the local Maven binary equivalent.
- Java contract compile: generated DTO compile through `verify-contracts` before implementation waves.
- Frontend static: `node --check` over new `frontend/js/**/*.js`, plus a grep/static check that feature modules do not call `fetch` directly.
- Browser/UAT: start the local compose/frontend stack and verify login, forced password change, chat lazy-create/query/history/source modal, and admin guarded routes.
- Audit evidence: inspect `audit_events` rows for chat outcomes and rate-limit denial with shared `correlation_id`.

Validation must start at Wave 1. The contract-first wave is not optional because Java generated DTOs and frontend message rendering both depend on the corrected `Message` and chat query shapes.

## Planning Implications

1. Wave 1 must update and verify contracts before any Java chat implementation.
2. The first backend implementation wave must add the Flyway chat schema and repositories before controllers.
3. Query audit and rate limiting should be designed with the query orchestrator, not bolted on after `/chat/query`.
4. The frontend app shell/API-client/router should land before chat/admin screens so both can share guards, nav, error mapping, and session refresh.
5. Admin screens should remain frontend-only over existing endpoints; any missing endpoint must be flagged in the plan as a backend gap.
6. Source viewing remains quote-only; full-content viewer, Java chunk proxy, and Python `chunk_detail_service` wiring belong to backlog.
