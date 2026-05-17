# Phase 4: Python Ingestion & Indexing - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 delivers the Python ingestion pipeline for Java-owned uploaded documents. Python consumes `document.uploaded` and `document.deleted` events, fetches source files from MinIO, parses supported formats into a normalized representation, creates deterministic parent/child chunks, sanitizes child chunks, embeds and upserts child chunks into Qdrant, extracts graph entities/relations into Neo4j, and publishes terminal `document.indexed` or `document.indexing.failed` events back to Java.

This phase does not implement query retrieval, answer generation, frontend screens, manual reindex endpoints, Qdrant/Neo4j backups, OCR for scanned PDFs, graph community summaries, or Java retry/admin recovery workflows.

</domain>

<decisions>
## Implementation Decisions

### Docker, Contracts, And First Wave Preflight
- **D-01:** `python-ai` Docker builds must use repository-root build context with `dockerfile: ai-service/Dockerfile`, mirroring the Java backend root-context codegen pattern.
- **D-02:** `ai-service/Dockerfile` becomes multi-stage. Builder stage uses `ghcr.io/astral-sh/uv:0.5.26-python3.12-bookworm`, `WORKDIR /repo`, and copies `contracts/`, `scripts/`, and `ai-service/` into the same repo-root layout expected by current generator scripts.
- **D-03:** Do not modify `scripts/generate_python_contracts.py` or `scripts/generate_constants.py` in the codegen wave. They already serve shared Java/Python contract generation and script changes risk Java regressions.
- **D-04:** Builder stage installs PyYAML only as build tooling, runs `python /repo/scripts/generate_python_contracts.py` and `python /repo/scripts/generate_constants.py`, and writes generated Python artifacts to `/repo/ai-service/src/corp_rag_ai/contracts/generated/`.
- **D-05:** Runtime stage copies generated `/repo/ai-service/src` into `/app/src`; PyYAML must not be added to runtime dependencies or the final image.
- **D-06:** Root `.dockerignore` must exclude `.git`, `.planning/`, `backend/target/`, `**/__pycache__`, `**/.pytest_cache`, `ai-service/.venv`, `frontend/node_modules`, and `ai-service/src/corp_rag_ai/contracts/generated/`.
- **D-07:** Builder stage must explicitly `rm -rf /repo/ai-service/src/corp_rag_ai/contracts/generated` immediately before codegen. This prevents stale local generated files, including files no longer produced by generators, from entering the runtime image.
- **D-08:** Local dev and Docker codegen both write to `ai-service/src/corp_rag_ai/contracts/generated/`; local verification still runs through the existing `verify-contracts` path.
- **D-09:** `ai-service/README.md` must state that local dev runs codegen through `make`/`verify-contracts`, while Docker builds run the same generation inside the builder stage.
- **D-10:** Wave 1 smoke must prove `docker compose build python-ai` works after deleting generated files locally, `zombie.py` stale-file scenario does not enter the final image, final image lacks PyYAML, and `/health` plus `/ready` still respond.

