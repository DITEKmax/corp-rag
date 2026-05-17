# Phase 04 Research - Python Ingestion and Indexing

Date: 2026-05-17

This research validates the external API surfaces that materially affect Phase 04 planning. It is based on primary documentation and current repository state.

## A. HF Inference API and BGE-M3 Sparse Output

### Current API Summary

Hugging Face Inference Providers document the `feature-extraction` task as a dense embedding API: request payload supports `inputs`, `normalize`, `prompt_name`, `truncate`, and `truncation_direction`; response body is documented as an array of arrays. There is no documented `return_sparse`, `return_colbert_vecs`, `lexical_weights`, or equivalent sparse-output parameter in the hosted Inference Providers feature-extraction API.

BAAI/bge-m3 itself does support dense, sparse, and ColBERT modes. The model card documents 1024 dense dimensions, 8192 sequence length, and local `FlagEmbedding` usage with `model.encode(..., return_dense=True, return_sparse=True, return_colbert_vecs=False)`, returning `dense_vecs` and `lexical_weights`.

Therefore the Phase 04 assumption "HF Inference free tier returns dense+sparse for BAAI/bge-m3 in one payload" is not supported by the current official HF docs. Without a live custom endpoint, the safe conclusion is: HF Inference Providers can be used for dense embeddings, but not for BGE-M3 learned sparse vectors.

Primary sources:

- HF Inference Providers feature extraction docs: https://huggingface.co/docs/inference-providers/main/tasks/feature-extraction
- BAAI/bge-m3 model card: https://huggingface.co/BAAI/bge-m3
- HF Inference Endpoints overview: https://huggingface.co/docs/inference-endpoints/main/about
- FlagEmbedding PyPI: https://pypi.org/project/FlagEmbedding/

### Minimal Working Examples

Dense-only hosted call through Inference Providers:

```python
import os
from huggingface_hub import InferenceClient

client = InferenceClient(provider="hf-inference", api_key=os.environ["HF_API_TOKEN"])
dense = client.feature_extraction(
    ["short corporate policy text"],
    model="BAAI/bge-m3",
)

assert len(dense[0]) == 1024
```

Local dense+sparse call through FlagEmbedding:

```python
from FlagEmbedding import BGEM3FlagModel

model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)
output = model.encode(
    ["short corporate policy text"],
    batch_size=12,
    max_length=8192,
    return_dense=True,
    return_sparse=True,
    return_colbert_vecs=False,
)

dense_vec = output["dense_vecs"][0].tolist()
sparse_weights = output["lexical_weights"][0]  # dict[token_id, weight]
```

Qdrant sparse conversion stays the same:

```python
from qdrant_client.models import SparseVector

def to_qdrant_sparse(weights: dict[int | str, float]) -> SparseVector:
    items = sorted((int(k), float(v)) for k, v in weights.items())
    return SparseVector(
        indices=[idx for idx, _ in items],
        values=[value for _, value in items],
    )
```

### Alternatives if Hosted Sparse is Required

1. HF Inference Endpoints with a custom handler can expose `FlagEmbedding` output, but that is a paid/dedicated deployment path and is no longer "free tier HF Inference API".
2. Local FlagEmbedding for sparse + HF API for dense is technically possible, but it still requires loading BGE-M3 locally for sparse, adds cross-provider drift, and keeps the large dependency/image cost.
3. Full local FlagEmbedding is the most coherent open-source fallback: one model call gives deterministic dense+sparse outputs, no hosted sparse dependency, and matches BGE-M3's own documented API. Cost: large model download/cache, heavier Docker image or runtime model cache, slower CPU inference.
4. Alternative hosted providers need provider-specific proof that sparse output is returned. OpenAI-compatible embedding APIs generally return dense vectors only, so they do not satisfy the Phase 04 sparse contract without explicit sparse documentation.

### Risks and Gotchas

- This is a blocker for the current Phase 04 context. Planning should not assume HF free-tier sparse output.
- If Phase 04 keeps Qdrant named sparse vectors, embedding strategy must pivot before `PLAN.md`.
- If Phase 04 chooses full local FlagEmbedding, Docker, dependency, and UAT preflight decisions in `04-CONTEXT.md` must be updated.

