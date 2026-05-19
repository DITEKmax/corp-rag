---
status: complete
result: passed
phase: 04-python-ingestion-indexing
source: ["04-UAT.md", "manual UAT report 2026-05-19"]
updated: 2026-05-19
---

# Phase 4 UAT Evidence

Phase 4 UAT passed end-to-end on 2026-05-19. P1, P2, and P3 preflights passed. Scenarios 2 through 6 passed. Scenario 1 was skipped because the retained Phase 3 AMQP messages were lost before the Phase 4.5 LLM-provider pivot, so that specific retained-volume test could no longer be executed.

## Runtime Stack

| Component | Evidence |
|---|---|
| Python AI image | `corp-rag-python-ai:phase1` at commit `9d7842d` with ISO 8601 AMQP datetime fix |
| Java backend image | `corp-rag-java-backend:phase1` |
| LLM | DeepSeek V4 Flash through OpenRouter free tier, 1000 RPD with $10 credit |
| Embedder | `BAAI/bge-m3` through local FlagEmbedding, dense 1024 + sparse + ColBERT |
| Containers | All 9 containers healthy: postgres, rabbitmq, minio, qdrant, neo4j, langfuse, java-backend, python-ai, frontend |

## Result Matrix

| Check | Result | Evidence |
|---|---|---|
| P1 FlagEmbedding bge-m3 smoke | PASSED | Dense and sparse vectors were produced locally. |
| P2 DeepSeek/OpenRouter smoke | PASSED | DeepSeek returned valid entity extraction JSON. |
| P3 Docker stack startup | PASSED | 9 containers healthy, lifespan complete, `/diagnostics` returned 4 true flags. |
| Scenario 1: accumulated Phase 3 messages | SKIPPED | Phase 3 accumulated AMQP messages were lost before Phase 4.5 pivot; the test was impossible to run honestly. |
| Scenario 2: fresh Markdown happy path | PASSED | Document indexed in about 70 seconds with Java, AI Postgres, Qdrant, and Neo4j state aligned. |
| Scenario 3: invalid PDF format | PASSED implicitly | Terminal parsing failure, no Qdrant points, no Neo4j entities, no infinite redelivery. |
| Scenario 4: atomic rollback at Neo4j failure | PASSED | Graph-stage failure left zero Qdrant points for the document. |
| Scenario 5: duplicate redelivery idempotency | PASSED with deferred bug | Final stores stayed consistent; duplicate still re-ran expensive work. |
| Scenario 6: delete cleanup | PASSED | Java soft delete preserved metadata; AI, Qdrant, and Neo4j cleanup completed. |

## Scenario 1 - Accumulated Phase 3 Messages

**Result:** SKIPPED.

The retained Phase 3 AMQP messages were lost before the Phase 4.5 LLM-provider pivot. The scenario depended on those retained messages and could not be reconstructed without creating new evidence that would no longer test the intended retained-volume state.

## Scenario 2 - Fresh Markdown Happy Path

**Result:** PASSED.

| Field | Value |
|---|---|
| Document ID | `42203559-1ac4-47f7-bbfa-6fdfd2bad4f1` |
| Title | `TechCorp Security Policy v2` |
| File | `phase4-techcorp.md`, 1594 bytes, `text/markdown` |
| Metadata | Department=`IT`, AccessLevel=`INTERNAL`, DocType=`POLICY`, Language=`en` |
| Uploaded | `2026-05-19T17:59:35Z` |
| Indexed | `2026-05-19T18:00:45Z`, about 70 seconds end-to-end |

Observed terminal state:

- Java `documents`: `status=INDEXED`, `chunk_count=1`, `neo4j_entity_count=17`.
- AI `document_index_state`: `status=INDEXED`, `last_failure_stage=NULL`.
- Qdrant: 1 point with full payload schema: `chunkId`, `parentChunkId`, `documentId`, `documentTitle`, `sectionPath`, `position`, `page`, `content`, `language`, `docType`, `department`, `accessLevel`, `isSanitized`, `sanitizerFlags`.
- Neo4j: 17 entities extracted by DeepSeek. Observed entity names included `snyk education`, `engineering department`, `pluralsight`, `chief information security officer`, `techcorp security operations center`, `line managers`, `cisco anyconnect`, `duo security`, `okta`, `it security team`, `compliance department`, `third-party vendors`, `contractors`, `employees`, and `techcorp industries`.

## Scenario 3 - Invalid PDF Format

**Result:** PASSED implicitly.

| Field | Value |
|---|---|
| Document ID | `82c470e5-65ac-459a-8fd6-25689b270d5d` |
| File | `phase4-policy.pdf`, 956 bytes, hand-crafted minimal PDF |

Observed terminal state:

- Java: `status=INDEXING_FAILED`, `failure_stage=PARSING`, `failure_error_code=INVALID_FILE_FORMAT`.
- AI: `status=FAILED`, `last_failure_stage=PARSING`, `last_failure_code=INVALID_FILE_FORMAT`.
- Qdrant: 0 points for this document ID.
- Neo4j: 0 entities for this document ID.
- Failure was classified `retryable=false`, so the bad PDF did not cause infinite redelivery.

Note: Docling rejected PDFs in this Docker setup because OCR engines were missing (`rapidocr`, `easyocr`, and `tesseract` all missing). Markdown ingestion worked through Docling-native/non-OCR paths.

## Scenario 4 - Atomic Rollback At Neo4j Failure

**Result:** PASSED.

Note: the manual UAT note mentioned D-43, but the current `04-CONTEXT.md` defines D-43 as a table-chunking decision, not a rollback decision. This evidence records the observed rollback behavior without assigning an unverified decision number.

Setup: `docker compose stop neo4j`, then upload a valid Markdown document.

| Field | Value |
|---|---|
| Document ID | `8d296658-c8cc-4da9-b24d-944f8d567a83` |
| Title | `Globex Compliance Manual` |
| File | `phase4-globex.md`, 1460 bytes, `text/markdown` |
| Failed stage | `GRAPH_UPSERT` |

Python AI logs showed `ValueError: Cannot resolve address neo4j:7687`, followed by `_best_effort_graph_cleanup` and `_best_effort_qdrant_rollback`.

Observed terminal state:

- Java: `status=INDEXING_FAILED`, `failure_stage=GRAPH_UPSERT`, `failure_error_code=INDEXING_PIPELINE_ERROR`, `failure_retryable=false`.
- AI: `status=FAILED`, `last_failure_stage=GRAPH_UPSERT`, `last_failure_code=INDEXING_PIPELINE_ERROR`.
- Qdrant: 0 points for `8d296658-c8cc-4da9-b24d-944f8d567a83`.
- Stack recovered through `docker compose start neo4j`; Neo4j returned healthy.

## Scenario 5 - Duplicate Redelivery Idempotency

**Result:** PASSED with deferred bug.

Republished the exact duplicate `document.uploaded` event for the TechCorp document through RabbitMQ Management API:

| Field | Value |
|---|---|
| Document ID | `42203559-1ac4-47f7-bbfa-6fdfd2bad4f1` |
| Duplicate event ID | `2e01c126-191a-42a3-887f-f99646973c32` |
| API | `POST /api/exchanges/%2F/corp-rag.documents/publish` |
| Routing key | `document.uploaded` |
| Result | `routed=True` |

Data consistency passed:

- Neo4j entities stayed `17 -> 17`.
- Qdrant points stayed `1 -> 1`.
- AI `processed_events` stayed `4 -> 4`, with no new row.
- Queue ended at 0 messages: consumed and acked.

Deferred bug:

- Python AI logs showed the full pipeline re-ran on the duplicate event.
- Logs included `POST qdrant/points/delete -> 200`, `PUT qdrant/points -> 200`, and OpenRouter chat completions with `4x429` then `1x200`.
- Final state stayed consistent because Neo4j uses MERGE semantics, Qdrant uses delete-then-upsert, and `processed_events` stayed unique.
- Impact: wasted DeepSeek API calls and CPU on duplicate deliveries.

Code evidence:

- `DocumentIngestionService.handle_uploaded` has the intended guard: `if await self._processed_events.has_processed(event.metadata.event_id): return`.
- `IdempotentEventDispatcher` exists in `ai-service/src/corp_rag_ai/adapters/amqp/consumer.py`.
- `ai-service/src/corp_rag_ai/main.py` calls `await service.handle_uploaded(event)` directly inside a fresh `session_scope(session_factory)` and does not wrap handlers through `IdempotentEventDispatcher`.

Working hypothesis for Phase 5:

- Primary hypothesis: wire `IdempotentEventDispatcher` in `main.py` lifespan around upload/delete handlers.
- Secondary hypothesis: validate session/transaction isolation if wrapping alone does not make the guard see committed `processed_events` rows from prior runs.

## Scenario 6 - Delete Cleanup

**Result:** PASSED.

Request:

- `DELETE /api/v1/documents/42203559-1ac4-47f7-bbfa-6fdfd2bad4f1`
- Origin header and admin cookie supplied.
- Response: HTTP 204.

Observed after 20 seconds:

- Java: `status=INDEXED` preserved, `deleted_at=2026-05-19 18:44:54.583527+00`, `deleted_by=b12fc765-...`.
- AI: `status=DELETED`.
- Qdrant: 0 points for the document ID.
- Neo4j: `MATCH` for the `Document` node returned an empty result.
- AI `processed_events`: added `document.deleted:1`; final counts were `uploaded:4`, `deleted:1`.
- Python AI logs showed `POST qdrant/points/delete HTTP/1.1 200`.