### Event Intake, Idempotency, And State
- **D-11:** Consume the accumulated Phase 3 UAT RabbitMQ messages on first Phase 4 startup. Do not clear queues by default; the existing `2 uploaded + 1 deleted` messages are a free end-to-end smoke test.
- **D-12:** Python owns an AI Postgres `processed_events` table with only `event_id UUID PRIMARY KEY`, `event_type VARCHAR(64) NOT NULL`, and `consumed_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
- **D-13:** Python owns a `document_index_state` table with `document_id UUID PRIMARY KEY`, `status VARCHAR(32) NOT NULL` enum-like values `PENDING | INDEXING | INDEXED | FAILED | DELETED`, nullable `last_indexed_event_id`, nullable `last_failure_stage`, nullable `last_failure_code`, nullable `last_failure_at`, plus `created_at` and `updated_at`.
- **D-14:** Do not duplicate Java document metadata such as title, owner, content SHA, access level, department, doc type, language, MIME, size, original filename, or upload time in `document_index_state`. Those fields live in Java Postgres and Qdrant payload.
- **D-15:** `processed_events` means terminal outcome, not "handler started." Insert it only after indexed event published, failed event published, delete cleanup completed, or delete-before-upload skipped.
- **D-16:** First handler step is `SELECT 1 FROM processed_events WHERE event_id = ?`. If found, ACK and exit without side effects.
- **D-17:** Upload handler sets `document_index_state.status=INDEXING` before external work. If the process crashes before terminal completion, RabbitMQ redelivery sees no `processed_events` row and safely retries.
- **D-18:** If crash happens after terminal `processed_events` insert but before ACK, redelivery sees duplicate and ACKs. This is safe because terminal outcome already happened.
- **D-19:** If crash happens between result AMQP publish and terminal `processed_events` insert, redelivery may publish a duplicate result. Java result consumers are already idempotent through their own `processed_events` table.
- **D-20:** Delete handler always UPSERTs `document_index_state.status=DELETED`, creating a tombstone row even if no previous upload state exists.
- **D-21:** Upload handler checks for `status=DELETED` at the start. If found, silently skip indexing, insert `processed_events`, and ACK. Do not publish `document.indexing.failed` for delete-before-upload.
- **D-22:** Delete cleanup is inline in delete handler: Qdrant delete-by-filter `documentId`, Neo4j `MATCH (d:Document {id: $documentId}) DETACH DELETE d`, Postgres `DELETE FROM document_chunks_parent WHERE document_id = ?`, then `document_index_state.status=DELETED` and terminal `processed_events`.
- **D-23:** Do not delete MinIO objects in Phase 4; Java owns source object lifecycle.
- **D-24:** Python result outbox and publisher confirms are deferred to Phase 7+ unless real failures show the MVP gap is unacceptable.

### Parsing And Normalized Document Model
- **D-25:** Use a sectioned block model before chunking, not flat text or parser-native layout trees.
- **D-26:** Parser dispatch by MIME is locked: PDF and DOCX use docling; HTML uses trafilatura; Markdown uses `markdown-it-py` or mistune; plain text uses a trivial plain-text parser.
- **D-27:** Domain model `ParsedBlock` has `type: Literal["heading", "paragraph", "list_item", "table", "preformatted"]`, `text`, optional `level`, integer 0-based `position`, optional `page`, and `section_path: list[str]`.
- **D-28:** Domain model `ParsedDocument` has `document_id`, `language` from event payload, `blocks`, and `parse_warnings`.
- **D-29:** No format-specific fields such as PDF metadata, DOCX styles, fonts, colors, image references, or inline links are kept in `ParsedBlock`.
- **D-30:** `section_path` is computed once during normalization. Heading level `N` truncates the current path to `N-1` and appends the heading text; non-heading blocks inherit current path.
- **D-31:** Tables are atomic `type="table"` blocks whose `text` is Markdown table serialization. The chunker must not split a table block.
- **D-32:** Consecutive `list_item` blocks may be grouped as paragraph-like content by the chunker; each bullet does not need a separate child chunk.
- **D-33:** `parse_warnings` records parser simplifications such as merged table cells, skipped embedded objects, or password-protected regions. Warnings do not block indexing unless later sanitizer thresholds fail.
- **D-34:** Page semantics: PDF uses real docling page number; DOCX uses page if docling provides it, otherwise `None`; HTML/Markdown/plain text use `None`.
- **D-35:** One parser protocol is used: `async def parse(content: bytes, mime_type: str, language: str) -> ParsedDocument`.
- **D-36:** OCR for scanned PDFs is deferred to Phase 7+. If docling returns no extractable content, fail with `PARSING / INVALID_FILE_FORMAT`.
- **D-37:** Python trusts Java-provided `mimeType` and `language`; do not re-sniff MIME or detect language in Phase 4.
- **D-141:** Parser execution starts with a 2-4 hour Docling spike on a representative PDF. Primary path is structured `DoclingDocument` traversal into `ParsedBlock`s. If structured traversal is unstable or too costly, fallback path is `docling.export_to_markdown()` followed by the same `markdown-it-py` Markdown normalizer used for `text/markdown`.

### Deterministic Parent And Child Chunking
- **D-38:** Use deterministic structural+size parent-child chunking. This intentionally overrides `ARCHITECTURE.md`'s original SemanticSplitterNodeParser idea; semantic splitting is deferred to Phase 7+ ablation.
- **D-39:** Child chunks target 350 tokens, hard max 500 tokens, with 50-token overlap. Child chunks are Qdrant retrieval units.
- **D-40:** Parent chunks target 1500 tokens, hard max 2000 tokens, with zero overlap. Parent chunks are context units, not retrieval units.
- **D-41:** Token counting uses `tiktoken` `cl100k_base` everywhere in the chunker. It is a heuristic and does not need to match bge-m3 native tokenizer exactly.
- **D-42:** Parent grouping walks `ParsedBlock`s in order, groups by `section_path`, switches parent when section path changes or hard max would be exceeded, and treats tables as indivisible.
- **D-43:** If a single table exceeds parent hard max, the table becomes a single-block parent and emits a warning. It is still not split.
- **D-44:** Parent content is split into children with a sliding window near 350 tokens, up to hard max 500, preferring sentence/paragraph boundaries, and falling back to hard token cuts.
- **D-45:** Sentence splitting uses regex plus hardcoded Russian/English abbreviation guards. No `pysbd`, `nltk`, spaCy, or ML boundary detection in Phase 4.
- **D-46:** Boundary preference is paragraph break, then strong sentence terminator, then period, then newline, then hard token cap.
- **D-47:** Overlap never crosses a parent boundary. The first child in a parent has zero overlap.
- **D-48:** `parent_chunk_id` is deterministic UUID v5 with namespace `document_id` and name `parent:{position}`.
- **D-49:** `chunk_id` is deterministic UUID v5 with namespace `parent_chunk_id` and name `child:{position_in_parent}`.
- **D-50:** Parent chunks are stored in AI Postgres table `document_chunks_parent` with `parent_chunk_id`, `document_id`, `section_path TEXT[]`, `content TEXT`, `position`, `token_count`, `created_at`, and index on `document_id`.
- **D-51:** Parent chunks are not embedded in MVP. Phase 5 parent resolver fetches parent content from AI Postgres by `parentChunkId`.
- **D-52:** Qdrant stores one point per child chunk only.

### Chunk Text Serialization
- **D-53:** Each child chunk has two text forms: `content_for_embedding` used only during embedding, and `content` stored in Qdrant payload for display/citation/answer context.
- **D-54:** `content_for_embedding` contains breadcrumb plus body. `content` contains body only.
- **D-55:** Breadcrumb format is `[document title] › [section path joined by " › "]\n\n[body]`. The title comes from the upload event. If `section_path` is empty, breadcrumb is just title.
- **D-56:** Use U+203A `›` as breadcrumb separator because `/` appears in URLs, paths, and `and/or` text and can hurt sparse matching.
- **D-57:** Body serialization: headings as plain text, paragraphs as plain text separated by blank lines, list items prefixed with `• ` and adjacent items separated by newlines, preformatted blocks without code fences, and table blocks as Markdown table text.
- **D-58:** Parent `document_chunks_parent.content` stores the full parent body without breadcrumb. Display breadcrumb can be reconstructed from title and `section_path`.
- **D-59:** Do not store `content_for_embedding` in Qdrant payload or Postgres after indexing.
- **D-60:** Same `ParsedDocument` must produce byte-equal chunk text and deterministic UUIDs across retries.

### Qdrant Collection, Payload, And Embedding
- **D-61:** Qdrant collection is `documents_chunks`.
- **D-62:** Use named dense and sparse vectors: `dense` and `sparse`. These are Python-internal constants, not shared contract constants.
- **D-63:** Collection schema: dense vector size 1024 with cosine distance, plus sparse vector config for learned bge-m3 sparse vectors.
- **D-64:** Qdrant point ID is the deterministic child chunk UUID string.
- **D-65:** Qdrant payload fields are `chunkId`, `parentChunkId`, `documentId`, `documentTitle`, `sectionPath` array, `position` global child position, nullable `page`, display `content`, `language`, `docType`, `department`, `accessLevel`, `isSanitized`, and `sanitizerFlags`.
- **D-66:** Payload indexes are created for `documentId`, `language`, `docType`, `department`, and `accessLevel`. Do not index `parentChunkId` or `isSanitized` in MVP.
- **D-67:** Startup hook `ensure_collection_exists()` is controlled by `AI_QDRANT_INITIALIZE_COLLECTION`, default false for tests, true in compose.
- **D-68:** Existing collection with matching schema is no-op. Existing collection with incompatible schema logs error and raises. Do not auto-drop or recreate Qdrant data.
- **D-69:** Use local `FlagEmbedding` for bge-m3 embeddings in MVP. `BAAI/bge-m3` is loaded inside the Python AI service and produces both dense 1024 vectors and learned sparse lexical weights from one local model path.
- **D-70:** Add `FlagEmbedding` as the embedding dependency. Research found current stable `FlagEmbedding>=1.4.0,<2.0.0`; execution may only relax to `>=1.3.0,<2.0.0` if 1.4.x has a compatibility issue that is documented in the plan/execution notes.
- **D-71:** Embedding batch size remains 32 chunk texts, but it is an in-process `BGEM3FlagModel.encode(...)` batch, not an external HF API call. Keep one document in flight through AMQP prefetch 1.
- **D-72:** The model runs on CPU for MVP. Prefer `use_fp16=True` as the first smoke path for speed, but the embedding adapter must fall back to `use_fp16=False` if CPU/PyTorch fp16 fails or is materially slower in smoke verification.
- **D-142:** Do not use HF Inference free tier, DeepInfra, NVIDIA NIM, or HF Inference Endpoints for Phase 4 embeddings. Hosted sparse alternatives are paid or provider-specific and violate ADR-001's free-tier MVP constraint.
- **D-143:** Do not split dense and sparse generation across two providers. Hybrid `dense HF + sparse local` adds two code paths without MVP benefit.
- **D-144:** Do not self-host a separate text-embeddings-inference container in Phase 4. It is deferred to Phase 7+ if local CPU inference becomes a real bottleneck.
- **D-145:** Compose must provide a named `bge-m3-cache` Docker volume mounted at `/root/.cache/huggingface` for `python-ai`. This caches model weights across container restarts/recreates. Build planning should not assume this named volume is a Docker build cache; dependency layers and model cache are separate concerns.
- **D-146:** Expected local embedding footprint is heavy: PyTorch/transformers dependencies plus ~2.3GB model cache, with overall Docker disk usage around 5-6GB. Python AI runtime should reserve at least 3GB RAM for bge-m3 load/inference; compose should set an explicit 4GB `python-ai` memory limit to leave headroom for Phase 5 reranker work.
- **D-148:** Phase 5 is expected to use `bge-reranker-v2-m3` locally through `FlagEmbedding`/`FlagReranker`, but Phase 4 does not download the reranker model or implement reranking. Phase 4 only adds the shared `FlagEmbedding` package needed for bge-m3 embeddings.
- **D-73:** Convert bge sparse dictionary to Qdrant `SparseVector` by int-casting token IDs, float-casting weights, sorting by index, and building `indices`/`values`. Unit test this conversion.
- **D-74:** Before indexing/upserting a document, delete existing Qdrant points by `documentId`. This makes retry/reindex replace-all semantics safe.
- **D-75:** On `document.deleted`, use Qdrant delete-by-filter on `documentId`. Do not recompute point IDs.

### Neo4j Provenance-First Graph
- **D-76:** Use a provenance-first Neo4j schema. This intentionally overrides `ARCHITECTURE.md` section 9.3 direct edge graph. `04-CONTEXT.md` is the current contract; `ARCHITECTURE.md` remains historical reference.
- **D-77:** Do not create `Chunk` nodes in Neo4j for MVP. Qdrant is source of truth for child chunk payload/content; AI Postgres is source of truth for parent content.
- **D-78:** Neo4j nodes are `Document`, `Entity`, and `RelationMention`.
- **D-79:** `Document` node properties: `id`, `title`, `accessLevel`, `department`, `docType`, and `language`.
- **D-80:** `Entity` properties: deterministic `id`, `name`, `normalizedName`, `type`, `description`, and dense `embedding` vector.
- **D-81:** Entity type whitelist is `person`, `department`, `policy`, `system`, `procedure`, `role`, `date`, `concept`.
- **D-82:** `RelationMention` properties: deterministic `id`, `type`, and `description`.
- **D-83:** Edges are `(:Entity)-[:MENTIONED_IN {chunkId, parentChunkId, sectionPath}]->(:Document)`, `(:RelationMention)-[:SOURCE]->(:Entity)`, `(:RelationMention)-[:TARGET]->(:Entity)`, and `(:RelationMention)-[:EVIDENCE {chunkId, parentChunkId}]->(:Document)`.
- **D-84:** Neo4j indexes include entity normalized name, entity type, entity vector index with 1024 cosine, document id, document access level, and relation type.
- **D-85:** Entity ID is UUID v5 over fixed namespace and name `normalizedName:type`. Normalization is lowercase, trimmed, and whitespace-collapsed; do not attempt cross-language aliases in MVP.
- **D-86:** Entity `description` is set on first create and not overwritten on later matches to avoid drift.
- **D-87:** RelationMention ID is UUID v5 using source entity ID as namespace and name `targetEntityId:type`. One `(source, target, type)` relation globally maps to one RelationMention node; new evidence creates additional `EVIDENCE` edges.
- **D-88:** Phase 5 graph access filtering will filter through `Document` on `EVIDENCE`/`MENTIONED_IN` edges using access level, department, and doc type.
- **D-89:** Delete cleanup is only `MATCH (d:Document {id: $documentId}) DETACH DELETE d`. Do not delete matched `Entity` or `RelationMention` nodes during document cleanup.
- **D-90:** Orphan RelationMention cleanup, reference-counted entity cleanup, cross-language alias resolution, and community summaries are deferred to Phase 7+.

### Graph Extraction Execution
- **D-91:** Run graph extraction after successful Qdrant vector upsert.
- **D-92:** Use parent-level extraction: one Gemini 2.0 Flash structured-output call per parent chunk, sequentially. Do not run extraction per child and do not parallelize parent calls in MVP.
- **D-147:** Use the current `google-genai` SDK for Gemini API integration. Do not use legacy `google-generativeai` in Phase 4.
- **D-93:** If graph extraction or graph upsert fails, the whole document indexing fails. Do not emit `document.indexed` for hybrid-only partial state.
- **D-94:** On `ENTITY_EXTRACTION` or `GRAPH_UPSERT` failure after Qdrant upsert, rollback Qdrant by delete-by-filter `documentId`, then publish failed event and set `document_index_state.status=FAILED`.
- **D-95:** If rollback cleanup itself fails, log critical error and still publish the original failed event. A later retry/reindex starts with delete-by-filter and can repair stale Qdrant state.
- **D-96:** Entity extraction malformed JSON gets one local retry, then fails `ENTITY_EXTRACTION` with retryable false.
- **D-97:** After collecting unique entities for a document, embed entity texts as dense-only vectors through the same local `FlagEmbedding` bge-m3 adapter and store them on `Entity.embedding`.
- **D-98:** Entity embedding failure is attributed to `ENTITY_EXTRACTION` but uses the same local FlagEmbedding failure classification as `EMBEDDING`.
- **D-99:** Use one Neo4j write transaction per document for Document, Entities, RelationMentions, and edges.
- **D-100:** Graph extraction wave must create prompt file `ai-service/src/corp_rag_ai/pipeline/indexing/prompts/entity_extraction_v1.md` with `## System prompt` and `## User template` sections.
- **D-101:** Prompt file is versioned in filename; create a new file for major schema/type changes. Code references `ENTITY_EXTRACTION_PROMPT_VERSION`.
- **D-102:** Graph extraction wave must add golden fixture `ai-service/tests/fixtures/entity_extraction/01_hr_policy_basic.json`, mocked unit tests, skipped live Gemini integration test requiring `GEMINI_API_KEY`, and README guidance.
- **D-103:** Prompt content is authored during graph wave, but must include entity type whitelist, relation type guidance using UPPER_SNAKE_CASE open vocabulary, structured-output JSON schema, language instruction, and one few-shot example.

