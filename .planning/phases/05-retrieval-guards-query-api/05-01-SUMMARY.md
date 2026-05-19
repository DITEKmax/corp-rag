---
phase: 05-retrieval-guards-query-api
plan: "01"
subsystem: contracts-runtime
tags: [openapi, codegen, adr, idempotency, docker-compose, query-runtime]
requires:
  - phase: 04-python-ingestion-indexing
    provides: "Phase 04 ingestion pipeline, Qdrant/Neo4j indexing, sanitizer, and UAT carry-forward defects"
provides:
  - "UUID child-chunk citation contracts and retrieval metadata for Python and Java-facing APIs"
  - "Python codegen support for nullable allOf model properties"
  - "ADR-005 through ADR-008 for query routing, degraded mode, citations, and guards"
  - "Duplicate ingestion-event dispatcher wiring before business service construction"
  - "Phase 05 query runtime defaults and raised python-ai memory contour"
affects: [phase-05-query, phase-06-frontend-citations, phase-07-evaluation]
tech-stack:
  added: []
  patterns: [contract-first query DTOs, rules-first query routing ADR, fail-loud degraded mode, startup idempotent dispatch]
key-files:
  created:
    - docs/decisions/ADR-005-query-routing-model.md
    - docs/decisions/ADR-006-degraded-mode-policy.md
    - docs/decisions/ADR-007-citation-contract-and-refusal-rules.md
    - docs/decisions/ADR-008-guard-architecture.md
    - ai-service/tests/test_main_idempotent_dispatch.py
  modified:
    - contracts/openapi/ai-service-v1.yaml
    - contracts/openapi/api-v1.yaml
    - scripts/generate_python_contracts.py
    - ai-service/src/corp_rag_ai/main.py
    - ai-service/src/corp_rag_ai/config.py
    - infra/docker-compose.yml
    - .env.example
    - infra/.env.example
    - ai-service/README.md
    - infra/README.md
    - docs/ARCHITECTURE.md
    - docs/decisions/README.md
key-decisions:
  - "Generated contract outputs remain ignored build artifacts; verification regenerates them from root contracts."
  - "Duplicate upload/delete events now short-circuit through IdempotentEventDispatcher before DocumentIngestionService construction."
  - "Phase 05 query runtime defaults are explicit in settings, env examples, and Compose."
patterns-established:
  - "Property-level nullable allOf schemas resolve to referenced Pydantic model types."
  - "Main AMQP handlers share idempotent dispatch helpers before building expensive ingestion services."
requirements-completed: ["RET-01", "RET-02", "RET-03", "RET-04", "AGT-01", "AGT-02", "AGT-03", "SEC-01"]
duration: 27 min
completed: 2026-05-19
---

# Phase 05 Plan 01: Contract, ADR, Runtime, And Idempotency Summary

**Query contracts, ADR guardrails, duplicate ingestion dispatch, and local runtime defaults prepared for Phase 05 retrieval work**

## Performance

- **Duration:** 27 min
- **Started:** 2026-05-19T20:02:00Z
- **Completed:** 2026-05-19T20:29:08Z
- **Tasks:** 4 completed
- **Files modified:** 18 tracked files

## Accomplishments

- Updated Python and Java-facing OpenAPI contracts so citation `chunkId` values are UUID child chunk IDs and retrieval metadata exposes attempted/used retrievers, warnings, model ID, route, chunk counts, and reranker usage.
- Fixed Python contract generation so nullable `allOf` fields such as `guardVerdict` generate as `GuardVerdict | None`.
- Added ADR-005 through ADR-008 and refreshed architecture text for rules-first routing, fail-loud degraded mode, child-level citations, and downrank-not-exclude guard behavior.
- Wrapped upload/delete AMQP handlers with `IdempotentEventDispatcher` before ingestion service construction and added a regression for duplicate upload redelivery.
- Added Phase 05 query defaults to settings, env examples, docs, and Compose, with `python-ai` raised to 6 GiB limit / 4 GiB reservation.

## Task Commits

1. **Task 1a: Update query OpenAPI contracts** - `1815f38` (`feat(05-01): align query citation contracts`)
2. **Task 1b: Fix Python nullable/allOf codegen and regenerate models** - `8de7564` (`fix(05-01): preserve allOf contract model types`)
3. **Task 2: Add Phase 05 ADRs** - `757b27d` (`docs(05-01): add query ADR baseline`)
4. **Task 3: Close Phase 04 duplicate-idempotency carry-forward and query runtime defaults** - `5127074` (`fix(05-01): guard duplicate ingestion dispatch`)

## Files Created/Modified

- `docs/decisions/ADR-005-query-routing-model.md` - rules-first router and DeepSeek fallback decision.
- `docs/decisions/ADR-006-degraded-mode-policy.md` - explicit degraded-mode matrix.
- `docs/decisions/ADR-007-citation-contract-and-refusal-rules.md` - child-level UUID citation and refusal policy.
- `docs/decisions/ADR-008-guard-architecture.md` - input/output guard architecture.
- `contracts/openapi/ai-service-v1.yaml` and `contracts/openapi/api-v1.yaml` - query/citation/retrieval metadata contract alignment.
- `scripts/generate_python_contracts.py` - property-level `allOf` type resolution.
- `ai-service/src/corp_rag_ai/main.py` - idempotent upload/delete dispatch helpers.
- `ai-service/src/corp_rag_ai/config.py` - query runtime settings.
- `ai-service/tests/test_main_idempotent_dispatch.py` - duplicate upload short-circuit and settings defaults regression.
- `infra/docker-compose.yml`, `.env.example`, `infra/.env.example`, `ai-service/README.md`, `infra/README.md` - query defaults and memory contour.
- `docs/ARCHITECTURE.md`, `docs/decisions/README.md`, `docs/decisions/ADR-004-llm-provider-deepseek-openrouter.md` - ADR index and stale reference cleanup.

## Decisions Made

- Generated Python contract outputs were regenerated and verified but not committed because the repo treats them as ignored build artifacts.
- `IdempotentEventDispatcher` now sits in `main.py` before service construction, while `DocumentIngestionService` keeps its own terminal-event idempotency checks for direct service tests.
- Query runtime configuration starts with conservative MVP defaults: 30 second timeout, 0.65 router threshold, 4000 token context cap, 0.4 weak-evidence threshold, and 0.5 flagged-chunk multiplier.

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

- Root `python` was not available in this Windows environment. Verification used the project-managed `uv run --project ai-service --group dev python` environment instead.

## Verification

- `uv run --project ai-service --group dev python scripts/verify-contracts.py` with `MAVEN_CMD=C:\dev\apache-maven-3.9.15\bin\mvn.cmd` - passed.
- Generated `QueryResponse.guardVerdict` and `ProblemDetail.guardVerdict` annotations are `GuardVerdict | None` - passed.
- `uv run --project ai-service --group dev pytest ai-service/tests/test_amqp_consumer.py ai-service/tests/test_ingestion_orchestrator.py ai-service/tests/test_main_idempotent_dispatch.py` - 16 passed.
- `docker compose -f infra/docker-compose.yml config --quiet` - passed.

## User Setup Required

None - no new external service configuration required.

## Next Phase Readiness

Plan 05-02 can build query domain models, input guard, and routing against current generated Python contract models and the accepted ADR baseline. The Phase 04 duplicate-redelivery carry-forward is closed by regression coverage before retrieval load increases.

---
*Phase: 05-retrieval-guards-query-api*
*Completed: 2026-05-19*
