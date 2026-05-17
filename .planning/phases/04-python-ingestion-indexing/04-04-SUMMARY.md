---
phase: "04-python-ingestion-indexing"
plan: "04"
subsystem: ingestion
tags: [chunking, tiktoken, sanitizer, qdrant-payload]

requires:
  - phase: "04-02"
    provides: "ingestion state tables, StageFailure taxonomy, and parent chunk repository"
  - phase: "04-03"
    provides: "normalized ParsedDocument and ParsedBlock parser output"
provides:
  - "deterministic cl100k_base child splitting with guarded sentence boundaries"
  - "parent/child chunk domain models and UUID v5 chunker"
  - "Tier-0 corpus sanitizer with prompt-injection and secret-like flags"
affects: ["04-05-vector-indexing", "04-07-ingestion-orchestration", "05-retrieval-answering"]

tech-stack:
  added: ["tiktoken>=0.13.0,<1.0.0"]
  patterns:
    - "deterministic UUID v5 parent/child chunk identifiers"
    - "separate display content and embedding content with breadcrumb serialization"
    - "flag-but-keep sanitizer behavior for suspicious indexable chunks"

key-files:
  created:
    - "ai-service/src/corp_rag_ai/domain/chunks.py"
    - "ai-service/src/corp_rag_ai/pipeline/ingestion/sentence_boundary.py"
    - "ai-service/src/corp_rag_ai/pipeline/ingestion/chunker.py"
    - "ai-service/src/corp_rag_ai/pipeline/ingestion/corpus_sanitizer.py"
    - "ai-service/tests/test_sentence_boundary.py"
    - "ai-service/tests/test_chunker.py"
    - "ai-service/tests/test_corpus_sanitizer.py"
  modified:
    - "ai-service/pyproject.toml"
    - "ai-service/uv.lock"

key-decisions:
  - "Token counting uses tiktoken cl100k_base for all chunk sizing in this plan."
  - "Table blocks are isolated as atomic parent/child chunks so they are never split."
  - "Prompt-injection and secret-like matches set isSanitized=false but remain indexable unless the chunk is empty or garbage."

patterns-established:
  - "ChildChunk.to_qdrant_payload emits the locked child-only payload shape without content_for_embedding."
  - "CorpusSanitizer raises SANITIZATION / INVALID_FILE_FORMAT only when all children are dropped."

requirements-completed: ["ING-03", "ING-04"]

duration: "16 min"
completed: "2026-05-17"
---

# Phase 04 Plan 04: Deterministic Chunking And Tier-0 Sanitizer Summary

**Deterministic parent/child chunking with cl100k token sizing, Qdrant-ready child payloads, and regex-only corpus safety flags**

## Performance

- **Duration:** 16 min
- **Started:** 2026-05-17T18:33:00+03:00
- **Completed:** 2026-05-17T18:48:34+03:00
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Added `tiktoken` and a deterministic child splitter with paragraph/sentence/newline boundary preference, abbreviation guards, overlap, and hard-cut warnings.
- Added parent/child chunk domain models plus a `DocumentChunker` that builds UUID v5 parent and child IDs, separates global child `position` from `position_in_parent`, and serializes embedding breadcrumbs with U+203A.
- Added a Tier-0 sanitizer that removes control/zero-width noise, drops only empty or garbage chunks, flags prompt-injection and secret-like patterns, and fails deterministically when every child is dropped.

## Task Commits

1. **Task 1: Implement token counter and sentence-boundary splitter** - `b18e2bd` (feat)
2. **Task 2: Implement parent-child chunker and serialization** - `fa06f2a` (feat)
3. **Task 3: Implement Tier-0 corpus sanitizer** - `a821be5` (feat)

## Files Created/Modified

- `ai-service/src/corp_rag_ai/pipeline/ingestion/sentence_boundary.py` - cl100k token counter and deterministic child splitting.
- `ai-service/src/corp_rag_ai/domain/chunks.py` - parent/child chunk records and Qdrant payload candidate builder.
- `ai-service/src/corp_rag_ai/pipeline/ingestion/chunker.py` - parent grouping, child chunking, table atomicity, and breadcrumb serialization.
- `ai-service/src/corp_rag_ai/pipeline/ingestion/corpus_sanitizer.py` - cleanup, drop rules, locked sanitizer flags, and all-dropped StageFailure helper.
- `ai-service/tests/test_sentence_boundary.py` - splitter determinism, abbreviation, overlap, and hard-cut coverage.
- `ai-service/tests/test_chunker.py` - deterministic UUID/text, table atomicity, global/local positions, and payload-shape coverage.
- `ai-service/tests/test_corpus_sanitizer.py` - prompt/secret flag families, drop rules, surviving flagged chunks, and all-dropped failure coverage.
- `ai-service/pyproject.toml` and `ai-service/uv.lock` - `tiktoken` dependency.

## Decisions Made

- Used direct `tiktoken.get_encoding("cl100k_base")` access behind a cached helper so all token sizing stays deterministic and local.
- Kept `content_for_embedding` as an in-memory child field only; the Qdrant payload helper intentionally excludes it.
- Isolated table blocks into their own parent/child chunk to satisfy the no-split table contract even when neighboring section text exists.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Verification

- `uv run pytest tests/test_sentence_boundary.py` - passed.
- `uv run pytest tests/test_chunker.py` - passed.
- `uv run pytest tests/test_corpus_sanitizer.py` - passed.
- `uv run pytest tests` - passed, 53 tests.

## Self-Check: PASSED

- Deterministic IDs/texts are covered by unit tests.
- Sanitizer regex fixtures cover every locked pattern family implemented in the plan.
- Child payload candidates include `sectionPath` and global `position`, and exclude `content_for_embedding`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 04-05 can consume `ChildChunk.content_for_embedding`, `ChildChunk.to_qdrant_payload(...)`, and `ChunkingResult.parent_records()` for local bge-m3 embedding and Qdrant vector indexing.

---
*Phase: 04-python-ingestion-indexing*
*Completed: 2026-05-17*
