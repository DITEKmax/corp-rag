---
phase: 07-evaluation-observability
plan: "07"
subsystem: evaluation
tags: [eval, retrieval, ablation, qdrant, bm25, graph]
requires:
  - phase: 07-evaluation-observability
    provides: "07-04 retrieval mode primitives and BM25 harness"
  - phase: 07-evaluation-observability
    provides: "07-05 validated Russian golden dataset"
  - phase: 07-evaluation-observability
    provides: "07-06 production RAGAS source report with route metadata"
provides:
  - "retrieval-only five-mode ablation runner for vector-routed golden records"
  - "human-readable, JSON, and CSV Russian ablation reports"
  - "separate graph-route retrieval section"
  - "dense-only and sparse-only live Qdrant payload smoke evidence"
affects: [phase-07-evaluation, phase-08-delivery-polish, retrieval-ablation]
tech-stack:
  added: []
  patterns:
    - "Ablation scope is derived from actual production route/retriever metadata, not nominal golden type."
    - "Graph-routed records stay separate from vector retrieval metrics."
key-files:
  created:
    - ai-service/eval/ablation_runner.py
    - ai-service/eval/reports/ablation_ru.md
    - ai-service/eval/reports/ablation_ru.json
    - ai-service/eval/reports/ablation_ru.csv
    - ai-service/tests/test_eval_ablation_subset.py
    - ai-service/tests/test_eval_ablation_runner.py
    - ai-service/tests/test_eval_graph_report.py
  modified: []
key-decisions:
  - "Use the existing production RAGAS report only as route/retrieval metadata; measure hybrid+reranker by direct hybrid top-k retrieval plus local bge reranking."
  - "Exclude answerable records that production routed to UNSUPPORTED from vector metrics and surface them as route discrepancies."
  - "Record dense/sparse Qdrant payload smoke evidence in the ablation report before publishing metrics."
patterns-established:
  - "Generated ablation reports include scope ids, route discrepancies, vector metrics, graph metrics, and live index evidence."
requirements-completed: ["EVAL-04", "EVAL-02"]
duration: 35 min
completed: 2026-06-01
---

# Phase 07 Plan 07: Retrieval Ablation Summary

**Retrieval-only Russian ablation across BM25, dense, sparse, hybrid, and directly reranked hybrid candidates with graph-route results isolated**

## Performance

- **Duration:** 35 min
- **Completed:** 2026-06-01
- **Tasks:** 4
- **Files modified:** 7 created
- **Commit status:** Included in the 07-07 closeout commit after user confirmation.

## Accomplishments

- Closed the 07-04 carry-forward blocker first: live Qdrant dense-only and sparse-only queries both returned payloads with non-empty `documentId`.
- Added `ai-service/eval/ablation_runner.py` for retrieval-only ablation using actual production route metadata from `ragas_ru.json`.
- Corrected `hybrid+reranker` comparability: it now reranks the same hybrid top-k candidate layer used by `hybrid`, not final synthesis citations.
- Generated reports:
  - `ai-service/eval/reports/ablation_ru.md`
  - `ai-service/eval/reports/ablation_ru.json`
  - `ai-service/eval/reports/ablation_ru.csv`
- Added focused deterministic tests for subset selection, five-mode report shape, and graph-section separation.

## Key Results

Vector-routed answerable subset: 15 records. Graph-routed answerable records: 14. One answerable factual record, `ru-factual-009`, was excluded because production route metadata marked it `UNSUPPORTED`.

| Mode | Records | recall@5 | recall@10 | MRR |
|---|---:|---:|---:|---:|
| `bm25` | 15 | 0.8778 | 0.9667 | 0.9111 |
| `dense` | 15 | 0.9556 | 1.0000 | 0.9667 |
| `sparse` | 15 | 0.9778 | 1.0000 | 1.0000 |
| `hybrid` | 15 | 0.9778 | 1.0000 | 1.0000 |
| `hybrid+reranker` | 15 | 0.9778 | 1.0000 | 1.0000 |

## Interpretation

