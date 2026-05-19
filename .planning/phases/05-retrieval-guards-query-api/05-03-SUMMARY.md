---
phase: 05-retrieval-guards-query-api
plan: "03"
subsystem: qdrant-retrieval
tags: [qdrant, hybrid-retrieval, dense-sparse, rrf, access-filter, bge-m3]
requires:
  - phase: 05-retrieval-guards-query-api
    provides: "05-02 internal QueryInput, AccessFilter, RetrievalOptions, RouteDecision, and retrieval domain types"
provides:
  - "AccessFilter to Qdrant payload Filter translation"
  - "Qdrant dense+sparse RRF query primitive with storage-level access filtering"
  - "HybridRetriever that embeds a query and maps child-chunk payloads to RetrievalCandidate values"
  - "Flagged evidence score penalty with sanitizer flags preserved"
affects: [phase-05-graph-retrieval, phase-05-reranking, phase-05-orchestration, phase-07-evaluation]
tech-stack:
  added: []
  patterns: [storage-level access filters, qdrant named-vector RRF query, retrieval failure result, flagged-evidence downranking]
key-files:
  created:
    - ai-service/src/corp_rag_ai/pipeline/retrieval/__init__.py
    - ai-service/src/corp_rag_ai/pipeline/retrieval/hybrid.py
    - ai-service/tests/test_vector_indexer_query.py
    - ai-service/tests/test_hybrid_retriever.py
  modified:
    - ai-service/src/corp_rag_ai/pipeline/indexing/vector_indexer.py
    - ai-service/src/corp_rag_ai/domain/retrieval.py
key-decisions:
  - "Qdrant access filters are applied to both dense and sparse prefetches, plus the top-level query filter."
  - "Empty department lists preserve Java wildcard semantics by omitting only the department condition."
  - "Hybrid retrieval distinguishes zero permitted chunks from dependency failure through RetrievalResult.failure_reason and metadata warnings."
  - "Flagged chunks remain retrievable but have their score multiplied by the configured 0.5 default."
patterns-established:
  - "QdrantVectorIndex.query_hybrid owns named dense/sparse Prefetch construction and RRF FusionQuery."
  - "HybridRetriever maps only Qdrant-returned payloads; it does not perform in-memory access filtering."
  - "RetrievalResult carries candidates, metadata, and optional failure reason for orchestration."
requirements-completed: ["RET-01", "RET-02", "RET-04"]
duration: 7 min
completed: 2026-05-19
---

# Phase 05 Plan 03: Access-Filtered Qdrant Hybrid Retrieval Summary

**Qdrant dense+sparse RRF retrieval with Java-provided access filters pushed into storage**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-19T20:46:18Z
- **Completed:** 2026-05-19T20:53:32Z
- **Tasks:** 3 completed
- **Files modified:** 6 tracked files

## Accomplishments

- Added `qdrant_filter_from_access_filter` and `QdrantVectorIndex.query_hybrid`, using named `dense`/`sparse` prefetches and `FusionQuery(RRF)`.
- Ensured Qdrant receives `accessLevel` and `docType` conditions for every query, plus a `department` condition only when Java resolved non-wildcard departments.
- Added `HybridRetriever` that embeds query text, calls the Qdrant primitive, and maps payloads into child-level retrieval candidates with document metadata and parent chunk IDs.
- Added retrieval failure metadata for `embedding_unavailable` and `vector_retrieval_unavailable`, distinct from legitimate zero-result retrieval.
- Applied the flagged-evidence score penalty while preserving sanitizer flags for later output guard decisions.

## Task Commits

1. **Task 1: Add Qdrant access filter translation** - `500219c` (`feat(05-03): add access-filtered qdrant query`)
2. **Tasks 2-3: Implement dense+sparse RRF hybrid query, flagged penalty, and metadata** - `73ae4bd` (`feat(05-03): add hybrid retriever`)

## Files Created/Modified

- `ai-service/src/corp_rag_ai/pipeline/indexing/vector_indexer.py` - access-filter translator and hybrid Qdrant query method.
- `ai-service/src/corp_rag_ai/pipeline/retrieval/hybrid.py` - query embedding, Qdrant retrieval, candidate mapping, failure metadata, flagged downranking.
- `ai-service/src/corp_rag_ai/domain/retrieval.py` - parent chunk ID, retrieval failure reason, and retrieval result wrapper.
- `ai-service/tests/test_vector_indexer_query.py` - exact Qdrant filter and prefetch assertions.
- `ai-service/tests/test_hybrid_retriever.py` - candidate mapping, zero results, dependency failure, and flagged score penalty tests.

## Decisions Made

- Qdrant filtering is storage-first. Tests inspect the filter passed into Qdrant instead of validating Python-side post-filtering.
- `PUBLIC` visibility is not broadened in Python; access levels are used exactly as Java resolved them.
- Hybrid retrieval does not call graph/Neo4j dependencies; graph retrieval remains isolated to 05-04.

## Deviations from Plan

None - plan executed as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

None.

## Verification

- `uv run --project ai-service --group dev pytest ai-service/tests/test_vector_indexer_query.py ai-service/tests/test_hybrid_retriever.py ai-service/tests/test_embedding_adapter.py` - 11 passed.
- `uv run --project ai-service --group dev pytest ai-service/tests/test_vector_indexer_query.py ai-service/tests/test_hybrid_retriever.py ai-service/tests/test_vector_indexer_upsert.py ai-service/tests/test_vector_indexer_collection.py ai-service/tests/test_embedding_adapter.py` - 21 passed.
- `uv run --project ai-service --group dev pytest ai-service/tests/test_vector_indexer_query.py ai-service/tests/test_hybrid_retriever.py` - 7 passed.

## User Setup Required

None - no new external service configuration required.

## Next Phase Readiness

Plan 05-04 can build graph retrieval against the same `AccessFilter`, `RetrievalCandidate`, `RetrievalMetadata`, and `RetrievalResult` primitives. Later orchestration can combine hybrid dependency failures and no-evidence results without conflating them.

---
*Phase: 05-retrieval-guards-query-api*
*Completed: 2026-05-19*