### Tier-0 Corpus Sanitizer
- **D-104:** Phase 4 sanitizer is Tier-0 regex/rules only. Do not add LLM sanitizer during ingestion.
- **D-105:** Sanitizer runs on child chunk text after chunking and before embedding. It does not modify parent chunks in AI Postgres.
- **D-106:** Sanitizer output per child is `sanitized_text`, `is_sanitized`, `sanitizer_flags`, and `drop`.
- **D-107:** Drop chunks only when text is empty after cleanup, whitespace/control-character-only, punctuation-only, or single repeated character of length 50+. Prompt injection and secret-like patterns are flagged, not dropped.
- **D-108:** Minor cleanup normalizes whitespace while preserving paragraph breaks, strips leading/trailing whitespace, removes zero-width characters, removes control characters except newline and tab, and does not lowercase or strip punctuation.
- **D-109:** Prompt-injection flags include English and Russian patterns for ignoring instructions, forgetting prior content, role override, system prompt markers, chat templates, and disregarding rules.
- **D-110:** Secret-like flags include API key/secret/password/token literals, AWS key literals, JWT-like tokens, PEM private keys, and bearer tokens.
- **D-111:** Deliberately do not detect PII, profanity, NSFW, base64 blobs, semantic prompt injection without regex match, or OCR quality in Phase 4.
- **D-112:** Parser returning zero blocks fails `PARSING / INVALID_FILE_FORMAT`. Chunker producing zero children after non-empty blocks, or sanitizer dropping all children, fails `SANITIZATION / INVALID_FILE_FORMAT`.
- **D-113:** If at least one child remains, proceed to embedding even if some remaining chunks are flagged with `isSanitized=false`.
- **D-114:** `chunkCount` in `document.indexed` is the count of Qdrant-upserted child chunks after drops.
- **D-115:** Sanitizer flag counts are internal Python details. Do not extend the `document.indexed` event in Phase 4.
- **D-116:** Sanitizer code should be reusable enough for Phase 5 Tier-0 input guard, but Phase 5 usage is not a Phase 4 requirement.

