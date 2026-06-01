---
phase: 07-evaluation-observability
plan: "04"
subsystem: evaluation
tags: [eval, retrieval, ablation, bm25, metrics]
requires:
  - phase: 07-evaluation-observability
    provides: "07-03 frozen corpus and eval package foundation"
provides:
  - "eval-only dense, sparse, and hybrid Qdrant query modes"
  - "classical BM25 lexical baseline under ai-service/eval"
  - "retrieval-mode labels for bm25, dense, sparse, hybrid, and hybrid+reranker"
  - "deterministic document-level recall@k, MRR, and nDCG helpers"
affects: [phase-07-evaluation, retrieval-ablation, eval-reports]
tech-stack:
  added:
    - "bm25s>=0.2,<1.0"
  patterns:
    - "Production /v1/query keeps hybrid RRF as the default and exposes no retrieval-mode switch"
    - "Classical BM25 lives only under ai-service/eval and stays distinct from bge-m3 learned sparse retrieval"
key-files:
  created:
    - ai-service/eval/retrieval_modes.py
    - ai-service/eval/bm25.py
    - ai-service/eval/metrics.py
    - ai-service/tests/test_eval_bm25.py
    - ai-service/tests/test_eval_metrics.py
  modified:
    - ai-service/pyproject.toml
    - ai-service/uv.lock
    - ai-service/src/corp_rag_ai/pipeline/indexing/vector_indexer.py
    - ai-service/tests/test_vector_indexer_query.py
key-decisions:
  - "Use bm25s 0.3.9 for the eval-only classical lexical baseline."
  - "Filter zero-score BM25 hits by default so no-overlap lexical queries do not look like evidence."
  - "Compute retrieval metrics only over expected_doc_ids; expected_chunk_hint remains advisory."
patterns-established:
  - "RetrievalMode maps vector variants to VectorQueryMode while rejecting bm25 as a Qdrant mode."
requirements-completed: ["EVAL-04", "EVAL-02"]
duration: 16 min
completed: 2026-06-01
---

# Phase 07 Plan 04: Retrieval Ablation Primitives Summary

**Eval-only retrieval modes, BM25 baseline, and deterministic document-level metrics**

## Performance

- **Duration:** 16 min
- **Completed:** 2026-06-01
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Added internal `VectorQueryMode` support for dense-only, sparse-only, and hybrid RRF Qdrant query construction.
- Kept production retrieval unchanged: `HybridRetriever` still calls `query_hybrid()` without a mode argument, so the default remains dense+sparse RRF.
- Added `eval.retrieval_modes.RetrievalMode` with the five ablation labels: `bm25`, `dense`, `sparse`, `hybrid`, and `hybrid+reranker`.
- Added an eval-only `bm25s` baseline over committed corpus text with document ids and metadata preserved for recall/MRR reporting.
- Added retrieval metric helpers for recall@k, MRR, and optional nDCG over `expected_doc_ids[]`.

## Task Commits

1. **Task 1: Add internal vector retrieval modes** - `f4791c6` (`feat(07-04): add eval vector query modes`)
2. **Task 2: Add BM25 baseline harness** - `bbddf9c` (`feat(07-04): add eval bm25 baseline`)
3. **Task 3: Add retrieval metric helpers** - `e3db4ac` (`feat(07-04): add retrieval metrics helpers`)

## Files Created/Modified

- `ai-service/src/corp_rag_ai/pipeline/indexing/vector_indexer.py` - internal `VectorQueryMode` plus dense/sparse/hybrid Qdrant argument construction.
- `ai-service/eval/retrieval_modes.py` - eval-only ablation mode names and mapping to vector query modes.
- `ai-service/eval/bm25.py` - classical BM25 baseline using `bm25s`.
- `ai-service/eval/metrics.py` - recall@k, MRR, nDCG, per-record scoring, and metric summaries.
- `ai-service/tests/test_vector_indexer_query.py` - dense-only and learned-sparse-only query construction coverage.
- `ai-service/tests/test_eval_bm25.py` - BM25 ranking and mode-distinction coverage.
- `ai-service/tests/test_eval_metrics.py` - duplicate, no-hit, multi-doc, and validation coverage.
- `ai-service/pyproject.toml`, `ai-service/uv.lock` - added `bm25s`.

## Decisions Made

- Dense and sparse Qdrant modes reuse the same access-filter conversion as hybrid mode.
- BM25 zero-score hits are filtered by default to avoid treating arbitrary no-overlap documents as retrieved evidence.
- No FastAPI, Java, frontend, or contract retrieval-mode field was added.

## Deviations from Plan

- `ai-service/src/corp_rag_ai/pipeline/retrieval/hybrid.py` did not need changes because production defaults are preserved at the vector index boundary.

## Issues Encountered

- Docker-backed Qdrant smoke could not be executed because the compose project has no running services. `docker compose -f infra/docker-compose.yml ps` returned only the table header.
- Therefore the live payload contract for dense-only and sparse-only retrieval returning non-empty `documentId` remains unverified until the frozen corpus is indexed.

## Verification

- PASS: `uv run --project ai-service --group dev pytest ai-service/tests/test_vector_indexer_query.py` - 4 passed.
- PASS: `uv run --project ai-service --group dev pytest ai-service/tests/test_eval_bm25.py` - 3 passed.
- PASS: `uv run --project ai-service --group dev pytest ai-service/tests/test_eval_metrics.py` - 6 passed.
- PASS: `uv run --project ai-service --group dev pytest ai-service/tests/test_vector_indexer_query.py ai-service/tests/test_eval_bm25.py ai-service/tests/test_eval_metrics.py` - 13 passed.
- PASS: static scan for retrieval-mode terms found only `ai-service/eval`, tests, and the internal vector indexer enum; no `/v1/query`, Java, frontend, or contract surface was added.
- BLOCKED: Docker-backed dense/sparse Qdrant payload smoke, because no local compose services are running.

## Next Phase Readiness

The code prerequisites for retrieval ablation are present. Plan 07-05 is still blocked until the frozen corpus is indexed and `golden_ru.meta.json` records indexing evidence.

## Self-Check: PASSED WITH LIVE-SMOKE BLOCKER

- Summary exists and references all 07-04 commits.
- Deterministic tests pass.
- BM25 and learned sparse are separate implementations and mode names.
- Production query behavior remains default hybrid RRF.
- Live Qdrant payload verification is explicitly carried forward.

---
*Phase: 07-evaluation-observability*
*Completed: 2026-06-01*
