# Phase 4: Python Ingestion & Indexing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md; this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 4-Python Ingestion & Indexing
**Areas discussed:** Event intake and idempotency, Parsing and chunk structure, Qdrant and Neo4j index shape, Sanitization and failure reporting

---

## Event Intake And Idempotency

| Option | Description | Selected |
|--------|-------------|----------|
| Root build context | Repo-root Docker build context with `ai-service/Dockerfile`; preserve root contracts source of truth. | yes |
| Pre-generate before build | Generate Python contract files on host before Docker build. | |
| Copy contracts into ai-service | Copy contract/script sources into service-local context. | |
| Repo-root builder stage | Multi-stage Dockerfile keeps `/repo` layout so current generator scripts work without changes. | yes |
| Add generator output args | Modify generator scripts with output/root parameters. | |
| Keep single-stage image | Keep PyYAML/build tooling in runtime image. | |
| Processed events + document index state | AI Postgres tracks terminal processed events and per-document index/tombstone state. | yes |
| Processed events only | Only event ledger; rely on Qdrant/Neo4j idempotent upserts/deletes. | |
| No AI DB state | Let RabbitMQ and external stores carry idempotency. | |
| processed_events means terminal outcome | Insert processed row only after terminal outcome; retry is safe before then. | yes |
| insert-first + resume on state | Insert first but resume incomplete state on duplicate/redelivery. | |
| Add Python outbox | Add durable result outbox for Python result events. | |

**User's choice:** Root build context; repo-root builder stage; generated directory ignored and deleted before builder codegen; processed_events plus document_index_state; terminal-outcome processed_events semantics.
**Notes:** Existing Phase 3 UAT messages must be consumed on first startup as a smoke test. Python cannot copy Java insert-first idempotency because Python has external side effects after DB work. Python result outbox and publisher confirms are deferred.

---

## Parsing And Chunk Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Sectioned block model | Normalize all formats into ordered typed blocks with section path and optional page. | yes |
| Plain text stream | Flatten to text and split by tokens. | |
| Rich parser-native model | Preserve detailed parser-native layout trees. | |
| Deterministic parent-child chunks | Structural parent chunks plus child retrieval chunks with deterministic UUIDs. | yes |
| Child-only chunks | Store only retrieval-sized Qdrant chunks. | |
| Semantic splitter first | Use semantic/embedding splitter as primary chunker. | |
| Regex + abbreviation guard | Sentence-aware split with deterministic regex and ru/en abbreviation list. | yes |
| Pure token windows | Always cut by token window. | |
| NLP sentence segmenter | Add pysbd/nltk/spaCy or similar. | |
| Section-aware plain text | Use breadcrumb+body for embeddings and body-only content for payload/display. | yes |
| Raw block concatenation | Join blocks without breadcrumbs or formatting rules. | |
| Markdown document reconstruction | Reconstruct markdown-like text with markers/fences. | |

**User's choice:** Sectioned block model, deterministic structural parent-child chunking, regex sentence boundaries, section-aware plain text serialization.
**Notes:** This intentionally defers SemanticSplitter to Phase 7+ and stores parent chunks only in AI Postgres. Qdrant has one point per child chunk.

---

## Qdrant And Neo4j Index Shape

| Option | Description | Selected |
|--------|-------------|----------|
| Single collection, named dense+sparse vectors | One Qdrant `documents_chunks` collection with named dense and sparse vectors per child point. | yes |
| Single hybrid vector field | Dense vector plus sparse data outside Qdrant-native sparse vector config. | |
| Separate dense and sparse collections | Split dense/sparse stores. | |
| Provenance-first graph | Neo4j graph stores Document, Entity, RelationMention and evidence provenance. | yes |
| Direct entity graph | Direct entity-to-entity relation edges. | |
| Community graph now | Add communities/summaries during indexing. | |
| Parent-level extraction after vector upsert | Run Gemini extraction per parent, fail whole document on graph failure. | yes |
| Best-effort graph extraction | Let Qdrant indexing succeed even if graph extraction fails. | |
| Child-level extraction | Extract graph data from child chunks. | |
| Prompt + golden fixture in graph wave | Plan must include prompt markdown and golden fixture/test artifacts. | yes |
| Fully specify prompt now | Lock full prompt text in context. | |
| Leave prompt to implementer discretion | Only lock model/schema and let implementation decide prompt. | |

**User's choice:** Single Qdrant collection with named dense/sparse vectors; provenance-first Neo4j graph without Chunk nodes; parent-level graph extraction after vector upsert; graph prompt plus golden fixture delivered in graph wave.
**Notes:** Neo4j schema intentionally overrides `ARCHITECTURE.md` 9.3. Graph failure rolls back Qdrant partial state so Java only sees `INDEXED` for fully vector+graph indexed documents.