### Version Constraints

If local fallback is chosen:

```toml
"FlagEmbedding>=1.4.0,<2.0.0"
```

If dense-only HF smoke is still retained:

```toml
"huggingface-hub>=0.31.0,<1.0.0"
```

## B. qdrant-client API for Hybrid Named Dense+Sparse Vectors

### Current API Summary

Qdrant supports multiple named dense vectors per point and sparse vectors as additional named vectors in one collection. Sparse vectors must be named, dense and sparse names must differ, and sparse vector distance is always `Dot`; it does not need to be configured.

The current Python shape is:

```python
from qdrant_client import AsyncQdrantClient, models

client = AsyncQdrantClient(url="http://qdrant:6333")

await client.create_collection(
    collection_name="documents_chunks",
    vectors_config={
        "dense": models.VectorParams(size=1024, distance=models.Distance.COSINE),
    },
    sparse_vectors_config={
        "sparse": models.SparseVectorParams(),
    },
)
```

Point upsert with named vectors:

```python
from qdrant_client import models

point = models.PointStruct(
    id=str(child_chunk_id),
    vector={
        "dense": dense_vec,
        "sparse": models.SparseVector(indices=sparse_indices, values=sparse_values),
    },
    payload={
        "chunkId": str(child_chunk_id),
        "parentChunkId": str(parent_chunk_id),
        "documentId": str(document_id),
        "sectionPath": section_path,
        "content": content,
    },
)

await client.upsert(collection_name="documents_chunks", points=[point])
```

Delete by documentId filter:

```python
await client.delete(
    collection_name="documents_chunks",
    points_selector=models.FilterSelector(
        filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="documentId",
                    match=models.MatchValue(value=str(document_id)),
                )
            ]
        )
    ),
)
```

Primary sources:

- Qdrant collections docs: https://qdrant.tech/documentation/manage-data/collections/
- Qdrant sparse vectors article: https://qdrant.tech/articles/sparse-vectors/
- Qdrant hybrid search with FastEmbed: https://qdrant.tech/documentation/tutorials-search-engineering/hybrid-search-fastembed/
- qdrant-client PyPI: https://pypi.org/project/qdrant-client/

### Risks and Gotchas

- The docs do not state that sparse indices must be sorted, but sorting before constructing `SparseVector` remains a cheap deterministic invariant and should stay in tests.
- Current compose uses `qdrant/qdrant:v1.12.6`. Named sparse vectors are supported in Qdrant 1.7+, so this is compatible with the target schema.
- Use `AsyncQdrantClient` in the FastAPI worker to avoid blocking the event loop.

### Version Constraints

PyPI latest observed: `qdrant-client 1.17.1` released 2026-03-13. Because compose currently pins Qdrant server `1.12.6`, prefer a conservative client range that supports the API without forcing server upgrade:

```toml
"qdrant-client>=1.12.2,<1.18.0"
```

## C. Gemini Structured Output via Google Gen AI SDK

### Current API Summary

The current official Python SDK is `google-genai`, not the legacy `google-generativeai` package. Google's docs show:

- `from google import genai`
- `client = genai.Client()`
- `client.models.generate_content(...)`
- structured output via `response_mime_type='application/json'` and `response_schema=...` in the Python SDK, or the newer REST/docs shape using `response_format`.

Gemini structured output supports JSON Schema/Pydantic models, but the docs also note model-specific behavior: Gemini 2.0 Flash supports structured outputs, with a note that Gemini 2.0 requires explicit `propertyOrdering` in JSON input when using raw JSON schema. The Python SDK Pydantic path is the cleanest implementation path.

Primary sources:

- Gemini structured output docs: https://ai.google.dev/gemini-api/docs/structured-output
- Google Gen AI Python SDK docs: https://googleapis.github.io/python-genai/
- Gemini rate limits docs: https://ai.google.dev/gemini-api/docs/rate-limits
- google-genai PyPI: https://pypi.org/project/google-genai/

### Minimal Working Example

