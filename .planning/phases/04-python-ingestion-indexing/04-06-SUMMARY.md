---
phase: 04-python-ingestion-indexing
plan: 06
subsystem: indexing
tags: [neo4j, gemini, google-genai, graph-rag, entity-extraction]

requires:
  - phase: 04-05
    provides: local bge-m3 embeddings and Qdrant vector indexing
provides:
  - Provenance-first Neo4j Document/Entity/RelationMention graph indexing
  - Versioned Gemini entity/relation extraction prompt and structured-output adapter
  - Golden fixture, CI-safe graph extraction tests, and skipped live Gemini integration smoke
affects: [phase-04-ingestion-orchestration, phase-05-retrieval, neo4j, gemini]

tech-stack:
  added:
    - "neo4j>=5.28.4,<6.0.0"
    - "google-genai>=2.0.0,<3.0.0"
  patterns:
    - Config-gated Neo4j schema initialization
    - Parent-level structured Gemini extraction with one malformed-output retry
    - Deterministic UUID v5 graph entity and relation mention IDs

key-files:
  created:
    - ai-service/src/corp_rag_ai/pipeline/indexing/graph_indexer.py
    - ai-service/src/corp_rag_ai/pipeline/indexing/entity_extractor.py
    - ai-service/src/corp_rag_ai/pipeline/indexing/prompts/entity_extraction_v1.md
    - ai-service/tests/fixtures/entity_extraction/01_hr_policy_basic.json
    - ai-service/tests/test_graph_indexer_schema.py
    - ai-service/tests/test_graph_indexer_write.py
    - ai-service/tests/test_entity_extractor.py
    - ai-service/tests/test_entity_extraction_fixture.py
    - ai-service/tests/test_entity_extraction_live.py
    - .planning/phases/04-python-ingestion-indexing/04-USER-SETUP.md
  modified:
    - ai-service/pyproject.toml
    - ai-service/uv.lock
    - ai-service/src/corp_rag_ai/config.py
    - ai-service/src/corp_rag_ai/main.py
    - ai-service/README.md

key-decisions:
  - "Neo4j schema initialization is opt-in through AI_NEO4J_INITIALIZE_SCHEMA so unit tests and default local startup do not require a live graph store."
  - "Entity and relation IDs are deterministic UUID v5 values from normalized names/types and source-target-type relation triples."
  - "Gemini malformed structured output gets exactly one local retry; dependency 429/5xx/timeout failures use bounded retry and sanitized StageFailure output."

patterns-established:
  - "Graph writes replace a document by deleting only the Document node and attached edges, then MERGE shared Entity and RelationMention nodes."
  - "Prompt artifacts live under pipeline/indexing/prompts and are versioned by ENTITY_EXTRACTION_PROMPT_VERSION."
  - "Live external-service tests are marked integration and skip unless their required credential is present."

requirements-completed: ["ING-06"]

duration: 13 min
completed: 2026-05-17
---

# Phase 04 Plan 06: Gemini Entity Extraction And Neo4j Graph Indexing Summary

**Parent-level Gemini extraction with deterministic provenance-first Neo4j graph indexing**

## Performance

- **Duration:** 13 min
- **Started:** 2026-05-17T16:12:36Z
- **Completed:** 2026-05-17T16:25:22Z
- **Tasks:** 3
- **Files modified:** 15

## Accomplishments

- Added a Neo4j async graph indexer with locked Document/Entity/RelationMention schema, document-only cleanup, vector index initialization, and write-transaction tests.
- Added a versioned Gemini prompt artifact and structured extractor using `google-genai`, Pydantic validation, whitelist enforcement, malformed-output retry, and dependency backoff.
- Added a golden HR policy fixture, graph dedupe/entity embedding path, skipped live Gemini integration test, and README instructions.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Neo4j async schema initializer and graph indexer** - `1f5c777` (feat)
2. **Task 2: Implement Gemini structured entity extractor and prompt artifact** - `f3b9df1` (feat)
3. **Task 3: Add golden fixture, entity embedding, and live integration test** - `1cda7a8` (feat)

**Plan metadata:** this summary commit

## Files Created/Modified

