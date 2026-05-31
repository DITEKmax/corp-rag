---
phase: "06-chat-frontend-experience"
plan: "05"
subsystem: "java-chat-query-orchestration"
tags: ["java", "chat", "query", "audit", "rate-limit", "python-client"]

requires:
  - phase: "06-chat-frontend-experience"
    provides: "Plan 02 paired chat persistence"
  - phase: "06-chat-frontend-experience"
    provides: "Plan 03 limiter/audit/Python query client"
  - phase: "06-chat-frontend-experience"
    provides: "Plan 04 chat conversation REST controller"
provides:
  - "POST /api/v1/chat/query"
  - "Java query orchestration over Python /v1/query"
  - "BL-02 internal auto-retry and DEGRADED outcome"
  - "paired persistence and query audit for all processed outcomes"
affects: ["06-07", "06-09"]

tech-stack:
  added: []
  patterns: ["rate-limit before query processing", "answered-pair history assembler", "single persisted pair per processed query"]

key-files:
  created:
    - "backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatHistoryAssembler.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatQueryService.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatTitleService.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/service/chat/ChatHistoryAssemblerTest.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/service/chat/ChatQueryServiceTest.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/service/chat/ChatTitleServiceTest.java"
  modified:
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/ChatController.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatMessageMapper.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/ChatControllerTest.java"

key-decisions:
  - "429 is handled in ChatController before request validation/service/Python/chat writes; it emits only CHAT_QUERY_RATE_LIMITED audit."
  - "Python history is last 10 complete ANSWERED pairs; incomplete/failed/degraded pairs are dropped as pairs."
  - "BL-02 retry is one extra Java-side Python call in the same request; external history sees one persisted pair."
  - "No Python prompt or output-guard code was changed; Java persists DEGRADED if retry does not recover."

patterns-established:
  - "Processed non-429 outcomes append exactly one user row plus one assistant row with a shared correlation_id."
  - "REFUSED_GUARD, TIMEOUT, and AI_UNAVAILABLE persist rows, audit, then return ProblemDetails through existing handlers."
  - "NO_EVIDENCE and DEGRADED return 200 ChatQueryResponse status bubbles with no answer text/citation chips."

requirements-completed: ["CHAT-01", "CHAT-02"]

duration: "13 min"
completed: "2026-05-27"
---

# Phase 6 Plan 05: Chat Query Orchestration Summary

**`POST /api/v1/chat/query` now runs through Java, enforces the locked query lifecycle, calls Python only through the Java client, persists paired history, and audits every significant outcome.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-05-26T23:59:51+03:00
- **Completed:** 2026-05-27T00:12:31+03:00
- **Tasks:** 4
- **Files modified:** 9

## Accomplishments

- Added `/api/v1/chat/query` to `ChatController` with `chat.query` permission, per-user rate-limit gate, `Retry-After` 429 response, and rate-limit audit before service work.
- Added `ChatQueryService` to validate required `conversationId`, verify active owner-scoped conversation, resolve access filter, assemble answered-pair history, call Python `/v1/query`, map outcomes, persist paired rows, audit, and return contract-aligned responses/problems.
- Added `ChatHistoryAssembler` to load and sanitize last-10 ANSWERED user+assistant pairs, preventing dangling user-only history from reaching Python.
- Added `ChatTitleService` for one-time placeholder-to-first-message title derivation through the existing repository guard.
- Reused `ChatMessageMapper` for fresh response citation/retrievalMeta DTO mapping.
- Added tests for rate limit, correlation ID propagation, answered/no-evidence/degraded/guard/timeout outcomes, BL-02 auto-retry, paired persistence, title derivation, and answered-pair history filtering.

## Status Mapping

- `ANSWERED`: Python `answered=true` with valid displayable citations. Persists answer text, citations snapshot, confidence, retrievalMeta; returns 200.
- `NO_EVIDENCE`: Python `answered=false`. Persists status plus retrievalMeta when present, no answer text/citations; returns 200.
- `DEGRADED`: missing/invalid citations after one internal retry. Persists status only plus retrievalMeta if available, no answer text/citations; returns 200.
- `REFUSED_GUARD`: Python guard 422. Persists paired rows, audits, then returns 422 ProblemDetails.
- `TIMEOUT`: Python timeout. Persists paired rows, audits, then returns 503 ProblemDetails.
- `AI_UNAVAILABLE`: Python 503/connection/unknown upstream problem. Persists paired rows, audits, then returns 503 ProblemDetails.
- `RATE_LIMITED`: 429 before service/Python/DB writes. Emits audit only; no chat rows and no `updated_at` bump.

## Audit Events

- `CHAT_QUERY_ANSWERED`
- `CHAT_QUERY_REFUSED_GUARD`
- `CHAT_QUERY_NO_EVIDENCE`
- `CHAT_QUERY_DEGRADED`
- `CHAT_QUERY_TIMEOUT`
- `CHAT_QUERY_AI_UNAVAILABLE`
- `CHAT_QUERY_RATE_LIMITED`

## Task Commits

1. **Tasks 1-4: Query endpoint, history/title helpers, outcome mapping, persistence, and tests** - `1455191` (`feat(06-05): add chat query orchestration`)

## Deviations from Plan

- No Python synthesis prompt hardening was performed. This honors the execution guardrail: Java `DEGRADED` is the Phase 6 deliverable if BL-02 retry still fails.

## Issues Encountered

- The first focused test run had an over-specific title truncation assertion; the test now checks the actual contract: normalized, bounded, ellipsized title.

## Verification

- `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test -Dtest=*ChatQueryService*,*ChatHistoryAssembler*,*ChatTitleService*,*ChatController* -Dsurefire.failIfNoSpecifiedTests=false` exited 0.
- `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test -DskipTests=false` exited 0.
- `git diff --check` exited 0.
- `git diff --name-only` before commit showed only Java chat/controller/test files; no Python files were modified.

## Plan 09 UAT Notes

- Live chat UAT needs a query-visible corpus; otherwise CHAT-02 can legitimately return `NO_EVIDENCE`. Live UAT on 2026-05-31 confirmed the retained Phase 5 corpus was still present, so reindex is only needed if that visibility check fails.
- Run one untimed reranker pre-warm query before timed live checks to avoid cold-reranker timeout noise.

## User Setup Required

None for unit/integration tests. Live Python UAT remains Plan 09.

## Next Phase Readiness

Ready for Plan 06-06. The frontend API client can rely on Java-only chat endpoints, 429 ProblemDetails with `Retry-After`, and stable message statuses.

---
*Phase: 06-chat-frontend-experience*
*Completed: 2026-05-27*