```python
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

ENTITY_TYPES = (
    "person",
    "department",
    "policy",
    "system",
    "procedure",
    "role",
    "date",
    "concept",
)

class ExtractedEntity(BaseModel):
    name: str = Field(description="Display name from the source text.")
    type: Literal[
        "person", "department", "policy", "system",
        "procedure", "role", "date", "concept",
    ]
    description: str

class ExtractedRelation(BaseModel):
    sourceEntityName: str
    targetEntityName: str
    type: str = Field(description="UPPER_SNAKE_CASE relation predicate.")
    description: str

class ExtractionResult(BaseModel):
    entities: list[ExtractedEntity]
    relations: list[ExtractedRelation]

client = genai.Client()
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="Extract entities and relations from: ...",
    config=types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=2000,
        response_mime_type="application/json",
        response_schema=ExtractionResult,
    ),
)

result = ExtractionResult.model_validate_json(response.text)
```

### Malformed JSON Handling

Even with structured output, implementation should parse through Pydantic and treat `ValidationError` or JSON decode failure as semantic malformed output. The locked Phase 04 behavior remains: one local retry, then `ENTITY_EXTRACTION / INDEXING_PIPELINE_ERROR / retryable=false`.

### Rate Limits

Current official rate-limit docs no longer publish a stable static RPM/TPM/RPD table for standard calls. They state that limits are measured by RPM, TPM, and RPD, applied per project, and active model limits must be viewed in AI Studio. Therefore the plan should not hardcode public numeric Gemini 2.0 Flash quotas. UAT preflight must perform a real structured-output smoke call with the configured `GEMINI_API_KEY`.

### Risks and Gotchas

- `google-generativeai` from older examples should not be added. Use `google-genai`.
- If code uses raw JSON schema for Gemini 2.0 Flash, include explicit property ordering. Pydantic through the SDK is simpler and should be preferred.
- Gemini 2.0 Flash is supported for structured output, but access and quota must be validated in UAT preflight.

### Version Constraints

PyPI latest observed: `google-genai 2.0.0` released 2026-05-07.

```toml
"google-genai>=2.0.0,<3.0.0"
```

## D. Neo4j Python Driver Async and Vector Index

### Current API Summary

Neo4j vector indexes are available in both Enterprise and Community Edition. Community Edition can index embeddings stored as `LIST<INTEGER | FLOAT>` properties. Native `VECTOR` properties require Enterprise/Aura block format, so Phase 04 should store entity embeddings as Python `list[float]`, not native `VECTOR`.

The current compose uses `neo4j:5.26.25-community`, which is compatible with vector indexes over list properties.

Vector index syntax for Phase 04:

```cypher
CREATE VECTOR INDEX entity_embedding_idx IF NOT EXISTS
FOR (e:Entity)
ON e.embedding
OPTIONS { indexConfig: {
  `vector.dimensions`: 1024,
  `vector.similarity_function`: 'cosine'
}}
```

Query syntax compatible with Neo4j 5.x:

```cypher
CALL db.index.vector.queryNodes('entity_embedding_idx', $limit, $queryEmbedding)
YIELD node AS entity, score
RETURN entity, score
```

Async driver pattern:

```python
from neo4j import AsyncGraphDatabase

driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

async def write_graph(tx, params):
    await tx.run(
        """
        MERGE (d:Document {id: $document_id})
        SET d.title = $title,
            d.accessLevel = $access_level
        """,
        **params,
    )

async with driver.session(database="neo4j") as session:
    await session.execute_write(write_graph, params)
```

Primary sources:

- Neo4j vector indexes docs: https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/
- Neo4j Python async docs: https://neo4j.com/docs/python-manual/current/concurrency/
- Neo4j async API docs: https://neo4j.com/docs/api/python-driver/current/async_api.html
- neo4j PyPI: https://pypi.org/project/neo4j/

### Risks and Gotchas

- Do not use native `VECTOR` property types on Community Edition. Store `embedding` as `LIST<FLOAT>`.
- Neo4j creates vector indexes in the background. Startup `ensure_graph_schema()` should run `SHOW VECTOR INDEXES` or tolerate `POPULATING`; UAT should query after service readiness or after the index reaches `ONLINE`.
- The Python driver may retry transaction functions on transient server errors. Keep write callbacks idempotent and avoid hidden external side effects inside `execute_write`.

