---
phase: 05-retrieval-guards-query-api
plan: "02"
subsystem: query-boundary
tags: [query-domain, input-guard, routing, openrouter, deepseek, strict-json-schema]
requires:
  - phase: 05-retrieval-guards-query-api
    provides: "05-01 query contracts, ADR baseline, runtime defaults, and idempotent ingestion prerequisite"
provides:
  - "Internal query, guard, retrieval metadata, citation draft, refusal, and result domain types"
  - "REST adapter mapping generated QueryRequest/QueryResponse DTOs to domain-owned types"
  - "Deterministic input guard with prompt-injection, out-of-scope, and policy refusal results"
  - "Rules-first query router with DeepSeek/OpenRouter strict JSON fallback and bounded retry"
affects: [phase-05-retrieval, phase-05-orchestration, phase-06-chat, phase-07-evaluation]
tech-stack:
  added: []
  patterns: [domain-owned query boundary, deterministic guard short-circuit, rules-first routing, strict schema LLM fallback]
key-files:
  created:
    - ai-service/src/corp_rag_ai/domain/query.py
    - ai-service/src/corp_rag_ai/domain/guard.py
    - ai-service/src/corp_rag_ai/domain/retrieval.py
    - ai-service/src/corp_rag_ai/adapters/rest/query.py
    - ai-service/src/corp_rag_ai/pipeline/guards/input_guard.py
    - ai-service/src/corp_rag_ai/pipeline/routing/query_router.py
    - ai-service/tests/test_query_domain.py
    - ai-service/tests/test_query_input_guard.py
    - ai-service/tests/test_query_router.py
  modified:
    - contracts/openapi/ai-service-v1.yaml
    - ai-service/src/corp_rag_ai/config.py
key-decisions:
  - "Generated contract DTOs remain at REST adapter boundaries; pipeline/domain modules use internal dataclasses and enums."
  - "Input guard is deterministic for MVP and returns refused QueryResult objects with empty retrieval metadata before downstream work."
  - "Rules-based router decisions have confidence 1.0 and skip OpenRouter; ambiguous questions use DeepSeek strict JSON fallback."
  - "Low-confidence, malformed, or dependency-failed classifier output becomes UNSUPPORTED so retrieval and generation can short-circuit."
patterns-established:
  - "QueryResult.refused carries guard/refusal reason plus UNSUPPORTED retrieval metadata for safe early exits."
  - "RouteClassifierResponse uses Pydantic strict schema generation with OpenRouter-unsupported keys stripped."
  - "Representative router fixtures track fallback rate; current observed fallback rate is 10%."
requirements-completed: ["AGT-01", "SEC-01", "AGT-03"]
duration: 16 min
completed: 2026-05-19
---

# Phase 05 Plan 02: Query Domain, Input Guard, And Router Summary

**Domain-owned query boundary with deterministic guard refusals and rules-first DeepSeek-backed routing**

## Performance

- **Duration:** 16 min
- **Started:** 2026-05-19T20:30:28Z
- **Completed:** 2026-05-19T20:46:18Z
- **Tasks:** 3 completed plus 1 prerequisite contract correction
- **Files modified:** 14 tracked files

## Accomplishments

- Added internal query, access filter, retrieval options, route decision, guard verdict, citation draft, retrieval metadata, refusal, and query result types.
- Added a REST adapter that maps generated AI-service contract models into internal domain types and maps domain results back to `QueryResponse`.
- Added deterministic `InputGuard` behavior for prompt injection, system-prompt extraction, policy abuse, and clear out-of-scope requests, returning `answered=false` with empty citations and no retrieval work.
- Added `QueryRouter` rules for factual, aggregation, multi-hop, comparison, and unsupported routes, with confidence `1.0` and no classifier call on rule hits.
- Added DeepSeek/OpenRouter fallback classification through strict JSON schema, bounded retry, confidence thresholding, and safe unsupported degradation.

## Task Commits

1. **Prerequisite: Align AI-service retriever contract enum** - `05c2bfe` (`fix(05-02): align ai retriever contract enum`)
2. **Task 1: Add internal query, guard, and retrieval domain types** - `2345672` (`feat(05-02): add query boundary domain models`)
3. **Task 2: Implement input guard with explicit short-circuit results** - `5d98381` (`feat(05-02): add deterministic input guard`)
4. **Task 3: Implement rules-first router and DeepSeek fallback classifier** - `d5a1c48` (`feat(05-02): add query router`)