### Failure Matrix And Failed Event Reporting
- **D-117:** `04-CONTEXT.md` is the canonical source for stage/error/retryability behavior. Do not spread contradictory retry rules across implementation.

| Stage | Example failure | errorCode | retryable | Rollback before failed event publish | Event behavior |
|---|---|---|---|---|---|
| FETCHING | MinIO timeout / network | DEPENDENCY_UNAVAILABLE | true | None | publish failed; status=FAILED |
| FETCHING | MinIO object 404 delete race | DOCUMENT_NOT_FOUND | false | None | silently skip; do not publish failed |
| FETCHING | MinIO 403 / auth error | DEPENDENCY_UNAVAILABLE | false | None | publish failed; status=FAILED |
| PARSING | docling crash / corrupt file | INVALID_FILE_FORMAT | false | None | publish failed; status=FAILED |
| PARSING | parser returned 0 blocks | INVALID_FILE_FORMAT | false | None | publish failed; status=FAILED |
| PARSING | unsupported MIME | UNSUPPORTED_FILE_TYPE | false | None | publish failed; status=FAILED |
| CHUNKING | internal logic error | INDEXING_PIPELINE_ERROR | false | None | publish failed; status=FAILED |
| SANITIZATION | all children dropped / 0 valid chunks | INVALID_FILE_FORMAT | false | None | publish failed; status=FAILED |
| SANITIZATION | internal logic error | INDEXING_PIPELINE_ERROR | false | None | publish failed; status=FAILED |
| EMBEDDING | FlagEmbedding model load failed | INDEXING_PIPELINE_ERROR | false | None | publish failed; status=FAILED |
| EMBEDDING | FlagEmbedding inference exception, OOM, torch/transformers runtime error | INDEXING_PIPELINE_ERROR | false | None | publish failed; status=FAILED |
| VECTOR_UPSERT | Qdrant connection refused / timeout | DEPENDENCY_UNAVAILABLE | true | None | publish failed; status=FAILED |
| VECTOR_UPSERT | Qdrant 4xx bad schema / missing collection | INDEXING_PIPELINE_ERROR | false | None | publish failed; status=FAILED |
| ENTITY_EXTRACTION | Gemini 429 after 3 attempts | DEPENDENCY_UNAVAILABLE | true | Qdrant delete-by-filter documentId | publish failed; status=FAILED |
| ENTITY_EXTRACTION | Gemini 5xx / timeout after backoff | DEPENDENCY_UNAVAILABLE | true | Qdrant delete-by-filter documentId | publish failed; status=FAILED |
| ENTITY_EXTRACTION | Gemini malformed JSON after retry | INDEXING_PIPELINE_ERROR | false | Qdrant delete-by-filter documentId | publish failed; status=FAILED |
| ENTITY_EXTRACTION | Gemini auth error | DEPENDENCY_UNAVAILABLE | false | Qdrant delete-by-filter documentId | publish failed; status=FAILED |
| ENTITY_EXTRACTION | entity embedding FlagEmbedding failure | INDEXING_PIPELINE_ERROR | false | Qdrant delete-by-filter documentId | publish failed; status=FAILED |
| GRAPH_UPSERT | Neo4j connection refused / timeout | DEPENDENCY_UNAVAILABLE | true | Qdrant delete-by-filter documentId | publish failed; status=FAILED |
| GRAPH_UPSERT | Neo4j Cypher constraint violation | INDEXING_PIPELINE_ERROR | false | Qdrant delete-by-filter documentId; Neo4j cleanup attempted | publish failed; status=FAILED |
| GRAPH_UPSERT | Neo4j out of memory | INDEXING_PIPELINE_ERROR | false | Qdrant delete-by-filter documentId; Neo4j cleanup attempted | publish failed; status=FAILED |