### Version Constraints

PyPI current driver is 6.2.0, but latest 5.x is 5.28.4 and is the conservative match for a Neo4j 5.26 LTS server.

```toml
"neo4j>=5.28.4,<6.0.0"
```

## E. Docling API for PDF/DOCX Parsing

### Current API Summary

Docling's primary entry point is `DocumentConverter`. `convert(source)` returns `ConversionResult`, whose `.document` is a `DoclingDocument`. `DoclingDocument` can export to Markdown, HTML, JSON/dict, DocTags, and tables can be exported to pandas DataFrames.

For Phase 04, the safest implementation path is:

1. Use Docling for PDF/DOCX conversion.
2. Prefer structured `DoclingDocument` items when practical for text/table/page metadata.
3. If item-level labels/page metadata prove too unstable during implementation, use `export_to_markdown()` and run the already locked Markdown block normalizer as fallback.

Primary sources:

- Docling DocumentConverter API: https://docling-project.github.io/docling/reference/document_converter/
- Docling DoclingDocument API: https://docling-project.github.io/docling/reference/docling_document/
- Docling table export example: https://docling-project.github.io/docling/examples/export_tables/
- Docling supported formats: https://docling-project.github.io/docling/usage/supported_formats/
- docling PyPI: https://pypi.org/project/docling/

### Minimal Working Example

```python
from pathlib import Path

from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert(Path("document.pdf"))
doc = result.document

markdown = doc.export_to_markdown()

for table_ix, table in enumerate(doc.tables):
    table_df = table.export_to_dataframe(doc=doc)
    table_markdown = table_df.to_markdown(index=False)
```

### Structured Block Extraction Notes

Docling exposes a rich `DoclingDocument` object with `texts`, `tables`, `pictures`, `pages`, and body traversal/export APIs. The docs clearly support table extraction and whole-document Markdown serialization. They do not provide a concise single example for "ordered text blocks with heading level, paragraph/list/table type, and page number" in one stable call. Implementation should include a spike/test fixture before locking the final adapter internals.

If direct structured traversal is too costly, fallback to Docling Markdown export plus Markdown parser is acceptable and does not violate the locked downstream `ParsedDocument` shape. It does reduce direct PDF page fidelity unless page annotations can be recovered from Docling metadata.

### Failure Behavior

Docling `DocumentConverter.convert(..., raises_on_error=True)` raises conversion errors for failed conversion. Phase 04 should catch broad Docling conversion exceptions at the parser adapter boundary and map them to `PARSING / INVALID_FILE_FORMAT / retryable=false`, preserving the locked sanitized `StageFailure` error messages.

### Install Size

Docling is a heavy dependency compared with the current AI service foundation. It has OCR/VLM-capable pipelines and model-related transitive dependencies. Phase 04 has already deferred OCR; implementation should configure Docling without optional OCR/VLM extras unless required by base install. Docker build time and image size should be checked in Wave 1 or parser wave.

### Version Constraints

PyPI latest observed: `docling 2.93.0` released 2026-05-07.

```toml
"docling>=2.93.0,<3.0.0"
```

## F. aio-pika Consumer Pattern with Manual ACK

### Current API Summary

aio-pika is an async RabbitMQ client built on aiormq. It supports robust auto-reconnect via `connect_robust`, channel QoS/prefetch, `Queue.consume()`, `IncomingMessage.ack()`, `nack()`, `reject()`, and `message.process()` context management.

For Phase 04 terminal-after-outcome idempotency, prefer explicit manual ACK rather than `message.process()` because ACK timing must occur after:

1. terminal external outcome,
2. terminal state update,
3. `processed_events` insert,
4. DB commit.

Minimal consumer skeleton:

