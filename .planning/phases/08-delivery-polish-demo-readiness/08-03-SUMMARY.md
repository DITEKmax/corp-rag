---
phase: 08-delivery-polish-demo-readiness
plan: "03"
subsystem: final-regression
tags: [final-regression, ragas, seeded-corpus, demo-readiness, evidence]

requires:
  - phase: 08-delivery-polish-demo-readiness
    plan: "01"
    provides: Clean 16-document seed corpus evidence
  - phase: 08-delivery-polish-demo-readiness
    plan: "02"
    provides: Healthy 9/9 compose evidence
provides:
  - Final Phase 8 regression evidence on the seeded 16-document corpus
  - Java chat citation proof with `ANSWERED` status
  - Production-path RAGAS report with known limitations documented
affects: [phase-8-regression, demo-readiness, ragas-evidence]

tech-stack:
  added: []
  patterns:
    - RAGAS production eval remains report-only evidence, not a CI gate
    - Reranker degradation is tracked as an explicit before/after regression signal

key-files:
  created:
    - .planning/phases/08-delivery-polish-demo-readiness/08-FINAL-REGRESSION.md
    - .planning/phases/08-delivery-polish-demo-readiness/08-FINAL-REGRESSION.json
    - .planning/phases/08-delivery-polish-demo-readiness/08-03-SUMMARY.md
  modified:
    - ai-service/eval/reports/ragas_ru.md
    - ai-service/eval/reports/ragas_ru.json
    - ai-service/eval/reports/ragas_ru.csv
    - .planning/phases/08-delivery-polish-demo-readiness/08-KNOWN-LIMITATIONS.md

key-decisions:
  - "The final regression evidence is accepted as a checkpoint, not as a hard CI gate."
  - "Outcome coverage misses are documented honestly; they do not block Phase 8 because the observed behavior is safe refusal rather than fabrication."
  - "Router false-MULTI_HOP and judge structured-output stability remain backlog/future work, not Phase 8 fixes."

requirements-completed: ["DEL-01"]

duration: checkpointed final run
completed: 2026-06-02
---

# Phase 08 Plan 03: Final Regression Summary

**Final regression evidence was captured on the clean 16-document seeded corpus and committed as report-only Phase 8 checkpoint evidence.**

## Performance

- **Duration:** checkpointed final run
- **Completed:** 2026-06-02
- **Evidence commit:** `aeae894 test(08-03): final regression evidence on seeded 16-doc corpus`
- **Files committed as evidence:** 5

## Accomplishments

- Captured final compose readiness, seed/index counts, Java chat proof, diagnostics before/after, and production-path RAGAS output.
- Verified the seeded corpus remained clean: Java `16/16`, Qdrant `16/16`, Neo4j `16/16`, `non_seed=0`.
- Proved the Java chat path with `ANSWERED` status and valid document-title citations.
- Recorded `reranker_degraded_count` before/after as `0/0`.
- Committed generated final evidence and `ragas_ru.*` reports after user review.

## Final Metrics

- `faithfulness=0.991`
- `answer_relevancy=0.865`
- `context_precision=1.0`
- `context_recall=1.0`
- `citation_doc_recall=0.533` against threshold `0.7` - not passed
- `outcome_accuracy=0.575` against threshold `0.8` - not passed
- `answered_count=16`
- `route_mix={"AGGREGATION":4,"COMPARISON":4,"FACTUAL":14,"MULTI_HOP":10,"UNSUPPORTED":8}`

## Limitations

The failed `outcome_accuracy` and `citation_doc_recall` thresholds are documented and accepted as Phase 8 report-only evidence rather than hidden or treated as passing.

Known causes:
- Multi-hop graph retrieval remains waived for Phase 8 and safely returns `refused_no_evidence` instead of unsupported answers.
- Router false-`MULTI_HOP` on `deepseek/deepseek-v4-flash` can classify answerable factual and aggregation questions into the graph path, which then safely refuses.
- `citation_doc_recall` is partly capped by those safe refusals because refused rows do not produce citations.
- The final RAGAS evidence includes 3 DeepSeek judge `OUTPUT_PARSING_FAILURE` cases; this structured-output instability is bounded by `--ragas-max-retries 1` and recorded.

See `.planning/phases/08-delivery-polish-demo-readiness/08-KNOWN-LIMITATIONS.md` for the full quality-vs-coverage framing.

## Verification

- Final regression run used production `/v1/query`, `top_k=10`, RAGAS concurrency `1`, `--ragas-max-retries 1`, `--ragas-max-wait 5`, and local `BAAI/bge-m3` embeddings.
- RAGAS judge model: `deepseek/deepseek-chat`.
- Production synthesis/router model: `deepseek/deepseek-v4-flash`.
- Chat proof status: `ANSWERED`.
- Final report status: `checkpoint`.
- Blocker: none.

## Decisions Made

- Keep final RAGAS as report-only evidence and do not convert threshold misses into a CI blocker in Phase 8.
- Do not change guard behavior, citation validation, access filters, weak-evidence thresholds, corpus content, model settings, router code, or graph retrieval code.
- Treat router false-`MULTI_HOP` and judge structured-output stabilization as backlog/future work.

## Deviations from Plan

### Accepted Report-Only Threshold Misses

**1. Outcome accuracy below threshold**
- **Observed:** `outcome_accuracy=0.575`, threshold `0.8`.
- **Reason:** Multi-hop waiver plus router false-`MULTI_HOP` routes answerable rows into a graph path that safely refuses.
- **Impact:** Demo remains acceptable because the system refuses rather than fabricating unsupported answers.

**2. Citation document recall below threshold**
- **Observed:** `citation_doc_recall=0.533`, threshold `0.7`.
- **Reason:** Safe refusals do not emit citations, and multi-hop coverage is intentionally limited.
- **Impact:** Answered rows retain strong faithfulness and context quality.

---

**Total deviations:** 2 accepted report-only threshold misses.
**Impact on plan:** Phase 8 is not blocked; limitations are documented as future work.

## User Setup Required

None for the committed evidence. Future live reruns still require a healthy local compose stack, ignored `infra/.env` credentials, and OpenRouter judge access.

## Next Phase Readiness

Phase 8 can proceed to remaining demo asset work without rerunning final regression. The official 08-03 evidence is fixed at the committed checkpoint.

---
*Phase: 08-delivery-polish-demo-readiness*
*Completed: 2026-06-02*