- **D-118:** AI Postgres failure during early idempotency check is not mapped to indexing stage and does not publish a failed event. Throw, let RabbitMQ retry/NACK/DLQ.
- **D-119:** If failed-event AMQP publish fails, do not insert `processed_events`. Redelivery retries the publish path.
- **D-120:** `retryable=true` is a Java/admin hint that a later document upload retry may succeed. It does not mean Python keeps retrying after local backoff has been exhausted.
- **D-121:** Use existing error codes only: `DEPENDENCY_UNAVAILABLE`, `DOCUMENT_NOT_FOUND`, `INVALID_FILE_FORMAT`, `UNSUPPORTED_FILE_TYPE`, and `INDEXING_PIPELINE_ERROR`. Do not add Phase 4 error codes unless a new discussion/contract wave is needed.
- **D-122:** `document.indexing.failed` envelope remains unchanged. Payload fields are `documentId`, `stage`, `errorCode`, `errorMessage`, `failedAt`, `retryable`, and `retryCount`.
- **D-123:** `errorMessage` is concise and sanitized. Do not include stack traces, `str(exception)`, raw HTTP response bodies, document text fragments, chunk IDs, document title, original filename, or secrets.
- **D-124:** Error message format is Russian stage description, English technical detail, and optional Russian remediation hint.
- **D-125:** Implement centralized `StageFailure` in `domain/exceptions.py` with `stage`, `error_code`, `retryable`, `message_template`, `template_vars`, and `to_error_message(max_len=2048)`.
- **D-126:** Template variables must be safe: exception class name only, HTTP status code, literal `timeout`, event MIME type, parser name, truncated structured Qdrant error summary, or truncated Neo4j constraint summary.
- **D-127:** Full exception details and raw dependency responses may go to Python application logs and Langfuse traces, not to Java events.
- **D-128:** Correlation ID for outbound result events is incoming AMQP header, then incoming envelope metadata, then a newly generated UUID.
- **D-129:** `retryCount` is 0 unless a future Java retry mechanism includes a count. Python does not track or increment retry count in Phase 4.