Bonus check:

- 15 orphan `Entity` nodes remained after delete.
- This is currently a design decision: entity nodes may be shared between documents. Phase 5/7 should decide between periodic cleanup and preservation.

## Bugs Fixed During UAT

### `d8e5190` - lifespan observability

- Added `logging.basicConfig(level=logging.INFO)` in `main.py`.
- Added `LIFESPAN` trace logs for each setup step.
- Added `/diagnostics` returning `{amqp_connection, amqp_runtime, qdrant_index, graph_index}`.
- This made silent AMQP consumer startup failures debuggable.

### `9d7842d` - ISO 8601 datetime format in AMQP events

- Fixed Python `json.dumps(default=str)` behavior that serialized datetimes as `2026-05-18 21:18:40.330005Z`.
- Java `jackson-datatype-jsr310` expects ISO 8601 with `T`, for example `2026-05-18T21:18:40.330005Z`.
- Added a custom serializer in `ai-service/src/corp_rag_ai/adapters/amqp/messages.py` for UTC datetime to `T/Z` ISO output and UUID to string.
- Covers `indexedAt` on success events and `failedAt` on failure events; `metadata.occurredAt` was already correct.
- Added regression coverage in `ai-service/tests/test_amqp_publisher.py` asserting `indexedAt` and `failedAt` contain no spaces and include ISO `T/Z`.
- Java DTO `DocumentIndexedConsumer.DocumentIndexedPayload` was not changed.
- Verification: all 9 targeted AMQP publisher/consumer tests passed.

## Deferred Bugs For Phase 5 Backlog

| ID | Item | Evidence | Phase 5 action |
|---|---|---|---|
| PH4-UAT-DEF-01 | Duplicate upload idempotency guard does not prevent full reprocessing. | Scenario 5 final state consistent, but Qdrant and DeepSeek calls re-ran for duplicate `eventId=2e01c126-191a-42a3-887f-f99646973c32`. | Wrap handlers with `IdempotentEventDispatcher` in `main.py` and add a regression proving duplicate event IDs do not call Qdrant, Neo4j, or OpenRouter. |
| PH4-UAT-DEF-02 | PDF parsing fails in current Docker setup. | Scenario 3 terminally failed `PARSING / INVALID_FILE_FORMAT`; OCR engines were missing (`rapidocr`, `easyocr`, `tesseract`). | Decide whether production Phase 5/8 needs PDF support; if yes, install/configure OCR engines or constrain supported source formats. |
| PH4-UAT-DEF-03 | Docling dependency surface needs audit. | `ai-service/pyproject.toml` directly lists only `docling>=2.93.0,<3.0.0`; `uv.lock` includes `docling-slim` transitively through `docling`. | Audit whether the lock composition is expected and whether slim/full extras match the desired PDF/OCR behavior. |
| PH4-UAT-DEF-04 | Python AI 4 GiB memory limit is tight. | bge-m3 embedding reached about 94% memory usage during UAT. | Raise `python-ai` `mem_limit` to 6 GiB if Phase 5 adds reranker/query runtime pressure. |
| PH4-UAT-DEF-05 | Neo4j orphan entities remain after document delete. | Scenario 6 left 15 orphan `Entity` nodes. | Decide whether Phase 5 retrieval should ignore orphan entities through document evidence filters, then defer cleanup to periodic Phase 7/8 maintenance if safe. |

## Topology And Config Reference

AMQP topology on `corp-rag.documents`:

| Queue | Routing key |
|---|---|
| `ai.document.uploaded` | `document.uploaded` |
| `ai.document.deleted` | `document.deleted` |
| `backend.document.indexed` | `document.indexed` |
| `backend.document.failed` | `document.indexing.failed` |

Important note: backend failed events use routing key `document.indexing.failed`, not `document.failed`.

Java `documents` columns observed during UAT:

`id`, `title`, `original_filename`, `mime_type`, `size_bytes`, `access_level`, `department`, `doc_type`, `language`, `status`, `owner_user_id`, `storage_bucket`, `storage_key`, `content_sha256`, `uploaded_at`, `indexed_at`, `chunk_count`, `failure_stage`, `failure_error_code`, `failure_message`, `failure_retryable`, `failure_retry_count`, `qdrant_collection`, `neo4j_entity_count`, `indexing_duration_ms`, `deleted_at`, `deleted_by`.

AI DB tables observed during UAT:

- `document_index_state(document_id, status, last_indexed_event_id, last_failure_stage, last_failure_code, last_failure_at, created_at, updated_at)`.
- `processed_events(event_id PK, event_type, consumed_at)`.
- `parent_chunks`.

## Summary

total: 9
passed: 8
issues: 5
pending: 0
skipped: 1
blocked: 0
