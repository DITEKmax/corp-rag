---
phase: 05-retrieval-guards-query-api
plan: "08"
subsystem: uat-handoff
tags: [uat, live-smoke, documentation, phase-closeout, handoff]
requires:
  - phase: 05-retrieval-guards-query-api
    provides: "completed Python query API and mocked verification"
provides:
  - "Phase 05 UAT checklist"
  - "Fresh corpus setup guide"
  - "Optional live query smoke tests"
  - "Phase 06 handoff documentation"
affects: [phase-05-query-api, phase-06-chat, phase-07-evaluation]
tech-stack:
  added: []
  patterns: [self-skipping live smokes, fresh-corpus UAT, phase boundary handoff, non-destructive evidence collection]
key-files:
  created:
    - ai-service/tests/test_query_live_smokes.py
    - .planning/phases/05-retrieval-guards-query-api/05-UAT.md
    - .planning/phases/05-retrieval-guards-query-api/05-USER-SETUP.md
  modified:
    - infra/README.md
    - ai-service/README.md
    - docs/ARCHITECTURE.md
    - .planning/ROADMAP.md
    - .planning/STATE.md
key-decisions:
  - "Live query smokes are optional integration tests and skip unless live flags, credentials, a running service, and fresh corpus readiness are explicit."
  - "Phase 05 live UAT requires fresh corpus setup because the Phase 04 happy-path document was deleted."
  - "Phase 06 owns Java chat persistence, query audit rows, browser chat UI, and source-viewer behavior."
patterns-established:
  - "Use AI_QUERY_LIVE_CORPUS_READY to prevent accidental false-negative retrieval smokes."
  - "Record reranker memory under the 6 GiB python-ai contour and alarm above 5.5 GiB."
  - "Treat vectorDegraded UAT evidence as the vector_retrieval_unavailable degradation warning unless a future explicit field is added."
requirements-completed: ["RET-01", "RET-02", "RET-03", "RET-04", "AGT-01", "AGT-02", "AGT-03", "SEC-01"]
duration: 6 min
completed: 2026-05-19
---

# Phase 05 Plan 08: UAT, Live Smokes, And Handoff Summary

**Phase 05 closeout docs and optional live query verification path**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-19T21:26:08Z
- **Completed:** 2026-05-19T21:32:10Z
- **Tasks:** 3 completed
- **Files modified:** 8 tracked files before summary

## Accomplishments

- Added optional live query smoke tests for guard rejection, out-of-scope refusal, factual cited answer, graph answer, no-evidence refusal, and Qdrant-off graph degradation.
- Added `05-USER-SETUP.md` with OpenRouter, stack startup, fresh corpus upload, corpus verification, and live smoke setup.
- Added `05-UAT.md` with numbered Phase 05 UAT scenarios, exact request payload patterns, expected response fields, store observations, evidence log, and reranker memory check.
- Updated infra and AI-service READMEs with query live smoke and Phase 5 runtime notes.
- Updated architecture docs with the implemented Python query flow, citation metadata shape, diagnostics fields, and Phase 6 boundary.
- Marked Phase 05 complete in roadmap/state and positioned Phase 06 as next.

## Task Commits

1. **Task 1: Automated verification and optional live smokes** - `bcc5b76` (`test(05-08): add query live smokes`)
2. **Task 2: Fresh corpus setup and UAT checklist** - `25c4c7d` (`docs(05-08): add query UAT setup`)
3. **Task 3: Final query behavior and Phase 6 handoff** - `f1ce1e6` (`docs(05-08): document query handoff`)

## Files Created/Modified

- `ai-service/tests/test_query_live_smokes.py` - optional self-skipping live query integration smokes.
- `.planning/phases/05-retrieval-guards-query-api/05-UAT.md` - manual UAT checklist and evidence log.
- `.planning/phases/05-retrieval-guards-query-api/05-USER-SETUP.md` - setup guide for fresh corpus and live query smokes.
- `infra/README.md` and `ai-service/README.md` - query UAT and live smoke instructions.
- `docs/ARCHITECTURE.md` - implemented Phase 5 query flow and Phase 6 boundary.
- `.planning/ROADMAP.md` and `.planning/STATE.md` - Phase 05 completion and Phase 06 next state.

## Decisions Made

- Live query tests require `AI_QUERY_LIVE_CORPUS_READY=true` so a missing corpus does not look like a query regression.
- The UAT runbook records live Phase 05 UAT as pending until credentials, Docker stack, and fresh corpus are available; it does not falsely claim live evidence.
- The Phase 6 handoff explicitly says Python returns the answer/citation/guard/retrieval metadata, while Java/frontend persistence and display remain Phase 6.

## Deviations from Plan

None - plan executed as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

- Live UAT was not executed in this automated pass because it requires user-provided OpenRouter credentials, a running Docker stack, and a fresh indexed corpus.

## Verification

- `uv run --project ai-service --group dev pytest ai-service/tests/test_query_live_smokes.py` - 6 skipped by default.
- `uv run --project ai-service --group dev pytest ai-service/tests/test_query_pipeline.py ai-service/tests/test_query_api.py ai-service/tests/test_query_graph.py` - 20 passed.
- `uv run --project ai-service --group dev pytest ai-service/tests` - 202 passed, 11 skipped.
- `$env:MAVEN_CMD='C:\dev\apache-maven-3.9.15\bin\mvn.cmd'; uv run --project ai-service --group dev python scripts/verify-contracts.py` - contract verification complete.
- `rg -n "gemini|ch-NNN|ch-001|streaming answers" docs ai-service/README.md .planning/phases/05-retrieval-guards-query-api/05-UAT.md` - no matches.

## User Setup Required

For live UAT only:

- Set `OPENROUTER_API_KEY`.
- Start Docker Compose.
- Upload and verify a fresh indexed corpus using `05-USER-SETUP.md`.
- Run `05-UAT.md` scenarios and record evidence.

## Next Phase Readiness

Phase 06 can now plan Java chat persistence, query audit rows, browser chat UI, and citation/source-viewer workflows against the Python `QueryResponse` contract.

---
*Phase: 05-retrieval-guards-query-api*
*Completed: 2026-05-19*
