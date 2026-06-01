# Phase 6 UAT Checklist

## Prerequisites

- Run Java backend, Python AI service, Postgres, MinIO, RabbitMQ, Qdrant, Neo4j, and frontend.
- Rebuild images for services whose code changed before live UAT. The compose image tags are static `phase1`; verify image freshness by `CREATED`, not by tag name. Rebuild `java-backend` and `frontend` for backend/frontend fixes, and rebuild `python-ai` whenever `ai-service` code changes.
- Use authenticated browser sessions with:
  - full admin permissions,
  - partial admin permissions,
  - normal `chat.query` user.
- For CHAT-02 live answer checks, first verify the known Phase 5 corpus is still query-visible. Live UAT on 2026-05-31 confirmed Qdrant `documents_chunks` was green with 4 points: `TechCorp Phase 5 Query Policy`, `TechCorp Approved Vendor List`, `TechCorp Q1 2026 Security Incident Report`, and `Acme Remote Work Policy`.
- Re-upload/reindex a known document only if the corpus visibility check fails.
- Set or record `AI_QUERY_LIVE_CORPUS_READY=true` only after the corpus is indexed/query-visible or the retained corpus has been verified.
- Run one untimed reranker pre-warm query before timed live CHAT-02 checks to avoid cold-reranker timeout noise.
- Do not commit secrets from `infra/.env`.

## Automated Baseline

- [ ] Contract verifier: `uv run --project ai-service --group dev python scripts/verify-contracts.py`
- [ ] Backend tests: `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test -DskipTests=false`
- [ ] Frontend JS syntax: run `node --check` for every `frontend/js/**/*.js`.
- [ ] Direct fetch gate: only `frontend/js/core/api-client.js` may match regex `(?<![A-Za-z_])fetch\(`
- [ ] Python/deferred endpoint gate: frontend contains no Python `:8000`, `/v1/query`, chunk-detail, or deferred citation-detail endpoint references.
- [ ] Permission-code generation: `uv run python scripts/generate_frontend_permission_codes.py --check`
- [ ] No new Redis/shared cache/Mongo/non-relational Phase 6 infrastructure.

## UI-01 Session Flow

- [ ] Initial load calls `/api/v1/me` before protected route content renders.
- [ ] No session redirects to `#/login` and preserves the requested route.
- [ ] Login succeeds with cookie auth and returns to the requested route.
- [ ] `mustChangePassword=true` redirects to `#/change-password` and blocks all other app routes.
- [ ] Reactive `PASSWORD_CHANGE_REQUIRED` ProblemDetails also redirects to `#/change-password`.
- [ ] Access-token 401 refresh is single-flight and retries the original request once.
- [ ] `/me` 5xx shows service unavailable with retry, not login.
- [ ] Logout clears memory state and routes to login.

## CHAT-01 Conversation Lifecycle

- [ ] `POST /chat/conversations` creates a conversation before the first `POST /chat/query`; `/chat/query` always has `conversationId`.
- [ ] Title starts as placeholder and changes only once to the first-message-derived title.
- [ ] Conversation list shows non-deleted conversations ordered by `updatedAt DESC`.
- [ ] Conversation row fields are title, updatedAt, and messageCount.
- [ ] `GET /chat/conversations/{id}/messages` shows persisted user and assistant rows, including refused/failed rows.
- [ ] `DELETE /chat/conversations/{id}` returns 204, is idempotent, hides the conversation from list/messages, and uses soft-delete server behavior.

## CHAT-02 Query Outcomes

- [ ] ANSWERED: one user row plus one assistant row share a correlation id; answer, qualitative confidence, citations, source chips, and diagnostics render.
- [ ] NO_EVIDENCE: visible assistant outcome with no retry and no fabricated answer.
- [ ] REFUSED_GUARD: 422 persists a visible guard-refusal assistant row; no retry button.
- [ ] DEGRADED / BL-02: strict output guard remains; UI shows compact retry state with no answer text and no citation chips.
- [ ] TIMEOUT: visible retry-focused assistant row.
- [ ] AI_UNAVAILABLE: visible retry-focused assistant row.
- [ ] Manual retry appears only for DEGRADED, TIMEOUT, and AI_UNAVAILABLE, and posts the same text as a new user+assistant pair.
- [ ] Failed/degraded pairs remain visible but are excluded from Python history as whole pairs.
- [ ] 429 rate limit returns ProblemDetails with `Retry-After`, creates no chat rows, and does not bump `updatedAt`.

## UI-02 Citations And Source Modal

- [ ] Citation chips map inline `[N]` to `citations[N-1]`.
- [ ] Chip preview uses `snippet`.
- [ ] Source modal renders only returned Citation fields: `documentTitle`, `sectionPath`, `quote`, `pageNumber`, and `accessLevel`.
- [ ] Source modal makes zero network calls.
- [ ] Source modal shows document text only and never renders `entity:X` / graph markers as normal text.
- [ ] `retrievalMeta` diagnostics are collapsed by default and hidden when null.

## UI-03 Admin Console

- [ ] Admin nav is permission-filtered from the shared route table.
- [ ] Forbidden direct admin route shows access denied, not blank content and not login when authenticated.
- [ ] Documents: list, upload, indexing/failure status, raw-open per click, delete with confirmation.
- [ ] Users: list, create, disable with confirmation, reset password with confirmation, user-role replace inside `#/admin/users`.
- [ ] Roles: list, create, edit permission set using generated PermissionCode checkboxes.
- [ ] Access policies: list, create attached to role, edit policy scope, delete with confirmation.
- [ ] Partial admin sessions see only permitted nav and mutation actions.
- [ ] Backend self-lockout is enforced for self-disable/self-role changes and last-admin protection.

## Audit And Correlation

- [ ] Audit rows exist for significant chat outcomes: answered, guard refusal, no evidence, degraded, timeout/unavailable, and rate-limited when exercised.
- [ ] Persisted user+assistant query rows share `correlation_id`.
- [ ] 429 has an audit event but no chat rows.
- [ ] ProblemDetails include correlationId.
- [ ] DB checks use `audit_events.occurred_at` for audit time and `documents.uploaded_at` for document upload time; document lifecycle statuses are `UPLOADED`, `INDEXING`, `INDEXED`, and `INDEXING_FAILED`.

## Do-Not-Break Gates

- [ ] Output guard remains strict; no code weakens guard validation to pass probes.
- [ ] BL-02 missing citations surfaces graceful DEGRADED/retry UI, never an empty bubble.
- [ ] Source viewer displays document text only, never graph/entity markers.
- [ ] Browser talks only to Java `/api/v1`, never Python.
- [ ] No Redis/shared cache/Mongo/new Phase 6 infrastructure is introduced.

## Backlog Confirmation

- [ ] Distributed Redis rate limiter remains deferred.
- [ ] RAG answer caching remains deferred and must include access scope plus corpus version in any future cache key.
- [ ] Full-content source viewer remains deferred; future implementation needs Python chunk detail wiring, Java proxy, and Java message-ownership/access checks.
