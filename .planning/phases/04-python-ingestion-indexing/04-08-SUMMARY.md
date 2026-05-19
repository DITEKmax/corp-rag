---
phase: 04-python-ingestion-indexing
plan: 08
subsystem: uat-closeout
tags: [uat, docker, ingestion, handoff, documentation]
status: complete
key-files:
  created:
    - .planning/phases/04-python-ingestion-indexing/04-UAT-EVIDENCE.md
    - .planning/phases/04-python-ingestion-indexing/04-08-SUMMARY.md
    - .planning/phases/04-python-ingestion-indexing/04-HANDOFF.md
  modified:
    - .planning/phases/04-python-ingestion-indexing/04-UAT.md
    - .planning/ROADMAP.md
    - .planning/STATE.md
requirements-completed: ["ING-01", "ING-02", "ING-03", "ING-04", "ING-05", "ING-06", "ING-07"]
completed: 2026-05-19
---

# Phase 04 Plan 08: UAT And Closeout Summary

Phase 4 is closed with end-to-end UAT evidence, known follow-up items, and a Phase 4 to Phase 5 handoff.

## Accomplishments

- Preserved the Phase 4 UAT runbook in `04-UAT.md` and recorded actual manual evidence in `04-UAT-EVIDENCE.md`.
- Confirmed P1 FlagEmbedding, P2 DeepSeek/OpenRouter, and P3 Docker startup preflights passed.
- Confirmed Scenarios 2 through 6 passed: fresh Markdown indexing, invalid PDF terminal failure, Neo4j-down rollback, duplicate redelivery final consistency, and delete cleanup.
- Documented Scenario 1 as skipped because the retained Phase 3 AMQP messages were lost before the Phase 4.5 pivot.
- Captured UAT-discovered fixes `d8e5190` and `9d7842d`.
- Captured Phase 5 backlog items for duplicate reprocessing, PDF/OCR support, Docling dependency audit, Python memory headroom, and Neo4j orphan entities.
- Created `04-HANDOFF.md` so Phase 5 can begin from the actual indexed-pipeline state instead of rediscovering Phase 4 behavior.

## Related Commits

| Commit | Description |
|---|---|
| `56c3e7a` | Add Phase 4 UAT runbook. |
| `146a2bd` | Add live integration smoke selectors. |
| `d9f668a` | Clarify UAT env file setup. |
| `7902c3d` | Pivot LLM provider from Gemini to DeepSeek V4 Flash through OpenRouter. |
| `f196b05` | Switch default model to `deepseek/deepseek-v4-flash:free`. |
| `d8e5190` | Add lifespan observability and `/diagnostics` for AMQP startup debugging. |
| `9d7842d` | Fix Python AMQP result-event datetime serialization to ISO 8601. |
| `dca3b26` | Add compose env defaults for Python AI AMQP consumers, Qdrant init, and Neo4j schema init. |
| this docs commit | Close Phase 4 with UAT evidence, summary, roadmap/state updates, and Phase 5 handoff. |

## UAT Result

| Area | Result |
|---|---|
| Preflight P1 | PASSED: local `BAAI/bge-m3` produced dense 1024 and sparse vectors. |
| Preflight P2 | PASSED: DeepSeek/OpenRouter returned valid entity extraction JSON. |
| Preflight P3 | PASSED: 9-container Docker stack healthy and `/diagnostics` returned all true. |
| Scenario 1 | SKIPPED: retained Phase 3 messages were no longer available. |
| Scenario 2 | PASSED: `42203559-1ac4-47f7-bbfa-6fdfd2bad4f1` indexed in about 70 seconds. |
| Scenario 3 | PASSED: `82c470e5-65ac-459a-8fd6-25689b270d5d` terminally failed at `PARSING / INVALID_FILE_FORMAT`. |
| Scenario 4 | PASSED: `8d296658-c8cc-4da9-b24d-944f8d567a83` failed at `GRAPH_UPSERT` and Qdrant rollback left 0 points. |
| Scenario 5 | PASSED with deferred bug: duplicate event `2e01c126-191a-42a3-887f-f99646973c32` left stores consistent but still re-ran expensive work. |
| Scenario 6 | PASSED: delete cleanup removed Qdrant points and Neo4j `Document` node for `42203559-1ac4-47f7-bbfa-6fdfd2bad4f1`. |

## Phase 4 Scope Delivered

- Wave 1: repo-root Python Docker build/codegen contour.
- Wave 2: AI ingestion state, AMQP foundation, manual ACK/NACK, and stage-aware failure events.
- Wave 3: normalized parsing for PDF, DOCX, HTML, Markdown, and plain text.
- Wave 4: deterministic parent/child chunking and Tier-0 sanitizer.
- Wave 5: local FlagEmbedding bge-m3 dense+sparse embeddings and Qdrant vector indexing.
- Wave 6: entity extraction and provenance-first Neo4j graph indexing.
- Wave 7: full upload/delete ingestion orchestration with terminal outcome semantics.
- Wave 8: UAT runbook, live smoke selectors, manual UAT evidence, and closeout.
- Phase 4.5/Wave 9: LLM provider pivot to DeepSeek V4 Flash through OpenRouter after the prior hosted provider was blocked by quota policy.

## Decisions And Follow-Ups

- No new `D-XX` decision numbers were introduced during closeout.
- ADR-004 remains the provider decision for DeepSeek V4 Flash through OpenRouter.
- Phase 4 UAT validates final consistency for duplicate redelivery, but not efficient short-circuiting; `PH4-UAT-DEF-01` is a Phase 5 backlog item.
- Phase 5 should seed or upload a fresh indexed document before retrieval work, because Scenario 6 deleted the TechCorp happy-path document as part of cleanup validation.

## Verification

- Manual UAT evidence is recorded in `04-UAT-EVIDENCE.md`.
- This closeout turn did not rerun the Docker UAT; it documents the user's just-completed run and verifies file/state conventions from the repository.

## Next Phase Readiness

Phase 5 can begin retrieval, guard, and query API planning against a working ingestion/indexing pipeline. Start from `04-HANDOFF.md`, then run `$gsd-discuss-phase 5` before creating the Phase 5 plan set.

## Self-Check: PASSED

- `04-UAT-EVIDENCE.md` exists and preserves exact UAT IDs/timestamps supplied by the user.
- `04-HANDOFF.md` exists and describes Phase 5 entry conditions.
- `ROADMAP.md` marks Phase 4 complete and Phase 5 next.
- `STATE.md` moves current work to Phase 5 readiness.

---
*Phase: 04-python-ingestion-indexing*
*Completed: 2026-05-19*
