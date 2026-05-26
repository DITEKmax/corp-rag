# Phase 6 UAT Evidence

Execution date: 2026-05-27

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

## Runtime Fix Found During UAT Prep

The frontend container serves static files on `http://localhost`, while Java runs on `http://localhost:8080`. A relative API base would call frontend nginx instead of Java. Fixed in `1deb747`:

- `frontend/js/core/api-client.js` now defaults to `http://localhost:8080/api/v1`.
- `window.CORP_RAG_API_BASE` can override the Java API base before `/js/app.js` loads.
- Java CORS/Origin config already allows `http://localhost` and `http://localhost:80`.

## Browser UAT Status

Live browser UAT was not executed in this environment.

Evidence:

- `docker compose -f infra/docker-compose.yml ps` returned no running services.
- CHAT-02 live checks require a freshly indexed corpus, `AI_QUERY_LIVE_CORPUS_READY=true`, and one untimed reranker pre-warm query. Those prerequisites were not established in this run.
- Authenticated full-admin, partial-admin, and normal chat browser sessions were not available.

This is recorded as a UAT blocker, not as a pass.

## Requirement Evidence Map

| Requirement | Automated evidence | Browser/live evidence | Status |
|-------------|--------------------|-----------------------|--------|
| CHAT-01 | Backend tests passed; `ChatRepositoryPersistenceIT` covers conversation/message persistence, shared correlation ids, history pairing, and soft-delete behavior. | Not run | PARTIAL |
| CHAT-02 | Backend tests passed; `ChatQueryServiceTest`, `ChatControllerTest`, `ChatRateLimiterTest`, and `PythonQueryClientTest` cover query outcomes, 429, Retry-After, Java-to-Python boundary, and persisted pairs. | Not run because live corpus/stack prerequisites were absent | PARTIAL |
| UI-01 | Frontend syntax/static checks passed; app shell/router/API client implementation is present. | Not run | PARTIAL |
| UI-02 | Frontend syntax/static checks passed; static grep proves no Python/deferred source endpoint references. | Not run | PARTIAL |
| UI-03 | Frontend syntax/static checks passed; admin endpoint coverage/self-lockout were verified from backend code. | Not run | PARTIAL |

## Audit And Correlation Evidence

Automated/code evidence:

- `AuditEventRepository` persists `correlation_id`.
- `ChatMessageRepository.appendPair` rejects user/assistant pairs with different correlation ids.
- `ChatRepositoryPersistenceIT` asserts user and assistant rows share the same correlation id.
- `ChatQueryServiceTest` asserts the request correlation id is sent to Python and persisted on both pair rows.
- `ChatControllerTest` asserts 429 includes `Retry-After`, returns `RATE_LIMIT_EXCEEDED`, and calls `queryAuditService.rateLimited(...)`.
- `ChatQueryAuditServiceTest` asserts `CHAT_QUERY_RATE_LIMITED` audit details include `status=RATE_LIMITED`.
- `ChatRateLimiterTest` asserts 429 ProblemDetails include `RATE_LIMIT_EXCEEDED`, `retryAfterSeconds`, and `correlationId`.

Live DB evidence:

- Not collected because the compose stack was not running.
- No live proof was collected for "429 audit row exists and no chat rows" beyond the controller/service tests above.

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

The codebase is automated-green, but Phase 6 browser UAT is incomplete until the local stack, seeded auth sessions, freshly indexed corpus, and reranker pre-warm prerequisites are available.
