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
