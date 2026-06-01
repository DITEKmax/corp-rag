---
phase: 07-evaluation-observability
plan: "01"
subsystem: infra
tags: [docker, memory, prewarm, bge-m3, reranker, diagnostics]
requires:
  - phase: 05.1-phase-5-uat-fix-wave
    provides: "live reranker memory and cold-start evidence"
provides:
  - "documented Python AI local evaluation memory contour"
  - "opt-in local query model prewarm hook"
  - "soft-fail prewarm diagnostics for embedding and reranker readiness"
affects: [phase-07-evaluation, python-ai, infra]
tech-stack:
  added: []
  patterns:
    - "Compose enables local-only expensive startup behavior while plain Settings remain test-safe"
    - "Local model prewarm failures are recorded as warnings and never block startup"
key-files:
  created:
    - ai-service/tests/test_query_runtime_prewarm.py
  modified:
    - .env.example
    - infra/.env.example
    - infra/README.md
    - infra/docker-compose.yml
    - ai-service/src/corp_rag_ai/config.py
    - ai-service/src/corp_rag_ai/main.py
    - ai-service/src/corp_rag_ai/pipeline/retrieval/reranker.py
    - ai-service/src/corp_rag_ai/service/query/factory.py
    - ai-service/src/corp_rag_ai/service/query/__init__.py
    - ai-service/tests/test_diagnostics.py
    - ai-service/tests/test_main_idempotent_dispatch.py
    - ai-service/tests/test_reranker.py
key-decisions:
  - "Use the smallest requested Phase 7 contour, 8 GiB limit with 6 GiB reservation, because Docker Desktop reports about 9.7 GiB available and Phase 5.1 measured about 4.08 GiB after bge-m3 plus reranker load."
  - "Keep prewarm disabled in plain Settings and enabled only by local Compose defaults so unit tests and non-Docker service imports do not download models."
  - "Prewarm only local bge-m3 and bge-reranker-v2-m3; it does not call OpenRouter, RAGAS, Langfuse, or any external paid service."
patterns-established:
  - "QueryRuntime keeps references to local model components that need lifecycle actions outside the query graph."
  - "Diagnostics expose prewarm readiness booleans without making readiness depend on prewarm success."
requirements-completed: ["OPS-01", "EVAL-02", "EVAL-04"]
duration: 22 min
completed: 2026-06-01
---

# Phase 07 Plan 01: Runtime Stability Summary

**Local Python AI evaluation runtime raised to an 8 GiB contour with soft-failing bge-m3 and reranker prewarm**

## Performance

- **Duration:** 22 min
- **Started:** 2026-06-01T07:41:00Z
- **Completed:** 2026-06-01T08:03:12Z
- **Tasks:** 3
- **Files modified:** 13

## Accomplishments

- Recorded the baseline: Docker is available, the Compose config renders, no corp-rag containers were running, and the previous live Phase 5.1 evidence measured `python-ai` at about 4.08 GiB after loading bge-m3 plus the reranker under the old 6 GiB limit.
- Raised the local Compose `python-ai` contour to `PYTHON_AI_MEMORY_LIMIT=8g` and `PYTHON_AI_MEMORY_RESERVATION=6g`, with both root and infra env examples documenting the override knobs.
- Added an opt-in query prewarm path that loads only local embedding/reranker components, exposes prewarm readiness in `/diagnostics`, and keeps startup alive when prewarm fails or times out.

## Task Commits

1. **Task 1: Measure and document the current cold-start contour** - recorded in this summary; live container stats were unavailable because the local stack was not running.
2. **Task 2: Raise Python AI memory contour if needed** - `54bc7b1` (`chore(07-01): raise local python ai memory contour`)
3. **Task 3: Add safe pre-warm hooks** - `e0f0754` (`feat(07-01): prewarm local query models safely`)

## Files Created/Modified

- `ai-service/tests/test_query_runtime_prewarm.py` - verifies prewarm failures become structured warnings instead of startup blockers.
- `ai-service/src/corp_rag_ai/config.py` - adds `AI_QUERY_PREWARM_ENABLED` and `AI_QUERY_PREWARM_TIMEOUT_SECONDS`.
- `ai-service/src/corp_rag_ai/service/query/factory.py` - keeps local embedder/reranker references and implements bounded prewarm orchestration.
- `ai-service/src/corp_rag_ai/pipeline/retrieval/reranker.py` - adds a prewarm method that loads and scores a local dummy pair through the existing timeout path.
- `ai-service/src/corp_rag_ai/main.py` - runs optional prewarm during lifespan and reports prewarm readiness in diagnostics.
- `infra/docker-compose.yml`, `.env.example`, `infra/.env.example`, `infra/README.md` - document and apply the Phase 7 local memory/prewarm contour.

## Runtime Baseline

- `docker info` succeeded: Docker Desktop is available with about 9.714 GiB memory.
- `docker compose -f infra/docker-compose.yml ps` showed no running project services, so live cold-start timing and `docker stats` evidence were not collected in this plan.
- Reproducible live command sequence for the next Docker run:
  - `docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build python-ai`
  - `docker stats python-ai --no-stream --format "{{.MemUsage}}"`
  - `Invoke-RestMethod http://localhost:8000/diagnostics`
  - run a first factual query, then repeat `docker stats python-ai --no-stream --format "{{.MemUsage}}"`
- Historical Phase 5.1 evidence remains the current memory baseline: 283.4 MiB before first reranker query, about 4.08 GiB after first successful reranker query, with the cold first factual query soft-degrading and the warm rerun accepted.

## Decisions Made

- Chose `8g` rather than `9g` for the local limit because it is the smallest value in the requested 8-9 GiB range and leaves more room for the rest of the local stack.
- Used Compose defaults to enable prewarm locally while leaving the Python settings default as disabled to keep tests and non-Docker imports deterministic.
- Added diagnostics booleans instead of making prewarm part of `/ready`; a prewarm failure is useful evidence, not a hard startup failure.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Live Docker evidence was partially unavailable because Docker was running but the corp-rag stack was not. The baseline records the exact commands needed to collect cold-start and memory evidence on the next live stack run.

## Verification

- PASS: `docker compose -f infra/docker-compose.yml config`
- PASS: `uv run --project ai-service --group dev pytest ai-service/tests/test_reranker.py ai-service/tests/test_diagnostics.py ai-service/tests/test_query_runtime_prewarm.py` — 11 passed, 1 skipped, 1 warning.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 07-02 can add Langfuse tracing and service metrics on top of a stable local model contour. The next live Docker run should collect the recorded cold-start/prewarm memory evidence before publishing final evaluation reports.

## Self-Check: PASSED

- Summary exists and references both Phase 7 production commits.
- Acceptance criteria are met: compose validates, prewarm failures soft-degrade, reranker degradation metadata tests still pass, and default tests do not require model downloads.
- No access-filter, citation-validation, OpenRouter, RAGAS, or Langfuse behavior was changed.

---
*Phase: 07-evaluation-observability*
*Completed: 2026-06-01*
