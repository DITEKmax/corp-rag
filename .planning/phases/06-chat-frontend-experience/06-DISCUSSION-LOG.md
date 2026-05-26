# Phase 6: Chat & Frontend Experience - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md; this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 6-Chat & Frontend Experience
**Areas discussed:** Conversation behavior, Citation and source viewer behavior, Admin workflow shape, Frontend app shell and session flow, Rate limiting, Chat persistence schema

---

## Conversation Behavior

| Question | Options Considered | Selected |
|---|---|---|
| Conversation lifecycle | Include delete; Append-only; Soft-hide only | Include delete as soft-delete |
| Refused/degraded/failure persistence | Save user + assistant outcome; Save user only; Save only successful exchanges | Save user + assistant outcome |
| Retry behavior | Retry creates a new pair; Retry replaces assistant row; No explicit retry | Retry creates a new pair |
| Conversation ordering | Latest activity; Created time; Newest answered only | Latest activity |

**User's choices:** Implement contracted DELETE as idempotent soft-delete; persist every processed query as exactly one user row plus one assistant-outcome row; retry manually as a new pair; sort conversations by `updated_at DESC`.

**Notes:** Rate-limit `429` is not persisted. Failed/refused rows stay visible but are excluded from Python history. Conversation title is derived from first user message and remains immutable after derivation.

---

## Citation And Source Viewer Behavior

| Question | Options Considered | Selected |
|---|---|---|
| Source viewer scope | MVP quote/snippet modal; Full-content source viewer | MVP quote/snippet modal |
| BL-02 missing citations UI | Degraded bubble with text; Compact retry state; Normal refusal | Compact retry state |
| Citation persistence | JSONB snapshot; Separate table; Chunk IDs only | JSONB snapshot |
| Store RetrievalMeta | Store JSONB; Do not store | Store JSONB |
| Return RetrievalMeta in history | Add nullable `Message.retrievalMeta`; Store only | Add nullable `Message.retrievalMeta` |

**User's choices:** Source modal renders from returned citation fields only. BL-02 shows no answer text and no chips. Citations and retrieval metadata are JSONB snapshots on assistant rows. `Message` includes nullable `retrievalMeta`.

**Notes:** Full-content source viewer is deferred because Python chunk detail service is not wired and would require Java proxy plus message-ownership checks. Output guard remains strict.

---

## Admin Workflow Shape

| Question | Options Considered | Selected |
|---|---|---|
| Admin completeness | Compact operational screens; Full CRUD console; Core happy paths only | Compact operational screens |
| Admin organization | Single tabs; Separate routes; Dashboard plus pages | Separate routes |
| Documents functionality | List/upload/delete/status/raw; No raw link; Read-only plus upload | List/upload/delete/status/raw |
| User/role editing | Tables plus drawers; Detail pages; Minimal modals | Tables plus drawers |

**User's choices:** Build compact operational admin screens across documents, users, roles, user-role assignment, and access policies over already implemented endpoints. Use separate guarded routes under one admin layout.

**Notes:** No new admin backend should be added silently. Permission-gated nav and routes are mandatory. Self-lockout must be verified server-side.

---

## Frontend App Shell And Session Flow

| Question | Options Considered | Selected |
|---|---|---|
| Bootstrap strategy | Session-first; Route-first; Login-only | Session-first |
| Session refresh | Refresh once on 401; No auto-refresh; Timer-based refresh | Refresh once with single-flight |
| CSRF/Origin handling | Centralized API client; Per-module; Browser default only | Centralized API client, no manual Origin |
| Route/nav permissions | Declarative route table; Per-page guards; Separate route/nav configs | Declarative route table |

**User's choices:** Call `/me` before rendering protected route content; use memory-only session state; honor forced password change; implement single-flight refresh because refresh tokens rotate by family; use one API client and one route table for guards/nav.

**Notes:** The frontend cannot set the forbidden `Origin` header. Planning must verify whether Java uses Origin/Referer-only checks or a double-submit CSRF token.

---

## Rate Limiting

| Option | Description | Selected |
|---|---|---|
| In-memory per Java instance | 30 req/min per user, checked before guard/Python/DB writes | Yes |
| Postgres-backed limiter | Cross-instance accurate, DB write per query | No |
| Redis/shared cache | Distributed limiter with new infrastructure | No |

**User's choice:** Implement an in-memory per-user Java limiter for `POST /chat/query` only.

**Notes:** `429` returns RFC7807 ProblemDetails using existing field conventions, includes correlationId and `Retry-After`, emits a light audit row, and creates no chat rows.

---

## Chat Persistence Schema

| Option | Description | Selected |
|---|---|---|
| Single `chat_messages` table | One ordered stream with role/status checks | Yes |
| Split user/assistant tables | Stronger row-type constraints, harder reads | No |
| Single table plus pair fields | More explicit pairing, extra complexity | No |

**User's choice:** Use `chat_conversations` and one `chat_messages` table in Java PostgreSQL via Flyway. JSONB handles citations and retrieval metadata.

**Notes:** `content` is nullable for non-answered assistant outcomes. `correlation_id` is shared by the user/assistant pair written for one request. Verify FK targets, naming conventions, and soft-delete implementation against existing migrations.

---

## the agent's Discretion

- Exact Java class/package names within existing backend patterns.
- Exact frontend module/component boundaries within the locked vanilla/BEM/router/API-client design.
- Exact qualitative confidence labels and user-facing copy for degraded/refusal states.
- Exact in-memory limiter algorithm details, as long as behavior remains per-user, thread-safe, 30/minute, and pre-persistence.

## Deferred Ideas

- Full-content source viewer and `/chat/messages/{messageId}/citations`.
- Distributed Redis/shared-store rate limiter.
- Redis RAG answer caching with access-scope and corpus-version-safe keys.
- Conversation restore/recovery or hidden-vs-deleted behavior.
- Conversation list last-outcome badges.
- Admin dashboard, drawer deep-links, and richer admin UX polish.
