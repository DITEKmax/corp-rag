---
status: partial
phase: 06-chat-frontend-experience
source: [06-VERIFICATION.md]
started: 2026-05-27
updated: 2026-06-01
---

# Phase 6 Human UAT

## Current Test

Live browser/API UAT ran on 2026-05-31 with the Java backend rebuilt from current code and the frontend still on a stale pre-Phase-6 image. Follow-up live UAT on 2026-06-01 confirmed several fixes and found Round 2 issues in users pagination, draft chat send state, cited synthesis stability, graph indexing degradation, and raw document URLs. The known Phase 5 corpus was still present; reindex was not required.

## Tests

### 1. Session Flow

expected: `/me` bootstrap, login, forced password change, refresh, logout, access denied, and service-unavailable behavior work in browser.
result: pending

### 2. Chat Flow

expected: lazy create, query, outcomes, retry, history reload, soft delete, and 429 behavior work through Java.
result: partial

evidence:
- API lifecycle passed for create, list, messages, failed outcome visibility, idempotent delete, and soft-delete persistence.
- Java `/chat/query` ANSWERED path was blocked by missing `JAVA_AI_BASE_URL` in compose, causing `AI_SERVICE_UNAVAILABLE`.
- Direct Python `/v1/query` proved ANSWERED, NO_EVIDENCE, UNSUPPORTED, REFUSED/missing_citations, DEGRADED/reranker_unavailable, and AI_UNAVAILABLE outcomes are observable.
- Rate limiting switched to 429 on request 31 with `Retry-After`; rate-limited requests created audit rows but no `chat_messages`.

### 3. Source Modal

expected: cited source opens from returned quote/snippet only and displays document text, never graph markers.
result: blocked by stale frontend image

### 4. Admin Console

expected: full and partial admins can exercise permitted document, user, role, and access-policy workflows.
result: blocked by stale frontend image

### 5. Audit/Correlation

expected: live DB/audit evidence confirms shared query correlation ids and 429 audit-without-chat-row behavior.
result: pass

evidence:
- User and assistant rows share one `correlation_id`.
- Five `CHAT_QUERY_RATE_LIMITED` audit rows were observed.
- Zero `chat_messages` rows were observed for rate-limited correlation ids.
- The audit timestamp column is `occurred_at`, not `created_at`.
- Document upload time is `documents.uploaded_at`, not `created_at`; document lifecycle statuses are `UPLOADED`, `INDEXING`, `INDEXED`, and `INDEXING_FAILED`.

### 6. Runbook Drift

expected: live UAT runbook points operators at fresh images and correct DB columns.
result: updated

evidence:
- Compose image tags remain static `phase1`; freshness must be checked by image `CREATED` time after rebuilding changed services.
- Live UAT should rebuild `java-backend` and `frontend` for backend/frontend code changes, and rebuild `python-ai` when `ai-service` code changes.

## Summary

total: 5
passed: 1
issues: 5
pending: 1
skipped: 0
blocked: 2
