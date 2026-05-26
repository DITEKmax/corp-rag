---
phase: "06-chat-frontend-experience"
plan: "03"
subsystem: "java-chat-query-foundation"
tags: ["java", "chat", "rate-limit", "audit", "python-client"]

requires:
  - phase: "06-chat-frontend-experience"
    provides: "Plan 01 contract status/retrievalMeta shape"
  - phase: "06-chat-frontend-experience"
    provides: "Plan 02 chat persistence and answered-pair history records"
  - phase: "05-retrieval-guards-query-api"
    provides: "Python /v1/query contract and guard/degraded outcomes"
provides:
  - "in-memory per-user POST /chat/query rate limiter"
  - "controller-facing RFC7807 429 writer with Retry-After"
  - "query audit helper and concrete event taxonomy"
  - "bounded Java RestClient for Python /v1/query"
affects: ["06-04", "06-05"]

tech-stack:
  added: []
  patterns: ["controller-facing helpers before controller implementation", "single Python query client with no chunk-detail path", "thread-safe in-memory token bucket"]

key-files:
  created:
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/ai/PythonQueryClient.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/config/AiServiceClientConfig.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/config/AiServiceProperties.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatQueryAuditService.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatRateLimitProblemWriter.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatRateLimiter.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/adapter/ai/PythonQueryClientTest.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/service/chat/ChatQueryAuditServiceTest.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/service/chat/ChatRateLimiterTest.java"
  modified:
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/ProblemDetailsWriter.java"
    - "backend/corp-rag-app/src/main/resources/application.yml"

key-decisions:
  - "Rate limiting is per authenticated userId, in-memory per Java instance, and counted before guard/Python/DB writes."
  - "429 uses existing ProblemDetails field names plus Retry-After; it emits audit but no chat rows."
  - "PythonQueryClient calls only POST /v1/query and never the deferred chunk-detail/source-viewer path."
  - "Default AI read timeout is 150s so Java can cover Python's 120s budget plus BL-02 internal retry/cold-reranker overhead."

patterns-established:
  - "Chat query audit events carry IDs, status, retrieval diagnostics, and upstream error metadata but not prompt/answer/quote/citation text."
  - "Single-flight/browser refresh remains frontend-owned; Java-side Python client is bounded by RestClient timeouts."
  - "Plan 03 creates no ChatController; Plan 04 owns REST endpoints."

requirements-completed: ["CHAT-02"]

duration: "14 min"
completed: "2026-05-26"
---

# Phase 6 Plan 03: Chat Query Foundation Summary

**The Java backend now has the shared query plumbing needed by the chat controller: rate limiting, audit event writing, and a bounded Python `/v1/query` client.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-05-26T23:35:40+03:00
- **Completed:** 2026-05-26T23:49:26+03:00
- **Tasks:** 4
- **Files modified:** 11

## Accomplishments

- Added `ChatRateLimiter`, a thread-safe per-user token bucket with a 30 requests/minute default and lazy stale-bucket cleanup.
- Added `ChatRateLimitProblemWriter` for controller-facing 429 responses with `Retry-After`, existing ProblemDetails shape, `RATE_LIMIT_EXCEEDED`, and correlation ID support.
- Added `ChatQueryAuditService` with concrete events for answered, guard refusal, no evidence, degraded, timeout, AI unavailable, and rate limited query outcomes.
- Extended `ProblemDetailsWriter` with a details-map overload so 429 can reuse the project ProblemDetails mechanism without ad-hoc response fields.
- Added `AiServiceProperties` and `AiServiceClientConfig` for a qualified Python AI `RestClient` with bounded connect/read timeouts.
- Added `PythonQueryClient` that maps Java chat query commands to Python `/v1/query`, includes required `conversationId`, converts answered-pair history, and returns typed outcomes for guard, degraded, timeout, unavailable, and generic problem cases.
- Added unit tests for limiter concurrency/window behavior, 429 response shape, audit event payloads, and Python client request/outcome mapping.

## Task Commits

1. **Tasks 1-4: Limiter, audit helper, Python client, and tests** - `240496b` (`feat(06-03): add chat query foundation`)

## Files Created/Modified

- `backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatRateLimiter.java` - In-memory per-user limiter.
- `backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatRateLimitProblemWriter.java` - RFC7807 429 writer with `Retry-After`.
- `backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatQueryAuditService.java` - Query audit event taxonomy and safe details mapping.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/ai/PythonQueryClient.java` - Java client for Python `/v1/query`.
- `backend/corp-rag-app/src/main/java/com/corprag/config/AiServiceClientConfig.java` - Qualified AI RestClient bean.
- `backend/corp-rag-app/src/main/java/com/corprag/config/AiServiceProperties.java` - AI service timeout/base-url configuration.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/ProblemDetailsWriter.java` - Details-map overload.
- `backend/corp-rag-app/src/main/resources/application.yml` - `app.ai-service` defaults.
- `backend/corp-rag-app/src/test/java/com/corprag/service/chat/ChatRateLimiterTest.java` - Limiter and 429 tests.
- `backend/corp-rag-app/src/test/java/com/corprag/service/chat/ChatQueryAuditServiceTest.java` - Audit payload tests.
- `backend/corp-rag-app/src/test/java/com/corprag/adapter/ai/PythonQueryClientTest.java` - Python client adapter tests.

## Decisions Made

- Kept the limiter self-contained and in-memory only; no Redis, JDBC, repository, or shared-cache dependency was introduced.
- Used `150s` as the default Java read timeout to stay above Python's query timeout and leave room for the BL-02 internal retry path.
- Treated missing/invalid citation ProblemDetails as `DEGRADED`, preserving the strict output guard while giving Plan 05 a typed outcome to persist.
- Kept rate-limit audit rows separate from chat persistence: user-scoped event, no conversation/message IDs, and no history row.

## Deviations from Plan

None - plan scope was executed as written. The BL-02 prompt-hardening item remains backlog/optional and was not implemented in Python.

## Issues Encountered

- `ChatRateLimiter.Decision.allowed()` conflicted with the record accessor name; the static factory was renamed to `permitted()`.
- PowerShell required Maven `--%` passthrough for dotted `-D` test properties.

## Verification

- `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test -Dtest=*ChatRateLimiter*,*ChatQueryAudit*,*PythonQueryClient* -Dsurefire.failIfNoSpecifiedTests=false` exited 0.
- `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test -DskipTests=false` exited 0.
- `rg -n "class ChatController|@.*Controller" backend/corp-rag-app/src/main/java/com/corprag/service/chat backend/corp-rag-app/src/main/java/com/corprag/adapter/ai backend/corp-rag-app/src/main/java/com/corprag/config` returned no matches.
- `rg -n "Redis|redis|Jdbc|Repository|DataSource" backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatRateLimiter.java` returned no matches.
- `rg -n "/v1/documents|chunks|chunk" backend/corp-rag-app/src/main/java/com/corprag/adapter/ai/PythonQueryClient.java` returned no matches.

## User Setup Required

None.

## Next Phase Readiness

Ready for Plan 06-04. The REST controller can use the limiter, 429 writer, audit helper, repositories, and Python client without revisiting Plan 03 config or source-viewer scope.

---
*Phase: 06-chat-frontend-experience*
*Completed: 2026-05-26*
