---
phase: 07-evaluation-observability
plan: "02"
subsystem: observability
tags: [langfuse, tracing, diagnostics, metrics, query-graph]
requires:
  - phase: 07-evaluation-observability
    provides: "07-01 local runtime memory contour and prewarm settings"
provides:
  - "Langfuse v2 SDK compatibility pin"
  - "root query traces with child query graph spans"
  - "synthesis generation observations"
  - "process-local query diagnostics counters"
affects: [phase-07-evaluation, python-ai, diagnostics]
tech-stack:
  added:
    - "langfuse~=2.0"
  patterns:
    - "Langfuse helper no-ops when placeholders or local health checks fail"
    - "Query graph nodes are wrapped centrally so span names match LangGraph node names"
key-files:
  created:
    - ai-service/src/corp_rag_ai/observability/__init__.py
    - ai-service/src/corp_rag_ai/observability/langfuse.py
    - ai-service/src/corp_rag_ai/observability/metrics.py
  modified:
    - ai-service/pyproject.toml
    - ai-service/uv.lock
    - ai-service/src/corp_rag_ai/adapters/rest/query.py
    - ai-service/src/corp_rag_ai/agent/graph.py
    - ai-service/src/corp_rag_ai/main.py
    - ai-service/src/corp_rag_ai/pipeline/generation/synthesizer.py
    - ai-service/src/corp_rag_ai/service/query/factory.py
    - ai-service/tests/test_diagnostics.py
    - ai-service/tests/test_query_api.py
    - ai-service/README.md
    - infra/README.md
key-decisions:
  - "Pin the Python client to langfuse 2.60.10 through langfuse~=2.0 and keep the compose container on langfuse/langfuse:2.95.11."
  - "Disable tracing automatically for placeholder keys or unreachable local Langfuse health so query behavior is unaffected."
  - "Expose process-local counters through /diagnostics rather than adding Prometheus, Grafana, or frontend observability UI."
patterns-established:
  - "Root query tracing is owned by the REST adapter; graph span tracing is owned by QueryGraphNodes."
  - "Synthesis generation observations are nested by context under the synthesize span."
requirements-completed: ["OPS-01", "EVAL-02"]
duration: 12 min
completed: 2026-06-01
---

# Phase 07 Plan 02: Observability Summary

**Langfuse v2 tracing and lightweight query diagnostics for the Python RAG pipeline**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-01T08:03:12Z
- **Completed:** 2026-06-01T08:14:57Z
- **Tasks:** 4
- **Files modified:** 14

## Accomplishments

- Added `langfuse~=2.0` and locked `langfuse==2.60.10`, while leaving the existing `langfuse/langfuse:2.95.11` container unchanged.
- Added a no-op-safe Langfuse helper that creates root query traces, graph node spans, and synthesis generation observations only when real local Langfuse keys are configured and the local health endpoint is reachable.
- Extended `/diagnostics` with process-local query counters, prewarm readiness, and Langfuse configured/reachable booleans without adding a metrics stack or frontend observability screen.

## Task Commits

1. **Task 1: Resolve Langfuse SDK compatibility** - `6c12d67` (`chore(07-02): pin langfuse v2 sdk`)
2. **Tasks 2-4: Root trace, graph/generation spans, diagnostics counters** - `abd6294` (`feat(07-02): trace query graph and diagnostics`)

## Files Created/Modified

- `ai-service/src/corp_rag_ai/observability/langfuse.py` - Langfuse v2 facade, placeholder/unreachable no-op behavior, root traces, spans, and generations.
- `ai-service/src/corp_rag_ai/observability/metrics.py` - thread-safe process-local query metrics snapshot.
- `ai-service/src/corp_rag_ai/adapters/rest/query.py` - wraps `/v1/query` in a root trace and records query metrics after safe results.
- `ai-service/src/corp_rag_ai/agent/graph.py` - wraps real graph nodes with same-name spans and safe metadata.
- `ai-service/src/corp_rag_ai/pipeline/generation/synthesizer.py` - traces OpenRouter synthesis as a generation under `synthesize`.
- `ai-service/src/corp_rag_ai/main.py` - initializes observability/metrics and extends diagnostics.
- `ai-service/README.md`, `infra/README.md` - document Langfuse v2, diagnostics counters, and no-op behavior.

## Decisions Made

- Used Langfuse SDK v2 (`2.60.10`) because the project’s local container is still Langfuse `2.95.11`; no v3 platform upgrade was introduced.
- Treated placeholder keys as disabled tracing, so the default Compose environment remains safe and does not attempt to export traces with fake credentials.
- Kept diagnostics in-process and read-only. These counters are demo/runtime evidence, not durable analytics.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Live Docker trace evidence was not collected because `docker compose -f infra/docker-compose.yml ps` showed no running project services. This is not an SDK compatibility blocker; the summary records the command gap, and the code path is covered by no-op/fake-client tests. Live trace validation remains part of Phase 7 UAT once the stack is running with real local Langfuse keys.

## Verification

- PASS: `uv lock --project ai-service`
- PASS: `docker compose -f infra/docker-compose.yml config`
- PASS: `uv run --project ai-service --group dev pytest ai-service/tests/test_query_api.py ai-service/tests/test_query_graph.py ai-service/tests/test_query_pipeline.py ai-service/tests/test_diagnostics.py` — 29 passed, 1 warning.

## User Setup Required

Docker trace verification requires real local Langfuse project keys in ignored `infra/.env`; placeholder keys intentionally no-op. No real Langfuse or OpenRouter secrets were committed.

## Next Phase Readiness

Plan 07-03 can build the eval corpus and harness foundation with trace/counter hooks already available. Final Phase 7 evidence should include a live Langfuse screenshot or exported trace ids after the stack is started with real local keys.

## Self-Check: PASSED

- Summary exists and references all 07-02 production commits.
- The SDK/container compatibility choice is pinned and documented.
- Required graph node span names are exactly the LangGraph node names.
- The generation observation is created inside the `synthesize` span context.
- Citation validation and refusal behavior remain covered by existing query graph/pipeline tests.

---
*Phase: 07-evaluation-observability*
*Completed: 2026-06-01*