### Verification And UAT
- **D-130:** Phase 4 UAT is held at the end, not interleaved after every wave.
- **D-131:** UAT preflight P1 must prove local FlagEmbedding bge-m3 model loading and one smoke inference. The smoke must verify dense vector dimension 1024 and non-empty sparse lexical weights. Failure means insufficient disk/RAM/model cache or dependency incompatibility, and blocks UAT.
- **D-132:** UAT preflight P2 must prove Gemini 2.0 Flash structured output access through `google-genai` with `GEMINI_API_KEY`.
- **D-133:** UAT preflight P3 must prove Docker stack starts on retained volumes, `python-ai` is healthy, Qdrant collection exists with correct schema, and Neo4j accepts connections.
- **D-134:** UAT Scenario 1 consumes Phase 3 accumulated messages and expects one successful indexed document, one deleted/tombstoned document, 3 AI `processed_events`, 2 `document_index_state` rows, no backend failed messages, and Java status/audit updated for indexed event.
- **D-135:** UAT Scenario 2 uploads a fresh multi-page PDF and expects Java `INDEXED`, realistic chunk count, `neo4jEntityCount >= 1`, Qdrant payload fields present, Neo4j Document/Entity/RelationMention data present, Java audit received indexed event, and parent rows in AI Postgres.
- **D-136:** UAT Scenario 3 forces non-retryable PARSING failure with a broken PDF-like file and expects `PARSING / INVALID_FILE_FORMAT / retryable=false`, Java `FAILED`, no Qdrant/Neo4j artifacts for that document, AI state `FAILED`, and terminal `processed_events`.
- **D-137:** UAT Scenario 4 stops Neo4j before a valid upload to force `GRAPH_UPSERT / DEPENDENCY_UNAVAILABLE / retryable=true` and must prove Qdrant rollback removed points for that `documentId`.
- **D-138:** UAT Scenario 5 republishes a processed `document.uploaded` event with the same `eventId` and expects Python duplicate ACK, no new Qdrant/Neo4j work, no new indexed event, and unchanged Java status.
- **D-139:** Optional UAT Scenario 6 deletes an indexed document and verifies Qdrant/Neo4j cleanup plus AI tombstone state.
- **D-140:** UAT does not manually cover every matrix row; unit/integration tests own regex patterns, failure matrix variants, parser MIME coverage, mock 429 behavior, and deterministic chunking.