## Files Created/Modified

- `ai-service/src/corp_rag_ai/domain/query.py` - query input, access filter, options, route decisions, refusals, and query result types.
- `ai-service/src/corp_rag_ai/domain/guard.py` - guard verdict, tier, and reason primitives.
- `ai-service/src/corp_rag_ai/domain/retrieval.py` - retrieval candidate, metadata, retriever type, and citation draft types.
- `ai-service/src/corp_rag_ai/adapters/rest/query.py` - generated contract DTO to internal domain mapping and response mapping.
- `ai-service/src/corp_rag_ai/pipeline/guards/input_guard.py` - deterministic input guard and refusal result creation.
- `ai-service/src/corp_rag_ai/pipeline/routing/query_router.py` - rules-first router and DeepSeek strict-schema classifier.
- `ai-service/src/corp_rag_ai/config.py` - query top-K defaults and caps.
- `contracts/openapi/ai-service-v1.yaml` - AI-service `RetrieverType` aligned to public `HYBRID`/`GRAPH`.
- `ai-service/tests/test_query_domain.py`, `test_query_input_guard.py`, `test_query_router.py` - focused regression coverage.

## Decisions Made

- Query pipeline code does not import generated contract modules; generated DTOs are mapped only in `adapters/rest/query.py`.
- Empty `AccessFilter.departments` is preserved as wildcard/all-departments semantics.
- Input guard uses code constants and existing corpus sanitizer prompt-injection signatures, not runtime external config.
- Router fallback rate is measured in tests; the current 10-query fixture suite invokes LLM fallback once, for a 10% fallback rate.

## Deviations from Plan

### Auto-fixed Issues

**1. Contract enum drift from 05-01**
- **Found during:** 05-02 preflight.
- **Issue:** `api-v1.yaml` exposed `RetrieverType` as `HYBRID`/`GRAPH`, while `ai-service-v1.yaml` still exposed stale `GRAPH_LOCAL`, `GRAPH_GLOBAL`, and `BM25_BASELINE` values.
- **Fix:** Aligned the AI-service OpenAPI enum and regenerated/verified generated Python models.
- **Files modified:** `contracts/openapi/ai-service-v1.yaml`
- **Verification:** `uv run --project ai-service --group dev python scripts/verify-contracts.py` with `MAVEN_CMD=C:\dev\apache-maven-3.9.15\bin\mvn.cmd` passed.
- **Committed in:** `05c2bfe`

---

**Total deviations:** 1 auto-fixed prerequisite correction.
**Impact on plan:** No scope expansion; correction was needed so 05-02 domain and adapter code matched the public query contract.

## Issues Encountered

- The first contract verification attempt could not find `mvn` on PATH. Rerunning with `MAVEN_CMD=C:\dev\apache-maven-3.9.15\bin\mvn.cmd` completed successfully.
- Router implementation initially had strict schema validation but no explicit retry. Added a bounded retry and malformed-output degradation tests before closing the plan.

## Verification

- `uv run --project ai-service --group dev python scripts/verify-contracts.py` with `MAVEN_CMD=C:\dev\apache-maven-3.9.15\bin\mvn.cmd` - passed.
- `uv run --project ai-service --group dev pytest ai-service/tests/test_query_domain.py` - 8 passed.
- `uv run --project ai-service --group dev pytest ai-service/tests/test_query_input_guard.py ai-service/tests/test_corpus_sanitizer.py` - 30 passed.
- `uv run --project ai-service --group dev pytest ai-service/tests/test_query_router.py ai-service/tests/test_entity_extractor.py` - 23 passed.
- `uv run --project ai-service --group dev pytest ai-service/tests/test_query_domain.py ai-service/tests/test_query_input_guard.py ai-service/tests/test_query_router.py ai-service/tests/test_corpus_sanitizer.py ai-service/tests/test_entity_extractor.py` - 61 passed.

## User Setup Required

None - no new external service configuration required.

## Next Phase Readiness

Plan 05-03 can consume `QueryInput.access_filter`, `RetrievalOptions`, `RouteDecision`, and `RetrievalMetadata` for access-filtered Qdrant hybrid retrieval. Live retrieval/UAT will still need a fresh indexed corpus before end-to-end query validation.

---
*Phase: 05-retrieval-guards-query-api*
*Completed: 2026-05-19*