- `ai-service/src/corp_rag_ai/pipeline/indexing/graph_indexer.py` - Neo4j schema initialization, document cleanup, graph DTOs, deterministic IDs, and write transaction.
- `ai-service/src/corp_rag_ai/pipeline/indexing/entity_extractor.py` - Gemini structured-output extraction, prompt loading, validation/retry handling, extraction mapping, dedupe, and entity embedding.
- `ai-service/src/corp_rag_ai/pipeline/indexing/prompts/entity_extraction_v1.md` - Versioned extraction prompt with whitelist, schema, relation guidance, and few-shot example.
- `ai-service/tests/fixtures/entity_extraction/01_hr_policy_basic.json` - Golden HR policy extraction fixture.
- `ai-service/tests/test_graph_indexer_schema.py` and `ai-service/tests/test_graph_indexer_write.py` - Neo4j schema/write contract tests.
- `ai-service/tests/test_entity_extractor.py`, `ai-service/tests/test_entity_extraction_fixture.py`, and `ai-service/tests/test_entity_extraction_live.py` - Mocked extractor, fixture, dedupe, embedding, and live-smoke coverage.
- `ai-service/src/corp_rag_ai/config.py` and `ai-service/src/corp_rag_ai/main.py` - Config-gated Neo4j schema initialization lifecycle.
- `ai-service/pyproject.toml` and `ai-service/uv.lock` - Added `neo4j`, `google-genai`, and pytest integration marker.
- `ai-service/README.md` - Documented live Gemini smoke execution.
- `.planning/phases/04-python-ingestion-indexing/04-USER-SETUP.md` - Captured `GEMINI_API_KEY` setup for live tests and UAT.

## Decisions Made

- Kept Neo4j startup initialization opt-in to match the Qdrant pattern and avoid requiring external graph infrastructure in unit tests.
- Preserved shared graph nodes by deleting only `(:Document {id})` and attached edges before reindexing a document.
- Used relation mention nodes instead of direct entity-to-entity relationships, preserving provenance through `EVIDENCE` edges.
- Kept live Gemini coverage credential-gated and skipped by default; mocked tests own CI behavior.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added config-gated Neo4j startup initialization**
- **Found during:** Task 1 (Neo4j async schema initializer and graph indexer)
- **Issue:** Wiring `ensure_graph_schema()` directly into FastAPI startup would make default unit/local runs require a live Neo4j service.
- **Fix:** Added `AI_NEO4J_INITIALIZE_SCHEMA` with default `false`, mirroring the existing Qdrant initialization pattern.
- **Files modified:** `ai-service/src/corp_rag_ai/config.py`, `ai-service/src/corp_rag_ai/main.py`, `ai-service/tests/test_graph_indexer_schema.py`
- **Verification:** `uv run pytest tests` passed with store-independent defaults.
- **Committed in:** `1f5c777`

**Total deviations:** 1 auto-fixed (1 missing critical).
**Impact on plan:** The adjustment preserves correctness and testability without changing the graph schema or external behavior when enabled.

## Issues Encountered

- The live Gemini integration test skipped because `GEMINI_API_KEY` is not set in this environment. This is expected and documented in README plus `04-USER-SETUP.md`.

## Verification

- `uv run pytest tests` - PASSED, 82 passed and 1 skipped.
- Live Gemini integration smoke - SKIPPED by default because `GEMINI_API_KEY` is missing.
- Neo4j Cypher tests prove no `Chunk` nodes are created and cleanup does not delete `Entity` or `RelationMention` nodes.
- Stub scan - PASSED, no TODO/FIXME/placeholders or empty UI stubs in created/modified implementation files.
- Threat surface scan - No new security-relevant surface beyond the plan threat model; Gemini and Neo4j surfaces are covered by T-04-06-01 through T-04-06-03.

## User Setup Required

External Gemini credentials are required only for live integration tests and end-of-phase UAT. See `04-USER-SETUP.md` for `GEMINI_API_KEY` setup and verification.

## Next Phase Readiness

Plan 04-07 can wire ingestion orchestration through the Qdrant vector indexer, Gemini extractor, entity embedding path, and Neo4j graph indexer. The graph path now exposes deterministic document replacement and CI-safe tests.

## Self-Check: PASSED

- Found summary, user setup note, graph indexer, entity extractor, and versioned prompt on disk.
- Found task commits `1f5c777`, `f3b9df1`, and `1cda7a8` in git history.
- Final verification passed with `uv run pytest tests` -> 82 passed, 1 skipped.

---
*Phase: 04-python-ingestion-indexing*
*Completed: 2026-05-17*