### the agent's Discretion
- Choose exact Python package/module names that preserve adapter/service/domain/repository boundaries and the locked file paths.
- Choose exact async libraries and wrappers around `aio-pika`, Qdrant client, Neo4j driver, MinIO client, local FlagEmbedding adapter, and `google-genai` SDK if behavior matches the decisions above.
- Choose exact prompt wording in `entity_extraction_v1.md` within the locked prompt lifecycle and content guidelines.
- Choose exact unit/integration test organization beyond required fixture names and critical tests.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning State
- `.planning/PROJECT.md` - project value, service ownership, architecture constraints, and locked decisions.
- `.planning/REQUIREMENTS.md` - Phase 4 requirements ING-01 through ING-07.
- `.planning/ROADMAP.md` - Phase 4 goal, success criteria, dependencies, and handoff note.
- `.planning/STATE.md` - current position, accumulated decisions, and Phase 3 handoff pointer.
- `.planning/phases/01-foundation-contracts/01-CONTEXT.md` - contract-first rules, generated-code policy, root contracts source of truth, and Docker Compose contour.
- `.planning/phases/02-identity-users-access-control/02-CONTEXT.md` - access-filter semantics and Java/Python split details.
- `.planning/phases/03-documents-events-audit/03-CONTEXT.md` - document lifecycle, outbox, result event, delete, audit, and correlation decisions that Phase 4 must preserve.
- `.planning/phases/03-documents-events-audit/03-HANDOFF.md` - Phase 4 preflight risks, accumulated RabbitMQ UAT messages, and Java integration artifacts.

### Contracts
- `contracts/asyncapi/events-v1.yaml` - document lifecycle envelope/payload schemas, event stages, queues, and headers.
- `contracts/constants.yaml` - shared routing keys, queue names, exchange names, and error codes used by Python-generated constants.
- `contracts/openapi/ai-service-v1.yaml` - query/access-filter contracts that later retrieval must align with.
- `contracts/openapi/api-v1.yaml` - Java document status and frontend-facing document behavior.

### Architecture And ADRs
- `docs/ARCHITECTURE.md` - target architecture, Python ingestion epics, parser/embedding/Qdrant/Neo4j references, and original graph/chunking designs that Phase 4 intentionally refines.
- `docs/PATTERNS.md` - event envelope, idempotent consumer, database-per-service, DTO separation, and transport/service layering patterns.
- `docs/decisions/ADR-001-embedding-model.md` - bge-m3 dense+sparse embedding decision.
- `docs/decisions/ADR-002-vector-database.md` - Qdrant collection, dense+sparse vector, and payload filter decision.
- `docs/decisions/ADR-003-java-python-split.md` - Java/Python responsibilities and database ownership.

