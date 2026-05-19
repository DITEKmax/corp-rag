# Phase 04 to Phase 05 Handoff

**Created:** 2026-05-19
**From:** Phase 04 - Python Ingestion & Indexing
**To:** Phase 05 - Retrieval, Guards & Query API
**Status:** Phase 04 passed end-to-end UAT. Phase 05 is ready for discussion and planning.

## Phase 4 Outcome

Phase 4 delivered the Python ingestion and indexing pipeline:

- Python consumes `document.uploaded` and `document.deleted` from RabbitMQ.
- Python fetches Java-owned document objects from MinIO.
- Supported documents are parsed into normalized blocks and deterministic parent/child chunks.
- Child chunks are sanitized, embedded with local `BAAI/bge-m3`, and upserted into Qdrant with dense 1024 + sparse vectors.
- Parent chunks are stored in AI Postgres for Phase 5 parent resolution.
- DeepSeek V4 Flash through OpenRouter extracts entities/relations.
- Neo4j stores provenance-first `Document`, `Entity`, and relation evidence data.
- Python publishes `document.indexed` or `document.indexing.failed` back to Java.
- Delete events clean Qdrant, Neo4j `Document` nodes, parent chunks, and AI index state.

Manual UAT passed on 2026-05-19. Evidence is in `04-UAT-EVIDENCE.md`.

## Artifacts Phase 5 Depends On

- `ai-service/src/corp_rag_ai/pipeline/indexing/embedding.py` - local bge-m3 embedding adapter.
- `ai-service/src/corp_rag_ai/pipeline/indexing/vector_indexer.py` - Qdrant collection schema, payload shape, and delete/replace behavior.
- `ai-service/src/corp_rag_ai/pipeline/indexing/graph_indexer.py` - Neo4j schema and document graph writes.
- `ai-service/src/corp_rag_ai/pipeline/indexing/entity_extractor.py` - DeepSeek/OpenRouter structured extraction client and schema handling.
- `ai-service/src/corp_rag_ai/pipeline/ingestion/orchestrator.py` - upload/delete pipeline ordering, terminal state, and rollback behavior.
- `ai-service/src/corp_rag_ai/repositories/ingestion_state.py` - `document_index_state`, `processed_events`, and parent chunk repositories.
- `contracts/asyncapi/events-v1.yaml` and `contracts/constants.yaml` - event and routing source of truth.
- `.planning/phases/04-python-ingestion-indexing/04-UAT-EVIDENCE.md` - actual UAT evidence and known follow-ups.

## Current Runtime Topology

AMQP exchange: `corp-rag.documents`.

| Queue | Routing key |
|---|---|
| `ai.document.uploaded` | `document.uploaded` |
| `ai.document.deleted` | `document.deleted` |
| `backend.document.indexed` | `document.indexed` |
| `backend.document.failed` | `document.indexing.failed` |

Important compose env defaults are now wired for `python-ai`:

```text
AI_AMQP_CONSUMERS_ENABLED=${AI_AMQP_CONSUMERS_ENABLED:-true}
AI_QDRANT_INITIALIZE_COLLECTION=${AI_QDRANT_INITIALIZE_COLLECTION:-true}
AI_NEO4J_INITIALIZE_SCHEMA=${AI_NEO4J_INITIALIZE_SCHEMA:-true}
```

## How To Start The Stack

From repo root:

```powershell
if (!(Test-Path infra/.env)) { Copy-Item infra/.env.example infra/.env }
```

Set at least these values in `infra/.env`:

```text
OPENROUTER_API_KEY=<openrouter-key>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DEEPSEEK_MODEL_ID=deepseek/deepseek-v4-flash:free
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=<strong-local-password>
```

Then run:

```powershell
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
Invoke-RestMethod http://localhost:8000/diagnostics
Invoke-RestMethod http://localhost:8080/actuator/health
```

Expected `/diagnostics` result after healthy startup:

```json
{
  "amqp_connection": true,
  "amqp_runtime": true,
  "qdrant_index": true,
  "graph_index": true
}
```

## Phase 5 Work To Plan

Phase 5 should deliver retrieval, guards, and query API behavior:

- Query embedding with the same bge-m3 adapter.
- Qdrant hybrid dense+sparse search with metadata/access filters.
- Neo4j graph traversal constrained by document evidence and access filters.
- Parent chunk resolution from AI Postgres by `parentChunkId`.
- Reranking or compacting retrieved evidence for generation.
- Query router for factual, aggregation, multi-hop, comparison, and unsupported queries.
- Input guard and output guard using Phase 4 sanitizer patterns where useful.
- DeepSeek/OpenRouter answer generation with cited structured output.
- Java-to-Python query API integration that accepts Java-resolved access filters.

Because Scenario 6 deleted the TechCorp happy-path document, Phase 5 should upload or seed a fresh indexed corpus before retrieval work.

## Known Issues Entering Phase 5

| ID | Issue | Guidance |
|---|---|---|
| PH4-UAT-DEF-01 | Duplicate `document.uploaded` events still re-run the pipeline even though final state is consistent. | Fix early in Phase 5 or before load testing. Wrap handlers with `IdempotentEventDispatcher` in `main.py` and add a regression proving Qdrant/Neo4j/OpenRouter are not called for already processed event IDs. |
| PH4-UAT-DEF-02 | PDF parsing fails in the current Docker setup without OCR engines. | Decide whether Phase 5 demo corpus uses Markdown/plain text only or whether PDF support must be hardened now. |
| PH4-UAT-DEF-03 | Docling dependency surface should be audited. | `pyproject.toml` directly depends on `docling`; `uv.lock` includes `docling-slim` transitively. Verify this is the intended dependency shape for OCR/PDF support. |
| PH4-UAT-DEF-04 | `python-ai` 4 GiB memory limit is tight. | Bump to 6 GiB if Phase 5 adds local reranking or concurrent query pressure. |
| PH4-UAT-DEF-05 | Orphan Neo4j `Entity` nodes remain after delete. | Retrieval must only return graph evidence connected to accessible `Document` nodes; cleanup can remain a later maintenance task if filters are strict. |

## Recommended Next GSD Command

Phase 5 has `Plans: TBD` in `ROADMAP.md`, so the next workflow should clarify and plan the phase before implementation:

```text
$gsd-discuss-phase 5
```

After the Phase 5 context is clarified, run:

```text
$gsd-plan-phase 5
```

Do not start Phase 5 execution until the plan exists and maps RET-01, RET-02, RET-03, RET-04, AGT-01, AGT-02, AGT-03, and SEC-01.

## Stop Point

Project is ready for Phase 5 discussion/planning. Phase 4 implementation and UAT closeout are complete.
