---
phase: 04-python-ingestion-indexing
plan: 05
subsystem: indexing
tags: [bge-m3, FlagEmbedding, qdrant, hybrid-search, vector-indexing]

requires:
  - phase: 04-04
    provides: deterministic child chunks, embedding text, and sanitizer metadata
provides:
  - Local bge-m3 dense+sparse embedding adapter with smoke validation
  - Qdrant documents_chunks collection initializer with named dense and sparse vectors
  - Replace-all child chunk vector upsert and document delete-by-filter semantics
affects: [phase-04-ingestion-orchestration, phase-05-retrieval, qdrant, embeddings]

tech-stack:
  added:
    - "FlagEmbedding>=1.4.0,<2.0.0"
    - "qdrant-client>=1.12.2,<1.18.0"
  patterns:
    - Lazy local model loading with explicit smoke preflight
    - Config-gated startup initialization for external stores
    - Delete-by-filter before vector upsert for idempotent reindexing

key-files:
  created:
    - ai-service/src/corp_rag_ai/pipeline/indexing/__init__.py
    - ai-service/src/corp_rag_ai/pipeline/indexing/embedding.py
    - ai-service/src/corp_rag_ai/pipeline/indexing/vector_indexer.py
    - ai-service/tests/test_embedding_adapter.py
    - ai-service/tests/test_vector_indexer_collection.py
    - ai-service/tests/test_vector_indexer_upsert.py
  modified:
    - ai-service/pyproject.toml
    - ai-service/uv.lock
    - ai-service/src/corp_rag_ai/config.py
    - ai-service/src/corp_rag_ai/main.py

key-decisions:
  - "Followed the locked local FlagEmbedding bge-m3 pivot; no hosted embedding API is used."
  - "Qdrant collection initialization is opt-in through AI_QDRANT_INITIALIZE_COLLECTION and raises on incompatible schema instead of recreating data."
  - "Vector reindexing deletes by documentId before upsert so retries replace old child points."

patterns-established:
  - "Embedding providers expose embed_texts() and return dense plus lexical sparse vectors."
  - "Indexable child DTOs carry sanitized embedding text separately from Qdrant display payload."
  - "Qdrant document cleanup always uses the locked documentId filter selector."

requirements-completed: ["ING-05"]

duration: 14 min
completed: 2026-05-17
---

# Phase 04 Plan 05: Local Embedding And Qdrant Vector Indexing Summary

**Local bge-m3 dense+sparse embeddings with safe Qdrant collection initialization and replace-all child vector upserts**

## Performance

- **Duration:** 14 min
- **Started:** 2026-05-17T15:50:00Z
- **Completed:** 2026-05-17T16:04:00Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Added a lazy local `FlagEmbedding` adapter for `BAAI/bge-m3` that validates 1024-dimensional dense vectors and non-empty sparse lexical weights.
- Added Qdrant collection initialization for `documents_chunks` with named `dense` and `sparse` vectors plus locked payload indexes.
- Added replace-all vector indexing semantics: delete existing points by `documentId`, embed sanitized child text, then upsert one point per child chunk.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add local FlagEmbedding adapter with smoke fallback** - `7dccd2c` (feat)
2. **Task 2: Implement Qdrant collection initializer and payload indexes** - `7cf79ae` (feat)
3. **Task 3: Implement vector upsert and delete-by-document** - `84dcaf0` (feat)

**Plan metadata:** this summary commit

## Files Created/Modified

- `ai-service/src/corp_rag_ai/pipeline/indexing/embedding.py` - Local bge-m3 adapter, dense/sparse output validation, live-smoke cache gate.
- `ai-service/src/corp_rag_ai/pipeline/indexing/vector_indexer.py` - Qdrant schema initializer, sparse conversion, point construction, replace/delete APIs.
- `ai-service/src/corp_rag_ai/config.py` - Qdrant initialization and embedding smoke/model settings.
- `ai-service/src/corp_rag_ai/main.py` - Opt-in startup collection initialization.
- `ai-service/pyproject.toml` and `ai-service/uv.lock` - Added `FlagEmbedding` and `qdrant-client`.
- `ai-service/tests/test_embedding_adapter.py` - Mocked local embedding adapter tests.
- `ai-service/tests/test_vector_indexer_collection.py` - Collection create/no-op/incompatible-schema tests.
- `ai-service/tests/test_vector_indexer_upsert.py` - Delete-by-filter, sorted sparse vector, and payload tests.

## Decisions Made

- Followed the plan's local `FlagEmbedding` decision and kept model loading lazy so unit tests do not download weights.
- Kept Qdrant collection creation behind `AI_QDRANT_INITIALIZE_COLLECTION=false` by default, preserving broker-independent and store-independent unit tests.
- Represented sanitized embedding text separately from Qdrant payload content so `content_for_embedding` is never persisted in payloads.

## Deviations from Plan

None - plan behavior executed as written. Both planned dependencies were resolved before task commits, while Qdrant behavior remained isolated to the Task 2 and Task 3 commits.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** None.

## Issues Encountered

- Live bge-m3 smoke was skipped because no local Hugging Face model cache is present (`model_cache_available()` returned `False`). This matches the plan: live smoke runs only when explicitly enabled or when the model cache exists.

## Verification

- `uv run pytest tests` - PASSED, 67 tests.
- Local bge-m3 live smoke gate - SKIPPED, no model cache present.
- Qdrant initializer tests cover collection create, existing matching schema, dense size mismatch, dense distance mismatch, and missing sparse vector.

## User Setup Required

None - no external service configuration file was generated. UAT still requires the bge-m3 model cache or explicit live-smoke enablement before end-to-end validation.

## Next Phase Readiness

Plan 04-06 can use the same local embedding adapter for entity embeddings and can rely on Qdrant child vector indexing for ingestion orchestration in Plan 04-07.

---
*Phase: 04-python-ingestion-indexing*
*Completed: 2026-05-17*