### Existing Integration Code
- `scripts/generate_python_contracts.py` - Python contract model generation used by local dev and Docker builder.
- `scripts/generate_constants.py` - Java/Python constants generation used by local dev and Docker builder.
- `ai-service/Dockerfile` - current Python image to convert to repo-root multi-stage codegen build.
- `ai-service/src/corp_rag_ai/main.py` - current FastAPI app entrypoint for startup hooks and health checks.
- `ai-service/src/corp_rag_ai/config.py` - existing Settings surface to extend with local embedding/model cache, Gemini, Qdrant init, and worker config.
- `ai-service/migrations/env.py` - Alembic async migration harness.
- `ai-service/migrations/versions/0001_empty_baseline.py` - baseline; Phase 4 migrations continue from here.
- `infra/docker-compose.yml` - python-ai context/env/dependency wiring, Qdrant, Neo4j, MinIO, RabbitMQ, and retained volume contour.
- `backend/corp-rag-app/src/main/java/com/corprag/config/AmqpConfig.java` - queue/exchange topology Python must consume/publish against.
- `backend/corp-rag-app/src/main/java/com/corprag/service/outbox/EventEnvelopeFactory.java` - Java envelope/header pattern Python should mirror for result events.
- `backend/corp-rag-app/src/main/java/com/corprag/service/events/IdempotentEventProcessor.java` - Java idempotent consumer behavior to understand and adapt, not copy blindly.
- `backend/corp-rag-app/src/main/resources/db/migration/V13__create_processed_events_table.sql` - Java processed-events schema reference.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/amqp/DocumentIndexedConsumer.java` - Java expectations for `document.indexed`.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/amqp/DocumentIndexingFailedConsumer.java` - Java expectations for `document.indexing.failed`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ai-service/src/corp_rag_ai/main.py` is currently only health/readiness; Phase 4 adds startup hooks and worker lifecycle while preserving those endpoints.
- `ai-service/src/corp_rag_ai/config.py` already uses pydantic-settings and has Postgres, RabbitMQ, Qdrant, Neo4j, MinIO, and Langfuse env fields to extend.
- `ai-service/migrations/` already has Alembic async infrastructure for AI-owned Postgres migrations.
- `scripts/generate_python_contracts.py` and `scripts/generate_constants.py` already generate ignored Python contract artifacts at the path runtime imports expect.
- `infra/docker-compose.yml` already wires python-ai to postgres, minio, rabbitmq, qdrant, neo4j, and langfuse.
- Java Phase 3 already declares queues, publishes `document.uploaded`/`document.deleted`, consumes `document.indexed`/`document.indexing.failed`, and carries correlation IDs.

### Established Patterns
- Contract-first: root `contracts/` and `contracts/constants.yaml` remain the shared source of truth; generated code is not committed.
- Java owns auth/RBAC/document metadata/MinIO upload lifecycle; Python owns parsing, indexing, vector/graph storage, and retrieval-time application of access metadata.
- Event messages use `EventEnvelope { metadata, payload }` with AMQP headers for correlation and event type/version.
- Consumers must be idempotent, but Python cannot copy Java's insert-first pattern because Python has external side effects outside one DB transaction.
- Service code should keep adapter/service/domain/repository separation; transport/AMQP adapters validate/map and delegate.

### Integration Points
- Extend Python dependencies for parsing, AMQP, MinIO, Qdrant, Neo4j, local FlagEmbedding, `google-genai`, token counting, Markdown parsing, and tests.
- Add AI Postgres migrations for `processed_events`, `document_index_state`, and `document_chunks_parent`.
- Add AMQP consumers for `ai.document.uploaded` and `ai.document.deleted`, plus publisher for backend result queues.
- Add MinIO fetch adapter using payload bucket/key rather than querying Java.
- Add Qdrant startup initializer and vector indexer.
- Add Neo4j schema initializer, entity extractor, and graph indexer.
- Add end-to-end orchestration in an ingestion service with terminal outcome semantics and rollback behavior.

</code_context>

<specifics>
## Specific Ideas

- First execution wave should prioritize clean Docker codegen and retained-queue startup safety before deeper ingestion logic.
- Local FlagEmbedding bge-m3 loading and dense+sparse smoke inference is a hard UAT preflight. HF sparse-output preflight is removed because HF free-tier feature extraction is dense-only.
- UAT should intentionally use the retained Phase 3 queue messages to validate delete-before-upload and real cross-service consumption.
- Phase 4 intentionally departs from two original architecture hints: deterministic structural chunking replaces SemanticSplitter for MVP, and provenance-first Neo4j graph replaces direct entity-edge graph.
- Parent context is stored in AI Postgres, not duplicated into every Qdrant payload and not embedded separately.
- Graph extraction prompt is a visible markdown artifact, not a buried Python string.

</specifics>

<deferred>
## Deferred Ideas

- Python result outbox and publisher confirms are deferred to Phase 7+.
- OCR for scan-only PDFs is deferred to Phase 7+.
- SemanticSplitter/pysbd/nltk/spaCy sentence splitting is deferred to Phase 7+ ablation.
- Hosted embedding providers such as DeepInfra, NVIDIA NIM, and HF Inference Endpoints are deferred because they are paid/provider-specific and violate the Phase 4 ADR-001 free-tier MVP constraint.
- Self-hosted text-embeddings-inference or a separate embedding service is deferred to Phase 7+ if local CPU FlagEmbedding becomes a measured bottleneck.
- Phase 5 reranker model download and reranking implementation are deferred to Phase 5; Phase 4 only reserves memory headroom.
- Parent embeddings and parent retrieval collection are deferred to Phase 7+ evaluation.
- Neo4j community detection, graph summaries, cross-language entity aliasing, orphan RelationMention cleanup, and reference-counted entity cleanup are deferred to Phase 7+.
- PII redaction and semantic LLM sanitizer during ingestion are deferred unless new requirements demand them.
- Java/admin manual retry endpoint and retry counters are deferred to Phase 7+.

</deferred>

---

*Phase: 4-Python Ingestion & Indexing*
*Context gathered: 2026-05-17*