- BM25 (0.88/0.97/0.91) is noticeably weaker than learned retrieval modes, supporting the thesis: bge-m3 learned sparse превосходит классический BM25.
- Sparse, hybrid, and hybrid+reranker all hit the ceiling at recall@10=1.0 and MRR=1.0.
- The reranker adds no measurable lift because retrieval saturates on a small corpus: 16 indexed docs and 15 vector-routed questions. Relevant documents are already in top-5 with ideal MRR, so there is nothing measurable to improve. This is an honest scale limitation of the experiment, not evidence that reranking is useless; reranker value should appear on larger corpora with noisier candidate sets.
- The graph route remains separate at recall@10=0.29, consistent with the known Phase 8 multi-hop debt.
- `ru-factual-009` is another false-UNSUPPORTED case: the router marked an answerable factual question as UNSUPPORTED. This is the same Phase 8 router debt as the multi-hop issue from 7.1.

Graph route section:

- Records: 14
- Citeable evidence rate: 0.2857
- recall@5: 0.2857
- recall@10: 0.2857
- MRR: 0.2857
- No-evidence refusals: 10

## Task Commits

This summary and all 07-07 ablation artifacts are included in the 07-07 closeout commit created after user confirmation.

## Files Created/Modified

- `ai-service/eval/ablation_runner.py` - ablation runner, report writer, dense/sparse payload smoke, and CLI.
- `ai-service/eval/reports/ablation_ru.md` - human-readable ablation report.
- `ai-service/eval/reports/ablation_ru.json` - machine-readable report with scope, metrics, and payload-smoke evidence.
- `ai-service/eval/reports/ablation_ru.csv` - per-query/per-mode retrieval metrics.
- `ai-service/tests/test_eval_ablation_subset.py` - route-metadata subset selection tests.
- `ai-service/tests/test_eval_ablation_runner.py` - BM25 id mapping and five-mode report tests.
- `ai-service/tests/test_eval_graph_report.py` - graph report separation tests.

## Decisions Made

- `hybrid+reranker` uses direct hybrid retrieval candidates plus local `BAAI/bge-reranker-v2-m3`, so it is comparable to the other retrieval modes and still avoids RAGAS judge calls.
- The runner maps BM25 manifest ids to indexed UUID document ids before scoring, keeping BM25 comparable to Qdrant modes and golden `expected_doc_ids`.
- Graph-routed records are reported from production retrieval metadata in their own section and are not averaged into vector metrics.

## Deviations from Plan

- Task 4 requested committing reports; the commit was held until explicit user confirmation, then included in the closeout commit.

## Issues Encountered

- Qdrant Python client emitted a compatibility warning: client `1.17.1` against server `1.12.6`; live dense/sparse/hybrid retrieval still completed.
- `ru-factual-009` has expected docs but production metadata routed it to `UNSUPPORTED`; the report excludes it from retrieval metrics and records the discrepancy as a false-UNSUPPORTED Phase 8 router debt.
- The first direct reranker rerun warmed/downloaded the local reranker model and produced temporary `reranker_unavailable` warnings; a second warmed rerun produced the final report with no reranker warnings.

## Verification

- PASS: `docker compose -f infra/docker-compose.yml ps` showed all nine services healthy.
- PASS: live dense-only Qdrant smoke returned `documentId=e077eb72-0e27-4e1e-9b63-34316e88b546`.
- PASS: live sparse-only Qdrant smoke returned `documentId=e077eb72-0e27-4e1e-9b63-34316e88b546`.
- PASS: `uv run --project ai-service --group dev pytest ai-service/tests/test_eval_ablation_subset.py ai-service/tests/test_eval_ablation_runner.py ai-service/tests/test_eval_graph_report.py ai-service/tests/test_eval_metrics.py` - 13 passed.
- PASS: `uv run --project ai-service --group dev python -m eval.ablation_runner --qdrant-url http://localhost:6333` generated Markdown, JSON, and CSV reports with `external_judge_used=false`.

## User Setup Required

None.

## Next Phase Readiness

Plan 07-07 evidence is generated and committed. Plan 07-08 can use `ablation_ru.*` directly.

## Self-Check: PASSED

- Five vector modes are present and distinct.
- Vector and graph route ids are listed separately.
- Graph metrics are not averaged into vector metrics.
- Dense/sparse payload smoke is recorded in the report.
- `hybrid+reranker` is measured from direct hybrid retrieval candidates, not final citation order.
- RAGAS judge was not invoked for ablation.
- Report and summary are committed after user confirmation.

---
*Phase: 07-evaluation-observability*
*Completed: 2026-06-01*
