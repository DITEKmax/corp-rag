---
phase: 05-retrieval-guards-query-api
plan: "07"
subsystem: query-orchestration
tags: [langgraph, query-api, fastapi, diagnostics, orchestration]
requires:
  - phase: 05-retrieval-guards-query-api
    provides: "05-02 through 05-06 query primitives"
provides:
  - "LangGraph query orchestration"
  - "POST /v1/query FastAPI route"
  - "Query service runtime composition"
  - "Query readiness diagnostics and mocked pipeline coverage"
affects: [phase-05-query-api, phase-06-chat, phase-07-evaluation]
tech-stack:
  added:
    - "langgraph>=0.2,<0.3"
  patterns: [typed graph state, thin graph nodes, contract adapter boundary, safe timeout response]
key-files:
  created:
    - ai-service/src/corp_rag_ai/agent/__init__.py
    - ai-service/src/corp_rag_ai/agent/state.py
    - ai-service/src/corp_rag_ai/agent/graph.py
    - ai-service/src/corp_rag_ai/service/__init__.py
    - ai-service/src/corp_rag_ai/service/query/__init__.py
    - ai-service/src/corp_rag_ai/service/query/service.py
    - ai-service/src/corp_rag_ai/service/query/factory.py
    - ai-service/tests/test_query_graph.py
    - ai-service/tests/test_query_api.py
    - ai-service/tests/test_diagnostics.py
    - ai-service/tests/test_query_pipeline.py
  modified:
    - ai-service/pyproject.toml
    - ai-service/uv.lock
    - ai-service/src/corp_rag_ai/adapters/rest/query.py
    - ai-service/src/corp_rag_ai/main.py
key-decisions:
  - "LangGraph orchestration is intentionally thin; guard, router, retriever, reranker, packer, synthesizer, and output guard remain separately testable services."
  - "The `/v1/query` adapter returns contract-shaped QueryResponse for safe success/refusal/timeout paths and Problem Details for boundary/configuration failures."
  - "Diagnostics expose query readiness from local configuration/state without live network calls."
patterns-established:
  - "QueryGraphState carries typed pipeline artifacts through LangGraph nodes."
  - "QueryRuntime composes external clients and closes Qdrant, Neo4j, and database resources from lifespan."
  - "Mocked pipeline tests verify degraded-mode metadata without live Qdrant, Neo4j, reranker, or OpenRouter."
requirements-completed: ["AGT-01", "AGT-02", "AGT-03", "RET-01", "RET-02", "RET-03", "RET-04", "SEC-01"]
duration: 17 min
completed: 2026-05-19
---

# Phase 05 Plan 07: Query Orchestration And API Summary

**LangGraph query orchestration with a contract-shaped Python `/v1/query` endpoint**

## Performance

- **Duration:** 17 min
- **Started:** 2026-05-19T21:09:05Z
- **Completed:** 2026-05-19T21:26:08Z
- **Tasks:** 3 completed
- **Files modified:** 15 tracked files

## Accomplishments

- Added `langgraph==0.2.76` under the locked `langgraph>=0.2,<0.3` dependency range.
- Added a typed `QueryGraphState` and compiled LangGraph flow covering input guard, route, retrieval, parent resolution, rerank, degradation, synthesis, output guard, and finalize nodes.
- Added query service/runtime composition for Qdrant, Neo4j, AI Postgres parent lookup, router, reranker, synthesizer, and output guard.
- Exposed `POST /v1/query` with contract request mapping, 30-second default timeout, safe timeout refusal, and Problem Details for invalid/configuration failure paths.
- Extended `/diagnostics` with query readiness fields while preserving Phase 04 diagnostics.
- Added mocked full-pipeline tests for guarded rejection, out-of-scope, factual cited answer, graph aggregation, weak/no evidence, reranker degradation, and vector dependency failure.

## Task Commits

1. **Task 1: LangGraph dependency and typed query graph state** - `4083a06` (`feat(05-07): add query graph orchestration`)
2. **Task 2: Query service and FastAPI route** - `f8031e8` (`feat(05-07): expose query API service`)
3. **Task 3: Diagnostics and full mocked pipeline coverage** - `529f266` (`test(05-07): cover query pipeline diagnostics`)

## Files Created/Modified

- `ai-service/src/corp_rag_ai/agent/` - typed graph state and compiled query graph.
- `ai-service/src/corp_rag_ai/service/query/` - graph-backed query service and runtime factory.
- `ai-service/src/corp_rag_ai/adapters/rest/query.py` - `/v1/query` route, timeout handling, and Problem Details mapping.
- `ai-service/src/corp_rag_ai/main.py` - lifespan query runtime wiring and diagnostics fields.
- `ai-service/tests/test_query_graph.py`, `test_query_api.py`, `test_query_pipeline.py`, and `test_diagnostics.py` - orchestration/API/readiness coverage.

## Decisions Made

- Comparison currently follows the hybrid path in the graph, matching the 05-07 plan acceptance rule; graph-backed comparison can be expanded later behind the same route node if needed.
- Boundary failures such as invalid internal query mapping or missing service configuration return Problem Details; safe query outcomes return `QueryResponse` with `answered=false`.
- `llm_reachable` in diagnostics is a cheap configured-state indicator, not a live OpenRouter call.

## Deviations from Plan

None - plan executed as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

- FastAPI rejected a `QueryResponse | JSONResponse` inferred response model, so the route disables automatic response-model inference and returns explicit contract/problem objects.

## Verification

- `uv run --project ai-service python -c "from importlib.metadata import version; from langgraph.graph import StateGraph, START, END; assert version('langgraph').startswith('0.2.'); assert StateGraph and START and END"` - passed.
- `uv run --project ai-service --group dev pytest ai-service/tests/test_query_graph.py` - 5 passed.
- `uv run --project ai-service --group dev pytest ai-service/tests/test_query_api.py ai-service/tests/test_query_graph.py` - 12 passed.
- `uv run --project ai-service --group dev pytest ai-service/tests/test_diagnostics.py ai-service/tests/test_query_pipeline.py ai-service/tests/test_query_api.py ai-service/tests/test_query_graph.py` - 21 passed.
- `uv run --project ai-service --group dev pytest ai-service/tests` - 202 passed, 5 skipped.
- `$env:MAVEN_CMD='C:\dev\apache-maven-3.9.15\bin\mvn.cmd'; uv run --project ai-service --group dev python scripts/verify-contracts.py` - contract verification complete.

## User Setup Required

None for mocked verification. Live `/v1/query` still requires a fresh indexed corpus plus configured Qdrant, Neo4j, AI Postgres, local embedding/reranker model cache, and OpenRouter API key.

## Next Phase Readiness

Plan 05-08 can focus on UAT evidence and live smoke helpers for the now-wired query API.

---
*Phase: 05-retrieval-guards-query-api*
*Completed: 2026-05-19*
