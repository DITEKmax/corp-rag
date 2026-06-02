---
phase: 08-delivery-polish-demo-readiness
plan: "04"
subsystem: demo-assets
tags: [demo, docs, architecture, video-checklist, waiver]

requires:
  - phase: 08-delivery-polish-demo-readiness
    plan: "03"
    provides: Final regression metrics and chat/citation proof
  - phase: 08-delivery-polish-demo-readiness
    plan: "05"
    provides: Known limitations and Phase 8 waiver wording
provides:
  - Demo-ready top-level README quickstart and evidence links
  - Architecture diagram reflecting the real Java/Python service boundary
  - Russian-corpus-first demo script with citations, Langfuse, injection/refusal, and multi-hop limitation scenes
  - Ready-to-record video checklist and explicit waiver status
affects: [demo-readiness, documentation, phase-8-delivery]

tech-stack:
  added: []
  patterns:
    - Quality-vs-coverage demo framing
    - Ready-to-record waiver for human presentation artifacts

key-files:
  created:
    - docs/demo/README.md
    - docs/demo/demo-script.md
    - docs/demo/video-checklist.md
    - .planning/phases/08-delivery-polish-demo-readiness/08-04-SUMMARY.md
  modified:
    - README.md
    - docs/ARCHITECTURE.md

key-decisions:
  - "Demo narrative is quality-vs-coverage: high grounded-answer quality, limited coverage, and safe refusal instead of fabrication."
  - "Architecture documentation keeps frontend -> Java only; Java owns auth/documents/chat/audit, while Python owns ingestion/retrieval/graph/guards/synthesis/eval."
  - "No video binary is committed; short-video capture is left as a ready-to-record human-action waiver with checklist."

patterns-established:
  - "Demo evidence index links compose, seed, final regression, RAGAS, injection, and known-limit artifacts."
  - "Demo scripts must use committed final metrics rather than regenerated or invented numbers."

requirements-completed: ["DEL-01"]

duration: 6 min
completed: 2026-06-02
---

# Phase 08 Plan 04: Demo Assets Summary

**Review-ready demo assets now present the MVP honestly as grounded where it answers and conservative where coverage is limited.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-02T03:02:08+03:00
- **Completed:** 2026-06-02T03:08:06+03:00
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Reworked `README.md` into a demo-ready local MVP entrypoint with compose startup, memory requirements, env setup, seed reset, health checks, final regression command, demo path, troubleshooting, and known limitations.
- Updated `docs/ARCHITECTURE.md` with the actual Phase 8 service boundary: frontend calls Java only; Java owns auth/documents/chat/audit/API; Python owns ingestion/retrieval/graph/guards/synthesis/eval; Qdrant/Neo4j/Langfuse support the stack.
- Created `docs/demo/README.md`, `docs/demo/demo-script.md`, and `docs/demo/video-checklist.md`.
- Built the demo narrative around the final metrics supplied by Phase 8 evidence: `faithfulness=0.991`, `answer_relevancy=0.865`, `context_precision=1.0`, `context_recall=1.0`, `answered=16/30 answerable`, `outcome_accuracy=0.575`, `citation_doc_recall=0.533`.
- Recorded the video status as ready-to-record waiver with exact next recording step and review criteria.

## Task Commits

1. **Task 1: Update README and architecture diagram** - `9e7704c` (`docs(08-04): update demo quickstart and architecture`)
2. **Task 2: Create demo asset index and script** - `5184e8a` (`docs(08-04): add demo assets and video checklist`)
3. **Task 3: Review or record short demo video** - covered by `5184e8a`; no video binary committed, ready-to-record waiver captured in `docs/demo/video-checklist.md`.

## Files Created/Modified

- `README.md` - top-level demo-ready quickstart, evidence links, final regression command, troubleshooting, and known limitations.
- `docs/ARCHITECTURE.md` - updated component diagram and ownership table for the real frontend/Java/Python boundary.
- `docs/demo/README.md` - demo asset index and evidence map.
- `docs/demo/demo-script.md` - concrete Russian-corpus-first demo script with citation, Langfuse, latency, injection/refusal, and multi-hop safe refusal scenes.
- `docs/demo/video-checklist.md` - recording checklist and ready-to-record waiver.
- `.planning/phases/08-delivery-polish-demo-readiness/08-04-SUMMARY.md` - plan close-out record.

## Verification

- `python -c "from pathlib import Path; t=Path('README.md').read_text(encoding='utf-8'); required=['docker compose','seed','final regression','docs/demo','known limitations']; missing=[x for x in required if x.lower() not in t.lower()]; assert not missing, missing"` - passed.
- `python -c "from pathlib import Path; t=Path('docs/demo/demo-script.md').read_text(encoding='utf-8'); required=['citation','Langfuse','latency','injection','multi-hop','safe refusal']; missing=[x for x in required if x.lower() not in t.lower()]; assert not missing, missing"` - passed.
- `git diff --check -- README.md docs\ARCHITECTURE.md docs\demo` - passed before task commits; only CRLF normalization warnings were reported.
- `git diff --cached --check` - passed for the demo asset commit.
- `rg -n "08-COMPOSE|08-SEED|08-FINAL|ragas_ru|injection_ru|08-KNOWN|ready-to-record|Review criteria" docs\demo` - passed.

## Decisions Made

- Used the final Phase 8 metrics exactly as provided and as recorded in evidence; no eval was rerun.
- Kept generated screenshots/video files out of the repository because none existed and the plan allowed a ready-to-record waiver.
- Described multi-hop waiver and router false-`MULTI_HOP` as measured limitations that lead to safe refusal, with links to `08-KNOWN-LIMITATIONS.md`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Two sandboxed Python assertion invocations hit transient `windows sandbox: spawn setup refresh`; both checks were rerun successfully with approved escalation.
- The first README assertion found the literal phrase `known limitations` missing even though the evidence link existed. README was corrected before the Task 1 commit.

## User Setup Required

Short-video capture remains a human presentation action. The waiver is explicit:

- No video file is committed in this plan.
- `docs/demo/video-checklist.md` is ready to record a 3-5 minute screen capture.
- If a video is later intentionally committed, add the reviewed artifact path to the checklist.

## Next Phase Readiness

Phase 8 demo assets are ready for review. Remaining close-out can use this summary and the existing Phase 8 evidence without rerunning eval or changing corpus/model settings.

---
*Phase: 08-delivery-polish-demo-readiness*
*Completed: 2026-06-02*
