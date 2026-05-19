---
phase: 05-retrieval-guards-query-api
plan: "04"
subsystem: graph-retrieval
tags: [neo4j, graph-retrieval, cypher, access-filter, multi-hop, comparison]
requires:
  - phase: 05-retrieval-guards-query-api
    provides: "05-02 query routing/domain primitives and 05-03 RetrievalResult/RetrievalCandidate conventions"
provides:
  - "Read-side graph access-filter Cypher helpers"
  - "GraphRetriever for aggregation, multi-hop, and comparison evidence"
  - "Document-backed graph evidence mapping to RetrievalCandidate values"
  - "Graph dependency and unsupported-depth failure metadata"
affects: [phase-05-reranking, phase-05-orchestration, phase-06-chat, phase-07-evaluation]
tech-stack:
  added: []
  patterns: [document-backed graph evidence, parameterized cypher access predicates, hop-capped traversal, route-specific graph degradation]
key-files:
  created:
    - ai-service/src/corp_rag_ai/pipeline/retrieval/graph_query_helpers.py
    - ai-service/src/corp_rag_ai/pipeline/retrieval/graph.py
    - ai-service/tests/test_graph_retriever.py
  modified:
    - ai-service/src/corp_rag_ai/domain/retrieval.py
    - ai-service/src/corp_rag_ai/pipeline/retrieval/__init__.py
key-decisions:
  - "Graph retrieval always joins entity/relation evidence back to accessible Document nodes before returning candidates."
  - "Multi-hop traversal is capped at 3 hops; deeper explicit requests short-circuit without Neo4j calls."
  - "Factual route ignores graph availability; aggregation/multi-hop/comparison report explicit graph retrieval failure."
patterns-established:
  - "Graph access params use accessLevels, docTypes, departments, and departmentWildcard without interpolating user values."
  - "Graph candidates carry graphPath/candidateGroup metadata for later synthesis or hybrid merge steps."
  - "Read-side graph retrieval modules do not modify the Phase 04 graph write path."
requirements-completed: ["RET-02", "RET-03", "AGT-01"]
duration: 5 min
completed: 2026-05-19
---

# Phase 05 Plan 04: Access-Filtered Neo4j Graph Retrieval Summary

**Document-backed Neo4j graph retrieval for aggregation, multi-hop, and comparison routes**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-19T20:53:32Z
- **Completed:** 2026-05-19T20:58:15Z
- **Tasks:** 3 completed
- **Files modified:** 5 tracked files

## Accomplishments

- Added read-side graph query helpers with parameterized `Document` access predicates for `accessLevel`, `docType`, and department wildcard semantics.
- Added `GraphRetriever` route handling for aggregation, multi-hop, comparison, factual no-op, graph dependency failure, and unsupported hop depth.
- Ensured returned graph evidence is backed by `MENTIONED_IN` or `EVIDENCE` edges to accessible `Document` nodes.
- Added graph candidate metadata (`graphPath`, `candidateGroup`, `relationType`) for later synthesis and comparison merging.
- Added tests for access-filtered Cypher, orphan avoidance, hop caps, dependency failure, factual graph independence, comparison hints, and empty accessible evidence.

## Task Commits

1. **Tasks 1-3: Graph access helpers, graph retrieval, multi-hop/comparison support** - `fab81a4` (`feat(05-04): add graph retriever`)

## Files Created/Modified

- `ai-service/src/corp_rag_ai/pipeline/retrieval/graph_query_helpers.py` - graph access params and Cypher query builders.
- `ai-service/src/corp_rag_ai/pipeline/retrieval/graph.py` - graph retrieval execution and candidate mapping.
- `ai-service/src/corp_rag_ai/domain/retrieval.py` - graph failure reasons and candidate metadata.
- `ai-service/src/corp_rag_ai/pipeline/retrieval/__init__.py` - retrieval package export.
- `ai-service/tests/test_graph_retriever.py` - graph retrieval safety and route behavior coverage.

## Decisions Made

- The graph read path is separate from `graph_indexer.py`; the Phase 04 write path remains untouched.
- Explicit deeper-than-cap multi-hop requests return `unsupported_graph_depth` before opening a Neo4j session.
- Empty accessible graph evidence is a legitimate no-answer outcome, not a dependency failure.

## Deviations from Plan

None - plan executed as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

None.

## Verification

- `uv run --project ai-service --group dev pytest ai-service/tests/test_graph_retriever.py ai-service/tests/test_graph_indexer_write.py` - 12 passed.
- `uv run --project ai-service --group dev pytest ai-service/tests/test_graph_retriever.py ai-service/tests/test_graph_indexer_write.py ai-service/tests/test_graph_indexer_schema.py` - 16 passed.
- `uv run --project ai-service --group dev pytest ai-service/tests/test_graph_retriever.py` - 9 passed.

## User Setup Required

None - no new external service configuration required.

## Next Phase Readiness

Plan 05-05 can combine hybrid and graph candidates through parent resolution, reranking, context packing, and citation lookup. Graph candidates already carry child chunk IDs, parent chunk IDs, document metadata, and graph path summaries.

---
*Phase: 05-retrieval-guards-query-api*
*Completed: 2026-05-19*
