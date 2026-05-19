---
phase: 05-retrieval-guards-query-api
plan: "05"
subsystem: context-reranking
tags: [parent-resolution, reranker, context-packing, citations, chunk-detail]
requires:
  - phase: 05-retrieval-guards-query-api
    provides: "05-03 hybrid candidates and 05-04 graph candidates with child and parent chunk IDs"
provides:
  - "AI Postgres parent chunk lookup by parent ID and document ID"
  - "ParentResolver that dedupes parent context units while preserving child citation candidates"
  - "Local bge-reranker-v2-m3 adapter with semaphore and soft degradation"
  - "XML-style context packer with parent-boundary token cap and child-level citation drafts"
  - "Chunk detail REST adapter/router mapping to generated contract ChunkDetail"
affects: [phase-05-synthesis, phase-05-query-api, phase-06-citations, phase-07-evaluation]
tech-stack:
  added: []
  patterns: [parent context units, child citation IDs, reranker degradation metadata, xml evidence boundaries]
key-files:
  created:
    - ai-service/src/corp_rag_ai/pipeline/retrieval/parent_resolver.py
    - ai-service/src/corp_rag_ai/pipeline/retrieval/reranker.py
    - ai-service/src/corp_rag_ai/pipeline/retrieval/context_packer.py
    - ai-service/src/corp_rag_ai/adapters/rest/chunks.py
    - ai-service/tests/test_parent_resolver.py
    - ai-service/tests/test_reranker.py
    - ai-service/tests/test_context_packer.py
    - ai-service/tests/test_chunk_detail_router.py
  modified:
    - ai-service/src/corp_rag_ai/repositories/ingestion_state.py
    - ai-service/src/corp_rag_ai/config.py
    - ai-service/src/corp_rag_ai/main.py
    - ai-service/tests/test_ingestion_state_repositories.py
key-decisions:
  - "Parent chunks are fetched from AI Postgres and used as context units; child chunks remain citation IDs."
  - "Reranker failures and disabled reranker state preserve candidates but set rerankerUsed=false-equivalent metadata through warnings."
  - "Context packing uses XML-style evidence boundaries and truncates a single oversized parent only as a last resort."
  - "Chunk detail route maps internal records to generated ChunkDetail without changing OpenAPI contracts."
patterns-established:
  - "ParentResolution carries parent contexts plus citation_candidates separately."
  - "RerankOutcome distinguishes reranker-used scores from raw retrieval-order fallback."
  - "PackedContext carries text, child-level CitationDrafts, token count, and warnings."
requirements-completed: ["RET-04", "AGT-03", "SEC-01"]
duration: 6 min
completed: 2026-05-19
---

# Phase 05 Plan 05: Parent Resolution, Reranking, Context, And Citations Summary

**Parent-context packing with child citations, local reranker degradation, and chunk-detail contract support**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-19T20:58:15Z
- **Completed:** 2026-05-19T21:04:23Z
- **Tasks:** 3 completed
- **Files modified:** 12 tracked files

## Accomplishments

- Added parent chunk read methods and `ParentResolver` to dedupe parent context units by `parentChunkId`, order by max child score, and preserve child candidates as citation units.
- Added lazy local `FlagReranker` adapter using `asyncio.to_thread`, normalized scores, semaphore concurrency, and raw-order fallback warnings.
- Added XML-style context packing with a token cap, parent-boundary truncation preference, and child-level `CitationDraft` creation.
- Added chunk-detail adapter/router and included it in the FastAPI app so Phase 6 source viewing can consume generated `ChunkDetail` shape.
- Verified contract generation/imports after adding the chunk-detail mapping path.

## Task Commits

1. **Task 1: Parent lookup and child-to-parent resolution** - `f4b0abf` (`feat(05-05): add parent context resolver`)
2. **Task 2: Local reranker with soft degradation** - `6a2aade` (`feat(05-05): add local reranker adapter`)
3. **Task 3: Context packing and chunk detail support** - `595ec8d` (`feat(05-05): add context packing and chunk detail`)

## Files Created/Modified

- `ai-service/src/corp_rag_ai/repositories/ingestion_state.py` - parent chunk read methods.
- `ai-service/src/corp_rag_ai/pipeline/retrieval/parent_resolver.py` - parent resolution and missing-parent warnings.
- `ai-service/src/corp_rag_ai/pipeline/retrieval/reranker.py` - local reranker adapter and fallback outcomes.
- `ai-service/src/corp_rag_ai/pipeline/retrieval/context_packer.py` - XML evidence context and citation draft creation.
- `ai-service/src/corp_rag_ai/adapters/rest/chunks.py` - chunk detail record, mapper, and router.
- `ai-service/src/corp_rag_ai/config.py` - final top-N and reranker concurrency settings.
- `ai-service/src/corp_rag_ai/main.py` - chunk detail router registration.
- Focused tests for parent resolver, reranker, context packer, chunk detail router, and repository reads.

## Decisions Made

- Missing parents warn and exclude only the missing parent from context; usable parents still proceed.
- Reranker confidence scores and raw retrieval scores are kept semantically distinct by `RerankOutcome.reranker_used`.
- The chunk-detail route returns 503 when no service is configured rather than pretending storage is available.

## Deviations from Plan

None - plan executed as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

None.

## Verification

- `uv run --project ai-service --group dev pytest ai-service/tests/test_parent_resolver.py ai-service/tests/test_ingestion_state_repositories.py ai-service/tests/test_reranker.py ai-service/tests/test_context_packer.py ai-service/tests/test_chunk_detail_router.py` - 18 passed.
- `uv run --project ai-service --group dev python scripts/verify-contracts.py` with `MAVEN_CMD=C:\dev\apache-maven-3.9.15\bin\mvn.cmd` - passed.

## User Setup Required

None - no new external service configuration required.

## Next Phase Readiness

Plan 05-06 can synthesize cited answers from `PackedContext`, child-level citations, reranker/degradation warnings, and retrieval failure metadata.

---
*Phase: 05-retrieval-guards-query-api*
*Completed: 2026-05-19*
