---
phase: 08-delivery-polish-demo-readiness
plan: "05"
status: active
updated: 2026-06-02
sources:
  - .planning/phases/07.1-fix-russian-router-and-graph-retrieval-quality-for-ragas-bas/07.1-03-SUMMARY.md
  - ai-service/eval/reports/ragas_ru.md
  - ai-service/eval/reports/injection_ru.md
  - docs/decisions/ADR-007-citation-contract-and-refusal-rules.md
  - docs/decisions/ADR-008-guard-architecture.md
---

# Phase 8 Known Limitations

This document records demo-readiness limitations that remain visible after Phase 8 Wave 1 polish. These are not hidden defects and are not treated as successful answers.

## Final Regression Quality vs Coverage

The final Phase 8 regression evidence shows high answer quality where the system answers, and limited answer coverage where it safely refuses instead of fabricating.

Final RAGAS quality metrics:
- `faithfulness=0.991`
- `context_precision=1.0`
- `context_recall=1.0`
- `answer_relevancy=0.865`

Interpretation:
- The system is not hallucinating on answered rows.
- Retrieved context is correct and sufficient for the scored answered rows.
- The cited-answer path remains suitable for demo use with the seeded 16-document corpus.

Coverage limits remain visible and are not hidden:
- `answered_count=16` out of 30 answerable golden rows.
- `outcome_accuracy=0.575` against threshold `0.8` is not passed.
- `citation_doc_recall=0.533` against threshold `0.7` is not passed.

The coverage gap is caused by two documented behaviors. Both produce safe `refused_no_evidence` outcomes rather than invented answers:

1. Multi-hop graph retrieval remains waived for Phase 8. The `ru-multihop-*` rows require text-conditioned multi-document graph retrieval that was deliberately not implemented in the final demo-readiness phase.
2. Router false-`MULTI_HOP` remains a reproducible limitation. The production synthesis/router model, `deepseek/deepseek-v4-flash`, can nondeterministically classify some answerable factual and aggregation questions as `MULTI_HOP`; once routed to graph retrieval, the current graph path may refuse. Across final regression attempts, `answered_count` varied `19 -> 17 -> 16`, while `MULTI_HOP` volume varied `10 -> 12`. This is a measured limitation, not a one-off random miss.

`citation_doc_recall=0.533` is partly explained by the same two causes: rows that fall into multi-hop refusal do not produce citations, so document-id recall is capped even though answered rows have strong faithfulness and context scores.

Judge stability remains a separate report-only caveat:
- The final evidence includes 3 DeepSeek judge `OUTPUT_PARSING_FAILURE` cases (`ru-aggregation-001`, `ru-aggregation-006`, `ru-aggregation-007`).
- This is the same structured-output instability class seen elsewhere with DeepSeek.
- It was bounded with `--ragas-max-retries 1` and is recorded rather than masked.

Backlog candidates:
- Stabilize router false-`MULTI_HOP` behavior for answerable factual and aggregation questions.
- Improve judge structured-output resilience for RAGAS scoring.

These items were consciously not fixed in Phase 8 because this is the final delivery-polish phase and the scope was not expanded to router redesign, judge redesign, or graph retrieval redesign.

## Waived For Phase 8 Demo

### Russian Multi-Hop Graph Retrieval

Records `ru-multihop-002`, `ru-multihop-003`, `ru-multihop-005`, and `ru-multihop-006` are explicitly waived for the Phase 8 demo scope.

Current behavior:
- Phase 07.1 fixed the router/localization issue for these rows; they now route to `MULTI_HOP`.
- They still return `refused_no_evidence` because current graph retrieval does not reliably gather text-conditioned evidence across multiple Russian documents.
- This is safe behavior: the system refuses instead of fabricating unsupported answers or emitting uncited claims.

Boundary:
- Phase 8 Plan 08-05 does not implement multi-hop graph retrieval redesign, semantic path ranking, entity-linking redesign, duplicate path suppression, hybrid graph/vector fallback, or broad Cypher changes.
- Citation validation, weak-evidence thresholds, refusal behavior, and access filters remain unchanged.

Future work:
- Improve text-conditioned multi-document graph retrieval so the waived records answer with valid document-backed citations.

## Non-Attempted Stretch Items

### Data-Exfiltration Guard Classification

The Russian injection probe report shows data-exfiltration attempts are blocked from succeeding, but they currently resolve as `refused_no_evidence` / `UNSUPPORTED` instead of explicit `refused_guard` classifications.

Boundary:
- Phase 8 Plan 08-05 documents this finding only.
- It does not add, tune, or weaken guard classifier logic.

Future work:
- Add explicit data-exfiltration guard classification while preserving current prompt-injection, jailbreak, citation, output guard, access-filter, and refusal protections.

### `ru-factual-009` Router/Unsupported Result

`ru-factual-009` remains an eval-quality stretch item: expected outcome is `answered`, but the current report shows `refused_no_evidence` with route `UNSUPPORTED`.

Boundary:
- Phase 8 Plan 08-05 does not retune the router, train a classifier, mutate the golden set, or add a golden-specific special case.

Future work:
- Investigate as general router/retrieval quality work only, with no regression to guard, citation, or access-filter contracts.

## Demo Framing

The demo can present the implemented RAG system, seed corpus readiness, compose health, citations, access control, and guard behavior. The limitations above should be described as known future work, not as silent failures or changed acceptance criteria.
