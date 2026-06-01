---
phase: 08-delivery-polish-demo-readiness
plan: "06"
subsystem: ai-service-indexing
tags: [entity-extraction, openrouter, deepseek, ingestion, neo4j, qdrant]

requires:
  - phase: 08-delivery-polish-demo-readiness
    provides: Java API seed reset and seed evidence workflow
provides:
  - Tolerant entity-extraction JSON parsing for fenced, prose-wrapped, and nested JSON responses
  - Bounded malformed-output retry loop with JSON-only repair instruction and per-call timeout
  - Explicit graph-skip warning detail for exhausted entity extraction failures
  - Live seed evidence showing Java 16/16, Qdrant 16/16, and Neo4j 16/16
affects: [phase-8-seed-evidence, graph-indexing, demo-corpus]

tech-stack:
  added: []
  patterns:
    - Candidate JSON extraction before strict Pydantic schema validation
    - Separate dependency retry and malformed-output retry loops

key-files:
  created:
    - .planning/phases/08-delivery-polish-demo-readiness/08-06-PLAN.md
    - .planning/phases/08-delivery-polish-demo-readiness/08-06-SUMMARY.md
  modified:
    - .planning/ROADMAP.md
    - .planning/phases/08-delivery-polish-demo-readiness/08-SEED-EVIDENCE.json
    - .planning/phases/08-delivery-polish-demo-readiness/08-SEED-EVIDENCE.md
    - ai-service/src/corp_rag_ai/pipeline/indexing/entity_extractor.py
    - ai-service/src/corp_rag_ai/pipeline/ingestion/orchestrator.py
    - ai-service/tests/test_entity_extractor.py
    - ai-service/tests/test_ingestion_orchestrator.py

key-decisions:
  - "Use three total malformed-output attempts: initial call plus two JSON-only repair attempts."
  - "Keep the entity extraction schema and graph mapping unchanged; tolerant parsing only selects a candidate JSON payload before strict validation."
  - "Preserve best-effort ingestion fallback and only add `detail` to the graph-skip warning context."

patterns-established:
  - "OpenRouter structured output wrappers are normalized before declaring a response malformed."
  - "Live seed cleanup deletes non-seed documents only through the Java document API."

requirements-completed: ["DEL-01"]

duration: 1h 35m
completed: 2026-06-01
---

# Phase 08 Plan 06: Entity Extraction Reliability Summary

**DeepSeek/OpenRouter entity extraction now recovers wrapped JSON, retries malformed output with bounds, and produced clean 16-document Neo4j seed evidence.**

## Performance

- **Duration:** 1h 35m
- **Started:** 2026-06-01T19:45:00Z
- **Completed:** 2026-06-01T21:23:16Z
- **Tasks:** 4
- **Files modified:** 8

## Accomplishments

- Added tolerant response parsing for markdown fenced JSON, prose preamble/postamble JSON, and nested JSON payload candidates before strict schema validation.
- Replaced the one-shot malformed retry flag with a bounded three-attempt malformed-output loop, minimal strict-JSON retry instruction, outcome logging, and `timeout=30.0` on completion calls.
- Kept best-effort ingestion semantics unchanged while adding `detail` to the graph-skip warning for document-id-level diagnosis.
- Rebuilt the local compose stack, deleted 11 non-seed documents through the Java document API, reran the seed reset, and updated Phase 8 seed evidence to success with Java 16/16, Qdrant 16/16, Neo4j 16/16.

## Task Commits

No commits were created in this runtime. The worktree already contained unrelated user changes in `.planning/STATE.md`, `ai-service/eval/seed_corpus.py`, and `ai-service/tests/test_eval_seed_corpus.py`; 08-06 changes are left uncommitted and isolated by file path.

## Files Created/Modified

- `.planning/phases/08-delivery-polish-demo-readiness/08-06-PLAN.md` - narrow insertion plan and execution contract.
- `.planning/ROADMAP.md` - Phase 8 plan count and Wave 1 insertion entry.
- `ai-service/src/corp_rag_ai/pipeline/indexing/entity_extractor.py` - tolerant parsing, bounded malformed retries, retry instruction, completion timeout.
- `ai-service/src/corp_rag_ai/pipeline/ingestion/orchestrator.py` - explicit `detail` in graph-skip warning extra.
- `ai-service/tests/test_entity_extractor.py` - fenced JSON, preamble JSON, retry success, retry exhaustion coverage.
- `ai-service/tests/test_ingestion_orchestrator.py` - warning detail coverage while preserving vector-success/indexed semantics.
- `.planning/phases/08-delivery-polish-demo-readiness/08-SEED-EVIDENCE.json` - live success evidence with fresh Java document ids.
- `.planning/phases/08-delivery-polish-demo-readiness/08-SEED-EVIDENCE.md` - human-readable live success evidence.

## Verification

- `uv run --project ai-service --group dev pytest ai-service/tests/test_entity_extractor.py ai-service/tests/test_ingestion_orchestrator.py` - 22 passed.
- `uv run --project ai-service --group dev pytest ai-service/tests/test_entity_extractor.py ai-service/tests/test_entity_extraction_fixture.py ai-service/tests/test_ingestion_orchestrator.py` - 23 passed.
- `docker compose --env-file infra\.env -f infra\docker-compose.yml up -d --build` - rebuilt and started the local stack with the updated `python-ai` image.
- Live cleanup/reseed:
  - Before cleanup: Java documents 27 total, seed 16, non-seed 11.
  - Deleted 11 non-seed documents through Java `/api/v1/documents/{id}`.
  - After reseed: `seed_success=True`, Java `16/16`, Qdrant `passed ok=True`, Neo4j `passed ok=True`, `non_seed_after=0`.

## Decisions Made

- Used tolerant parsing as a payload-selection step only; schema-invalid JSON still fails through the existing `EntityExtractionResponse` model.
- Kept malformed retries separate from dependency retries so transient OpenRouter/API failures and invalid model output remain independently bounded.
- Used a temporary runner in `C:\tmp` for live cleanup/reseed because heredoc stdin hit a Windows sandbox spawn issue; the temporary file was deleted after execution.

## Deviations from Plan

### Auto-fixed Issues

None - implementation stayed within the planned entity-extraction and ingestion warning scope.

---

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope expansion; live cleanup used the required Java API path.

## Issues Encountered

- The local compose stack was stopped before live verification. It was rebuilt and started with `infra/.env`, then Python AI startup was allowed to complete before reseeding.
- Direct heredoc execution for the live cleanup runner hit a Windows sandbox spawn error. A temporary `C:\tmp\gsd_08_06_live_seed.py` runner was created and deleted after successful execution.

## User Setup Required

None - live verification used the existing local compose stack and ignored `infra/.env` credentials.

## Next Phase Readiness

Seed evidence now satisfies the Phase 8 data-readiness gate for downstream final regression work. The remaining Phase 8 plans can consume `.planning/phases/08-delivery-polish-demo-readiness/08-SEED-EVIDENCE.md` with Java/Qdrant/Neo4j all at 16/16.

---
*Phase: 08-delivery-polish-demo-readiness*
*Completed: 2026-06-01*
