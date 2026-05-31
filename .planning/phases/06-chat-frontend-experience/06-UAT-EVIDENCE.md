# Phase 6 UAT Evidence

Execution dates: 2026-05-27 automated baseline; 2026-05-31 live browser/API UAT update.

## Automated Checks

| Check | Command | Result |
|-------|---------|--------|
| Contract verifier | `$env:MAVEN_CMD='C:\dev\apache-maven-3.9.15\bin\mvn.cmd'; uv run --project ai-service --group dev python scripts/verify-contracts.py` | PASS |
| Backend tests | `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test -DskipTests=false` from `backend/` | PASS |
| Frontend JS syntax | PowerShell loop over `frontend/js/**/*.js` with `node --check` | PASS, 29 JS files |
| Direct fetch boundary | `rg -n -P "(?<![A-Za-z_])fetch\(" frontend/js -g "*.js"` | PASS: only `frontend/js/core/api-client.js` matched |
| No Python/deferred endpoint references | `rg -n "localhost:8000|127\.0\.0\.1:8000|:8000|/v1/query|/chunks|chunk_detail|chat/messages/.*/citations|#/admin/user-roles" frontend/js frontend/styles` | PASS: no matches |
| Permission-code generation | `uv run python scripts/generate_frontend_permission_codes.py --check` | PASS |
| No Redis/Mongo/shared cache in runtime code/config | `rg -n "redis|mongo|shared cache" infra backend ai-service frontend --glob "!**/target/**" --glob "!**/.venv/**" --glob "!**/__pycache__/**"` | PASS: no matches |
| Compose service list | `docker compose -f infra/docker-compose.yml config --services` | PASS: postgres, minio, rabbitmq, qdrant, neo4j, langfuse, java-backend, python-ai, frontend |

## Live UAT Update 2026-05-31

The live stack had Java backend rebuilt from current code. The frontend image was stale (`corp-rag-frontend:phase1`, created before Phase 6), so browser UI-01/02/03 could not be completed until the frontend image is rebuilt.

Runtime fixes applied after this UAT:

- `BLOCK-1`: `infra/docker-compose.yml` now sets `JAVA_AI_BASE_URL` to `http://python-ai:8000` by default for the Docker network.
- `BLOCK-2`: `frontend/Dockerfile` now copies `js/`, and nginx proxies `/api/v1/` to `java-backend:8080`; `api-client.js` defaults to relative `/api/v1`.
- `DEFECT-01a`: Python `DocumentResultPublisher` emits `indexedAt` through the shared ISO-8601 UTC formatter.
- `DEFECT-01b`: Java document-indexed and document-failed AMQP consumers reject invalid envelope/payload messages with `AmqpRejectAndDontRequeueException`, allowing the existing DLQ bindings to catch poison messages.
- `DEFECT-02`: factual numeric deadline lookups such as "In how many business days..." route to `FACTUAL`/HYBRID instead of `AGGREGATION`/GRAPH.
- `BUILD-01`: `corp-rag-contracts` runs `scripts/generate_constants.py` during Maven `generate-sources`.

The earlier prep note about direct `http://localhost:8080/api/v1` is superseded by the nginx `/api/v1/` proxy.

## Browser/API UAT Status

Live UAT on 2026-05-31 was partial.

Passed on the rebuilt backend/API path:

- Backend unit and integration suite passed with 142 tests, 0 failures/errors/skips during UAT.
- Cross-origin validation passed: `Origin: http://localhost` accepted and `Origin: http://evil.example` rejected with `ORIGIN_VALIDATION_FAILED`.
- CHAT-01 API lifecycle passed: create, list, messages, failed assistant row visibility, idempotent delete, post-delete list, and DB soft-delete.
- CHAT-02 outcomes were observable across Java/Python direct checks: ANSWERED, NO_EVIDENCE, UNSUPPORTED, REFUSED/missing_citations, DEGRADED/reranker_unavailable, and AI_UNAVAILABLE.
- Rate limit moved from 503 to 429 on request 31; 429 produced audit rows and no chat message rows.