```python
import aio_pika

async def start_consumer(settings, handler):
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)

    queue = await channel.declare_queue(
        "ai.document.uploaded",
        durable=True,
        passive=True,
    )

    async def on_message(message: aio_pika.IncomingMessage) -> None:
        try:
            await handler(message.body, message.headers)
        except Exception:
            # Internal infrastructure failure before terminal outcome.
            # Requeue/DLQ policy depends on broker topology.
            await message.nack(requeue=True)
            raise
        else:
            await message.ack()

    await queue.consume(on_message, no_ack=False)
```

Primary sources:

- aio-pika docs: https://docs.aio-pika.com/
- aio-pika quick start: https://docs.aio-pika.com/quick-start.html
- aio-pika work queues tutorial: https://docs.aio-pika.com/rabbitmq-tutorial/2-work-queues.html
- aio-pika API reference: https://docs.aio-pika.com/apidoc.html
- aio-pika PyPI: https://pypi.org/project/aio-pika/

### Risks and Gotchas

- `message.process()` auto-acks on context success, which can obscure the explicit terminal insert/publish/ACK ordering. Use manual `ack()` for clarity.
- `prefetch_count=1` belongs on the channel before consuming.
- Use `passive=True` for queues declared by Java topology so Python fails fast if topology is missing.
- For exceptions before terminal failed-event publication, `nack(requeue=True)` is correct for transient internal infra failures. If Java configured DLX/dead-letter behavior via queue arguments, broker redelivery/DLQ policy will apply after its configured limits; Python should not invent a second retry counter.

### Version Constraints

PyPI latest observed: `aio-pika 9.6.2` released 2026-03-22.

```toml
"aio-pika>=9.6.2,<10.0.0"
```

## Additional Dependency Constraints

These were not core research topics, but they are needed by locked Phase 04 decisions:

```toml
"httpx>=0.28.0,<1.0.0"
"tiktoken>=0.13.0,<1.0.0"
"markdown-it-py>=4.2.0,<5.0.0"
"trafilatura>=2.0.0,<3.0.0"
```

Current AI service already has:

```toml
"fastapi>=0.115.0,<1.0.0"
"pydantic>=2.10.0,<3.0.0"
"sqlalchemy[asyncio]>=2.0.36,<3.0.0"
"asyncpg>=0.30.0,<1.0.0"
```

## Blockers Requiring Discussion Before PLAN.md

### BLOCKER-1: HF Inference Providers do not document BGE-M3 sparse output

Impact:

- Current `04-CONTEXT.md` assumes HF Inference API can produce both dense and sparse BGE-M3 vectors.
- Official HF feature-extraction docs only document dense `array[]` output.
- Official BGE-M3 sparse output path is local `FlagEmbedding`.
- Phase 04 Qdrant schema requires learned sparse vectors.

Decision needed before planning:

1. Pivot to full local `FlagEmbedding` for dense+sparse embeddings in Phase 04.
2. Keep HF dense and use local FlagEmbedding only for sparse, accepting duplicated model/provider complexity.
3. Use paid/custom HF Inference Endpoint exposing FlagEmbedding output.
4. Change retrieval MVP to dense-only Qdrant for Phase 04 and defer sparse to Phase 7, which would contradict the current dense+sparse contract and ADR-002 expectations.

Research recommendation:

- Prefer option 1 if the MVP must keep dense+sparse Qdrant in Phase 04.
- This updates Docker/dependency assumptions but keeps retrieval semantics coherent and deterministic.

### BLOCKER-2: Gemini 2.0 Flash rate limits are no longer static in public docs

Impact:

- Exact public RPM/TPM/RPD values should not be hardcoded in the plan.
- UAT must include live Gemini structured-output preflight with the configured project/API key.

Decision needed:

- No architecture pivot needed. Keep sequential parent extraction and backoff. Document that quotas are validated by UAT preflight, not by static docs.

## Non-Blocking Plan Updates

1. Replace `google-generativeai` wording with `google-genai` in implementation plans.
2. Store Neo4j entity embeddings as `LIST<FLOAT>`, not native `VECTOR`, because compose uses Community Edition.
3. Add a parser-wave spike/test for Docling structured traversal. If unstable, use Docling Markdown export plus Markdown normalizer fallback.
4. Use manual aio-pika ACK rather than `message.process()` for the terminal-after-outcome contract.