---

## Sanitization And Failure Reporting

| Option | Description | Selected |
|--------|-------------|----------|
| Tier-0 regex only | Deterministic regex/rule sanitizer over child chunk text before embedding. | yes |
| Tier-0 + fail-closed sanitizer | Any suspicious chunk fails the whole document. | |
| Tier-0 + LLM sanitizer | Add LLM classification during ingestion. | |
| One explicit matrix in CONTEXT | Put stage/error/retryability/rollback/event behavior in one table. | yes |
| Keep decisions distributed | Leave retryability across previous area notes. | |
| Only lock code enum names | Let implementation decide retryability by exception. | |
| Stage-specific concise error messages | Keep failed envelope unchanged and send sanitized concise messages. | yes |
| Verbose errorMessage | Put full exception detail in Java event. | |
| Extend failed event details | Add structured fields to AsyncAPI/Java consumer contract. | |
| Success + forced failure + delete race | Final UAT covers happy path, forced failed event, delete race, graph rollback, and idempotency. | yes |
| Happy path only | Only prove successful indexing. | |
| Full matrix UAT | Manually test every failure matrix row. | |

**User's choice:** Tier-0 regex sanitizer only; single canonical failure matrix; unchanged failed-event envelope with sanitized messages; final UAT covers success, forced failures, retained delete race, and idempotency.
**Notes:** Failure details go to Python logs/Langfuse, not Java event payload. UAT preflight must verify HF sparse output and Gemini structured-output access before full Docker UAT.

---

## the agent's Discretion

- Exact Python package/module names within the locked adapter/service/domain/repository shape.
- Exact client wrapper APIs for AMQP, MinIO, Qdrant, Neo4j, HF, Gemini, and Langfuse.
- Exact prompt wording in `entity_extraction_v1.md` within the locked prompt file lifecycle and content constraints.
- Exact implementation details of tests beyond required fixtures and critical smoke/UAT assertions.

## Deferred Ideas

- Python result outbox and publisher confirms.
- OCR for scanned PDFs.
- SemanticSplitter/NLP sentence segmentation.
- Local/self-hosted bge-m3 fallback unless HF sparse output blocks MVP.
- Parent embeddings.
- Neo4j communities, cross-language aliases, orphan cleanup, and reference-counted entity cleanup.
- PII redaction and LLM sanitizer during ingestion.
- Java/admin manual retry and retry counters.

---

## LLM Provider Pivot To DeepSeek

**Trigger:** Phase 4 UAT P2 preflight failed three times. The Gemini free tier for `gemini-2.0-flash` returned `429 RESOURCE_EXHAUSTED` with `limit=0` for RPM, RPD, and TPM across different API keys and two Google AI Studio projects, which makes this a policy-level regional/project restriction rather than a temporary rate limit.

| Provider | Pros | Cons | Decision |
|---|---|---|---|
| Gemini 2.0 Flash (status quo) | Already integrated, fast | quota=0 policy block, region-locked, requires Google billing | REJECTED |
| Gemini 1.5 Flash | Might have softer quota | same regional policy risk, slower | REJECTED |
| DeepSeek V4 Flash via OpenRouter | open-source, MIT, works from any region, strict json_schema mode, response-healing plugin, $0.14/$0.28 paid pricing | newer (Apr 2026), slightly higher latency | ACCEPTED |
| DeepSeek V3 via OpenRouter | older, more battle-tested | $0.32/$0.89, no 1M context | REJECTED for primary, kept available |
| Claude/OpenAI direct | best quality | no free tier, paid card needed | REJECTED |
| Local LLM (Ollama/llama.cpp) | full control | 16GB RAM is not enough for a serious model plus bge-m3 | REJECTED |

**Decision rationale:** DeepSeek V4 Flash satisfies the academic requirement for an open-source LLM while keeping the runtime hosted enough for MVP UAT. OpenRouter removes the single-provider access risk that blocked the previous provider and gives one OpenAI-compatible SDK surface for all LLM use cases. Strict `json_schema` mode keeps entity extraction and later guards/router outputs structured. The OpenRouter response-healing plugin auto-repairs common malformed JSON before application-side Pydantic validation. Using one model ID, `deepseek/deepseek-v4-flash`, simplifies testing, configuration, failure semantics, and later Phase 5 maintenance.

**Implications:** `ARCHITECTURE.md` section 3.3 is rewritten around DeepSeek V4 Flash through OpenRouter. ADR-001 is clarified and ADR-004 records the LLM provider decision. The Phase 4 failure matrix `EMBEDDING` and `ENTITY_EXTRACTION` rows use HTTP/provider error semantics where relevant. The `google-genai` dependency and Gemini environment/configuration surface are removed.
