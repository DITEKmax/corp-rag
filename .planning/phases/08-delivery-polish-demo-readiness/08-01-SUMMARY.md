---
phase: 08-delivery-polish-demo-readiness
plan: "01"
subsystem: seed-tooling
tags: [seed-corpus, java-api, qdrant, neo4j, evidence]

requires:
  - phase: 07.1-fix-russian-router-and-graph-retrieval-quality-for-ragas-bas
    provides: Repaired graph corpus baseline and deferred multi-hop retrieval waiver
provides:
  - Idempotent Java API demo corpus reset for the 16-document Russian corpus
  - Seed evidence with Java document ids, Qdrant cleanliness, and Neo4j graph completeness
  - Windows PowerShell wrapper for running the seed CLI without secrets
affects: [phase-8-regression, demo-readiness, final-eval]

tech-stack:
  added: []
  patterns:
    - Java document lifecycle as the only seed mutation path
    - Evidence files under the Phase 8 planning directory

key-files:
  created:
    - .planning/phases/08-delivery-polish-demo-readiness/08-01-SUMMARY.md
  modified:
    - ai-service/eval/seed_corpus.py
    - ai-service/tests/test_eval_seed_corpus.py
    - scripts/seed-demo-corpus.ps1
    - .planning/phases/08-delivery-polish-demo-readiness/08-SEED-EVIDENCE.json
    - .planning/phases/08-delivery-polish-demo-readiness/08-SEED-EVIDENCE.md

key-decisions:
  - "Seed reset uses Java login/list/delete/upload APIs and never manually clears Docker volumes or backing stores."
  - "Seed identity is based on stable corpus version and manifest doc ids written to Java document description metadata."
  - "Graph completeness for the final seed evidence depends on the 08-06 entity-extraction structured-output reliability fix."

patterns-established:
  - "Seed evidence is generated as both JSON and Markdown for reviewable demo-readiness proof."
  - "Windows wrapper delegates to the Python seed CLI and does not contain credentials or cleanup logic."

requirements-completed: ["DEL-01"]

duration: carried forward from 08-01 execution
completed: 2026-06-02
---

# Phase 08 Plan 01: Demo Corpus Seed Summary

**Idempotent Java API seed reset now loads the 16-document Russian demo corpus and records clean Java/Qdrant/Neo4j evidence.**

## Performance

- **Duration:** carried forward from prior 08-01 execution
- **Started:** 2026-06-01
- **Completed:** 2026-06-02
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Built `ai-service/eval/seed_corpus.py` as an opt-in reset CLI that authenticates to Java, deletes previous seed documents through Java DELETE, uploads all 16 manifest documents, polls terminal indexing, and writes evidence.
- Added focused seed-tool tests covering seed markers, matching, multipart metadata, polling, failure surfacing, browser-origin unsafe headers, and evidence formatting.
- Preserved user-facing manifest titles and wrote stable seed markers without committing credentials.
- Kept reset behavior within the product lifecycle: no direct Qdrant, Neo4j, MinIO, Postgres, RabbitMQ, or Docker volume cleanup.
- Final evidence now shows `success=true`, Java `16/16`, Qdrant `passed` with 16 document ids and 16 points, Neo4j `passed` with `neo4j_count=16`, and `non_seed=0`.

## Task Commits

Plan implementation was completed before this close-out. This summary commit closes the missing plan metadata and keeps the PowerShell wrapper aligned with a root-level `uv run --project ai-service` invocation.

## Files Created/Modified

- `ai-service/eval/seed_corpus.py` - Java API reset, upload, polling, store checks, and evidence writer.
- `ai-service/tests/test_eval_seed_corpus.py` - unit coverage for seed markers, Java API behavior, polling, and evidence formatting.
- `scripts/seed-demo-corpus.ps1` - thin Windows wrapper around `uv run --project ai-service python ai-service/eval/seed_corpus.py`.
- `.planning/phases/08-delivery-polish-demo-readiness/08-SEED-EVIDENCE.json` - final machine-readable seed evidence.
- `.planning/phases/08-delivery-polish-demo-readiness/08-SEED-EVIDENCE.md` - final human-readable seed evidence.

## Decisions Made

- Existing seed documents are deleted only through Java document APIs so the ordinary delete event path cleans Qdrant and Neo4j.
- The seed CLI writes evidence under the Phase 8 directory by default to support final regression and demo review.
- 08-06 fixed F-04 structured-output instability so all 16 seeded documents now reach Neo4j; 08-01 evidence records the final graph-complete outcome.

## Deviations from Plan

None - this close-out only creates the missing summary and keeps the wrapper thin.

---

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change; final seed evidence reflects the completed 08-01 + 08-06 state.

## Issues Encountered

- Initial live seed evidence had Neo4j `9/16` because DeepSeek/OpenRouter sometimes returned wrapped or malformed structured output. 08-06 hardened entity extraction parsing/retries; the final seed evidence is now Java/Qdrant/Neo4j `16/16`.

## User Setup Required

For live reruns, use ignored `infra/.env` or explicit environment variables for Java admin credentials and OpenRouter. No secrets are committed in the wrapper or evidence.

## Next Phase Readiness

Phase 8 Wave 1 can proceed to compose/runbook readiness and polish work with a clean seeded corpus: Java `16/16`, Qdrant `16/16`, Neo4j `16/16`, and `non_seed=0`.

---
*Phase: 08-delivery-polish-demo-readiness*
*Completed: 2026-06-02*
