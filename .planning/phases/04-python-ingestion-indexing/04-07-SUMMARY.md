---
phase: 04-python-ingestion-indexing
plan: 07
subsystem: ingestion
tags: [python, amqp, minio, qdrant, neo4j, ingestion]

requires:
  - phase: 04-python-ingestion-indexing
    provides: parser, chunker, sanitizer, vector indexing, graph indexing, AMQP foundation
provides:
  - Full upload ingestion orchestration from AMQP event to terminal indexed or failed event
  - Delete-event cleanup path for Qdrant, Neo4j, parent chunks, state tombstone, and processed event
  - MinIO source fetch adapter using official SDK with async wrapper and stage-aware failure mapping
affects: [phase-04-uat, phase-05-retrieval, java-indexing-status]

tech-stack:
  added: [minio]
  patterns:
    - terminal-after-outcome processed_events
    - Qdrant rollback after vector or graph-stage failures
    - payload-only upload metadata mapping

key-files:
  created:
    - ai-service/src/corp_rag_ai/adapters/minio/storage.py
    - ai-service/src/corp_rag_ai/pipeline/ingestion/events.py
    - ai-service/src/corp_rag_ai/pipeline/ingestion/orchestrator.py
    - ai-service/tests/test_minio_fetch_adapter.py
    - ai-service/tests/test_ingestion_orchestrator.py
  modified:
    - ai-service/pyproject.toml
    - ai-service/uv.lock
    - ai-service/src/corp_rag_ai/adapters/amqp/publisher.py
    - ai-service/src/corp_rag_ai/config.py
    - ai-service/src/corp_rag_ai/main.py
    - ai-service/src/corp_rag_ai/pipeline/indexing/vector_indexer.py

key-decisions:
  - "DocumentResultPublisher now returns the outbound result event ID so document_index_state can record the exact indexed result event."
  - "Upload and delete handlers share one orchestration service because their terminal processed_events semantics and cleanup dependencies are coupled."
  - "Sanitized child text overrides Qdrant payload content and embedding text while parent chunk storage remains unsanitized as planned."

patterns-established:
  - "Result publish before terminal state: indexed/failed AMQP publish completes before state terminal update and processed_events insert."
  - "Rollback-on-failure: vector, entity, and graph-stage failures trigger best-effort Qdrant delete-by-filter before failed event publication."
  - "Late delete protection: DELETED tombstones cause upload events and MinIO 404 delete races to terminally skip without failed events."

requirements-completed: ["ING-01", "ING-02", "ING-03", "ING-04", "ING-05", "ING-06", "ING-07"]

duration: 18 min
completed: 2026-05-17
---

# Phase 04 Plan 07: Full Ingestion Orchestration Summary

**Python upload and delete events now drive the full ingestion pipeline with terminal outcome semantics and rollback protection.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-05-17T16:28:29Z
- **Completed:** 2026-05-17T16:46:01Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- Added the official MinIO SDK and an async-safe fetch adapter that maps timeout, 403, and 404 cases into the locked failure/deletion race behavior.
- Wired upload events through fetch, parse, chunk, sanitize, parent storage, Qdrant upsert, Gemini entity extraction, Neo4j write, and terminal indexed/failed publication.
- Implemented delete cleanup for Qdrant, Neo4j, parent chunks, DELETED tombstones, and terminal processed_events, with mocked integration coverage for duplicate redelivery and failure ordering.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement MinIO fetch adapter and upload event mapping** - `f806aa2` (feat)
2. **Task 2: Implement upload handler with terminal success/failure semantics** - `3201efa` (feat)
3. **Task 3: Implement delete handler and integration-style pipeline tests** - `500dda6` (test)

**Plan metadata:** pending in docs commit.

## Files Created/Modified

- `ai-service/src/corp_rag_ai/adapters/minio/storage.py` - Official MinIO SDK adapter with `asyncio.to_thread` fetch and FETCHING failure classification.
- `ai-service/src/corp_rag_ai/pipeline/ingestion/events.py` - Event payload to internal upload/delete metadata mapping.
- `ai-service/src/corp_rag_ai/pipeline/ingestion/orchestrator.py` - Upload/delete ingestion service with terminal state ordering, rollback, and cleanup behavior.
- `ai-service/src/corp_rag_ai/adapters/amqp/publisher.py` - Result publisher returns outbound event IDs.
- `ai-service/src/corp_rag_ai/pipeline/indexing/vector_indexer.py` - Sanitized payload override and VECTOR_UPSERT failure mapping.
- `ai-service/src/corp_rag_ai/main.py` - AMQP consumer startup now builds real ingestion handlers and service dependencies.
- `ai-service/tests/test_ingestion_orchestrator.py` - Mocked end-to-end pipeline tests for success, parsing failure, graph rollback, delete races, duplicates, and delete cleanup.
- `ai-service/tests/test_minio_fetch_adapter.py` - MinIO adapter and upload metadata tests.

## Decisions Made

- Use the event payload as the only source for upload metadata. The Python service does not query Java for document metadata.
- Return result event IDs from the AMQP publisher so `last_indexed_event_id` can point at the Java-visible indexed event rather than the inbound upload event.
- Keep delete handling inside the same ingestion service as upload handling to centralize idempotency, terminal state, and cleanup ordering.

## Deviations from Plan

Task 3 delete-handler implementation landed with Task 2 because upload/delete orchestration shares the same service object and dependency wiring. Task 3 then added the required edge-case coverage. No behavior was skipped.

**Total deviations:** 1 scope-ordering adjustment. **Impact:** No user-facing or architectural drift; the final behavior matches the plan.

## Issues Encountered

- `python scripts\verify-contracts.py` failed initially because this shell resolves `python.exe` to the Windows Store shim and `mvn` is not on PATH.
- Verification passed after running through `uv` and setting `MAVEN_CMD=C:\dev\apache-maven-3.9.15\bin\mvn.cmd`.

## Verification

- `uv run pytest tests/test_minio_fetch_adapter.py` - passed, 4 tests.
- `uv run pytest tests/test_ingestion_orchestrator.py tests/test_vector_indexer_upsert.py tests/test_amqp_publisher.py` - passed, 14 tests.
- `$env:MAVEN_CMD='C:\dev\apache-maven-3.9.15\bin\mvn.cmd'; uv run python ..\scripts\verify-contracts.py` - passed.
- `uv run pytest tests` - passed, 95 passed and 1 skipped.

## User Setup Required

None - no external service configuration required by this plan.

## Next Phase Readiness

Ready for 04-08: final docs, live smoke helpers, and retained-volume Phase 4 UAT evidence. The remaining validation needs live Docker services, model cache/Gemini key preflights, and UAT scenario execution.

## Self-Check: PASSED

- All three planned tasks have commits.
- `04-07-SUMMARY.md` created with task commits, verification, decisions, and deviations.
- Success, failure, delete race, duplicate redelivery, graph rollback, and delete cleanup behaviors are covered under mocks.

---
*Phase: 04-python-ingestion-indexing*
*Completed: 2026-05-17*