Blocked before fixes:

- Java `/chat/query` ANSWERED path was blocked by missing Docker-network `JAVA_AI_BASE_URL`, causing `AI_SERVICE_UNAVAILABLE`.
- Browser UI-01/UI-02/UI-03 were blocked by stale frontend image content.
- One factual "how many business days" query routed to `AGGREGATION` and failed output guard with `missing_citations` despite the fact being citeable through `FACTUAL`.

## Requirement Evidence Map

| Requirement | Automated evidence | Browser/live evidence | Status |
|-------------|--------------------|-----------------------|--------|
| CHAT-01 | Backend tests passed; `ChatRepositoryPersistenceIT` covers conversation/message persistence, shared correlation ids, history pairing, and soft-delete behavior. | API lifecycle passed on 2026-05-31 | PASS |
| CHAT-02 | Backend tests passed; `ChatQueryServiceTest`, `ChatControllerTest`, `ChatRateLimiterTest`, and `PythonQueryClientTest` cover query outcomes, 429, Retry-After, Java-to-Python boundary, and persisted pairs. | Partial: outcomes observed, Java ANSWERED blocked before `JAVA_AI_BASE_URL` fix | PARTIAL |
| UI-01 | Frontend syntax/static checks passed; app shell/router/API client implementation is present. | Blocked by stale frontend image before rebuild | BLOCKED |
| UI-02 | Frontend syntax/static checks passed; static grep proves no Python/deferred source endpoint references. | Blocked by stale frontend image before rebuild | BLOCKED |
| UI-03 | Frontend syntax/static checks passed; admin endpoint coverage/self-lockout were verified from backend code. | Blocked by stale frontend image before rebuild | BLOCKED |

## Audit And Correlation Evidence

Automated/code evidence:

- `AuditEventRepository` persists `correlation_id`.
- `ChatMessageRepository.appendPair` rejects user/assistant pairs with different correlation ids.
- `ChatRepositoryPersistenceIT` asserts user and assistant rows share the same correlation id.
- `ChatQueryServiceTest` asserts the request correlation id is sent to Python and persisted on both pair rows.
- `ChatControllerTest` asserts 429 includes `Retry-After`, returns `RATE_LIMIT_EXCEEDED`, and calls `queryAuditService.rateLimited(...)`.
- `ChatQueryAuditServiceTest` asserts `CHAT_QUERY_RATE_LIMITED` audit details include `status=RATE_LIMITED`.
- `ChatRateLimiterTest` asserts 429 ProblemDetails include `RATE_LIMIT_EXCEEDED`, `retryAfterSeconds`, and `correlationId`.

Live DB evidence from 2026-05-31:

- Five `CHAT_QUERY_RATE_LIMITED` audit rows were observed.
- Zero `chat_messages` rows were observed for rate-limited correlation ids.
- User and assistant message pairs shared one `correlation_id`.
- The audit timestamp column is `occurred_at`, not `created_at`.

## Do-Not-Break Evidence

- Output guard code was not weakened in Phase 6; Plan 05 explicitly did not edit Python synthesis/guard code.
- BL-02 UI behavior is implemented as `DEGRADED`: compact retry bubble, no answer text, no citation chips.
- Source modal uses returned citation snapshot fields only and makes zero network calls.
- Source modal treats `entity:*` marker-like quote text as a rendering error instead of normal document text.
- Static grep found no frontend Python direct calls.

## Backlog Confirmed Not Implemented

- Distributed Redis rate limiter remains deferred.
- RAG answer caching remains deferred; future cache keys must include resolved access scope and corpus version.
- Full-content source viewer remains deferred; future work needs Python chunk-detail wiring, Java proxy, and Java message-ownership/access checks.

## Residual Risk

The codebase is automated-green, but Phase 6 browser UAT must be rerun after applying the runtime env change and rebuilding the frontend image. Reindex is not required while the retained Phase 5 corpus remains query-visible.
