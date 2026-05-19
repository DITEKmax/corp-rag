# Phase 5: Retrieval, Guards & Query API - Context

**Gathered:** 2026-05-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 5 delivers the Python AI query path behind Java's browser-facing chat API. Python accepts Java-owned `QueryRequest` calls with a server-resolved `AccessFilter`, rejects unsafe or out-of-scope queries before retrieval, routes supported queries, retrieves only permitted evidence from Qdrant and Neo4j, resolves parent context from AI Postgres, reranks evidence, generates cited structured answers through DeepSeek V4 Flash via OpenRouter, validates output before return, and reports retrieval, guard, degradation, and confidence metadata back to Java.

This phase also folds in one Phase 4 UAT prerequisite: fix duplicate ingestion event idempotency before load-sensitive query work starts.

This phase does not implement Java chat persistence, browser UI, evaluation dashboards, production throughput, streaming answers, OCR, backups, graph cleanup jobs, or trained ML classifiers.

</domain>

<decisions>
## Implementation Decisions

### Scope, Contracts, And ADRs
- **D-149:** Phase 5 is a diploma MVP. Optimize for defensible trade-offs, demoability during defense, and CI-testable behavior rather than production-grade throughput or extensibility.
- **D-150:** Java remains the browser-facing authority for auth, access-filter resolution, correlation, rate limiting, and audit persistence. Python only applies the Java-provided `AccessFilter` and returns evidence, answer, guard verdicts, and retrieval metadata.
- **D-151:** The Java-to-Python query path is synchronous HTTP, not AMQP. Java calls Python `POST /v1/query`, receives the response or error, then records query/guard/degradation audit rows inline on the Java side. Query processing is read-oriented and does not use Python `processed_events`.
- **D-152:** Use an explicit internal query timeout target of 30 seconds for Java-to-Python query calls. Planner may tune exact client/server timeout wiring, but silent indefinite waits are not acceptable.
- **D-153:** Contract work must start from the existing root OpenAPI files. `contracts/openapi/ai-service-v1.yaml` already defines `/v1/query`, `QueryRequest`, `QueryRoute`, `RetrieverType`, `GuardVerdict`, `RetrievalMeta`, and `QueryResponse`; Phase 5 should align with that surface or update it contract-first before implementation.
- **D-154:** Fix the current citation contract mismatch during the contract wave: actual `chunkId` values are deterministic UUID strings from Phase 4, not `ch-NNN-MMM` identifiers. `Citation`/chunk-detail schemas must represent UUID child chunk IDs and include enough display fields for Phase 6 source viewing.
- **D-155:** Add Phase 5 ADRs before or during the first design/contract wave: `ADR-005` Query routing model, `ADR-006` Degraded-mode policy, `ADR-007` Citation contract and refusal rules, and `ADR-008` Guard architecture. `docs/decisions/` currently ends at `ADR-004`.
- **D-156:** Map all Phase 5 plans directly to `RET-01` through `RET-04`, `AGT-01` through `AGT-03`, and `SEC-01` in `.planning/REQUIREMENTS.md`.
- **D-157:** `PH4-UAT-DEF-01` is folded into Phase 5 Wave 1, not deferred. Before query work, wire `IdempotentEventDispatcher` in `ai-service/src/corp_rag_ai/main.py` around upload/delete handlers and add a regression proving duplicate event IDs do not call Qdrant, Neo4j, or OpenRouter again.

### Guard Architecture
- **D-158:** Use a two-layer guard model. The input guard can hard-reject before retrieval; the output guard validates answer safety and citation compliance after generation and before return.
- **D-159:** Do not build a trained ML guard classifier in Phase 5. Use rules-based checks plus optional cheap DeepSeek classification when rules are insufficient. A custom ML classifier without a defended dataset is out of scope.
- **D-160:** Store Phase 5 guard patterns as code constants, consistent with the Phase 4 corpus sanitizer. Externalized runtime guard-pattern configuration is deferred.
- **D-161:** Reuse Phase 4 sanitizer regex signatures where appropriate for Tier-0 prompt-injection detection, but query guards may have query-specific wrappers and verdict mapping.
- **D-162:** Input prompt-injection attempts, such as instruction override, role-play attacks, or system prompt extraction, return `answered=false`, no retrieval, and a rejected guard verdict with reason `prompt_injection`.
- **D-163:** Off-topic or non-corporate requests, such as small talk, math, or code generation, return `answered=false`, no retrieval, and an `out_of_scope` guard verdict. This is not treated as an unsafe attack.
- **D-164:** Toxic or harassment requests return `answered=false`, no retrieval, and a rejected guard verdict with reason `policy`.
- **D-165:** Retrieved chunks with `isSanitized=false` are downranked, not excluded. Default penalty is a final-score multiplier of `0.5`. This intentionally overrides `docs/ARCHITECTURE.md` sections that say retrieval must filter `isSanitized=true`.
- **D-166:** If the final top-N evidence set contains only flagged chunks, the output guard forces `answered=false` with reason `unsafe_evidence_only`.
- **D-167:** Output guard validates citation coverage and leak risk. If a generated answer contains factual claims without valid citation refs, invalid citation refs, or secret/PII-like leakage patterns from retrieved evidence, it must block the answer or force `answered=false`.
- **D-168:** Retrieved context sent to the LLM must be isolated from instructions, using the XML-style context boundary already described in `docs/ARCHITECTURE.md`.
- **D-169:** Python returns guard and degraded-mode metadata; Java records audit rows for rejected, out-of-scope, and degraded query outcomes. Prefer direct Java audit table writes on the synchronous query path over outbox/event indirection for Phase 5.

### Query Routing
- **D-170:** Use rules-based routing first and DeepSeek JSON-schema classification as fallback. Do not build a trained ML router.
- **D-171:** The supported query routes are exactly `FACTUAL`, `AGGREGATION`, `MULTI_HOP`, `COMPARISON`, and `UNSUPPORTED`, matching the existing `QueryRoute` contract unless the contract wave renames fields consistently.
- **D-172:** Rules-based matches have implicit confidence `1.0` and skip the LLM classifier. LLM fallback returns `{query_type, confidence}` via strict JSON schema.
- **D-173:** Default router confidence threshold is `0.65`, exposed as `AI_ROUTER_CONFIDENCE_THRESHOLD=0.65`. If LLM fallback confidence is below threshold, route as `UNSUPPORTED`.
- **D-174:** If the DeepSeek classifier is unavailable, degrade to rules-only routing. If rules do not produce a route, return `UNSUPPORTED` with `answered=false`, no retrieval, and no generation.
- **D-175:** `FACTUAL` queries use Qdrant hybrid retrieval only: dense+sparse bge-m3 query vectors, RRF fusion, access filter in Qdrant, top-K around 20, rerank, top-N around 3, parent resolution, then generation. Neo4j is not in the primary factual path.
- **D-176:** `AGGREGATION` queries use Neo4j traversal first, then fetch supporting chunks/evidence for citation. Reranking is less central because evidence is selected by structured criteria.
- **D-177:** `MULTI_HOP` queries use Neo4j path traversal with a hard cap of 2-3 hops, then resolve document IDs and supporting chunks under the same access filter. Queries requiring deeper paths become `UNSUPPORTED`.
- **D-178:** `COMPARISON` queries run parallel factual-style evidence retrieval per compared entity or document, optionally using Neo4j only for entity disambiguation when names are ambiguous, then merge evidence for structured comparison generation.
- **D-179:** `UNSUPPORTED` short-circuits before retrieval and generation. Do not retrieve-then-fail for unsupported or low-confidence queries.
- **D-180:** Never broaden or bypass the access filter to improve recall. Low or empty retrieval under the user's filter is a legitimate `answered=false` outcome.

### Access-Filtered Retrieval
- **D-181:** Apply the Java-provided `AccessFilter` before retrieval in both storage systems: Qdrant payload filters and Neo4j Cypher `WHERE` clauses on `Document` node properties. Do not retrieve globally and filter in Python memory afterward.
- **D-182:** Qdrant access filtering uses Phase 4 payload fields `accessLevel`, `department`, and `docType`, with `PUBLIC` visibility semantics inherited from Phase 2 and Phase 3.
- **D-183:** Neo4j access filtering must filter through `Document` evidence edges, not directly through orphan `Entity` or `RelationMention` nodes. Orphan entities from deletes are ignored unless connected to accessible document evidence.
- **D-184:** Hybrid retrieval uses the existing Qdrant collection `documents_chunks`, named vectors `dense` and `sparse`, bge-m3 query embeddings, and Qdrant RRF/fusion. Classic BM25 is not part of Phase 5 production retrieval.
- **D-185:** The query embedder reuses the local bge-m3 adapter path from Phase 4. Query embedding failure is a hard query failure with `answered=false` and error `embedding_unavailable`.

### Parent Resolution, Reranking, And Context Packing
- **D-186:** Implement Phase 4 D-51 in Phase 5: parent resolver fetches parent content from AI Postgres `document_chunks_parent` by `parentChunkId`. Parent chunks are context units, not citation IDs.
- **D-187:** After reranker top-N child chunks, fetch all referenced parents, dedupe by `parent_chunk_id`, order parents by max child score descending, and concatenate parent content in that order.
- **D-188:** Total LLM evidence context cap is 4000 tokens. Truncate by parent boundary when possible; do not cut in the middle of a parent chunk unless the planner documents a last-resort behavior for a single oversized parent.
- **D-189:** Citations are per child chunk, not per parent chunk. Child chunks are the retrieval units, Qdrant point IDs, and Phase 6 source-viewer keys.
- **D-190:** Reranker is `bge-reranker-v2-m3` locally through FlagEmbedding/FlagReranker, as anticipated by Phase 4 D-148. Do not switch to a hosted reranker unless a later ADR supersedes this.
- **D-191:** Add `AI_RERANKER_ENABLED`, default true in compose/local runtime and false or mockable in CI/unit tests.
- **D-192:** Retrieval shape is Qdrant top-K about 20-30 into reranker top-N about 3-5. Do not send more than 5 final chunks/parents to generation by default because of context bloat and OpenRouter quota pressure.
- **D-193:** If reranker is unavailable but retrieval succeeded, soft-degrade to raw Qdrant order sliced to top-N, return `rerankerUsed=false`, and include a warning in retrieval metadata.
- **D-194:** MVP query concurrency is one around the local reranker critical section. Use a FastAPI-level semaphore or equivalent. Other async I/O may queue or continue, but shared local model memory must not be stressed by concurrent reranker calls.
- **D-195:** Raise `python-ai` compose memory contour in Wave 1 to `mem_limit: 6g` and `mem_reservation: 4g`. Keeping 4 GiB is rejected because Phase 4 UAT saw about 94 percent memory usage on embedding-only work.

### Citation, Refusal, And Confidence
- **D-196:** Answers must use strict inline citation references in `[N]` format, where `N` maps to the returned `citations` array.
- **D-197:** Generation prompts must tell the LLM to write only claims supported by provided evidence and to cite each factual claim with `[N]`. Unsupported claims must be omitted rather than guessed.
- **D-198:** Post-generation validation must reject answers with citation refs that do not map to existing citation indexes, or factual claims that lack refs. Planner may choose the exact heuristic for detecting uncited claims, but the validation requirement is locked.
- **D-199:** Aggregation answers still require citations. There is no citationless exception for counts, lists, comparisons, or summaries.
- **D-200:** Refuse with `answered=false` when input guard rejects, route is unsupported, retrieval returns zero chunks after access filtering, evidence is too weak, output guard fails, or the LLM explicitly says it cannot answer from provided context.
- **D-201:** Retrieval returning zero permitted chunks should produce an actionable answer such as "No accessible documents discuss this topic." Avoid vague "I don't know" wording when access-filtered absence is the reason.
- **D-202:** Weak evidence threshold is `confidence < 0.4`. Below that, force `answered=false` rather than generating a fragile answer.
- **D-203:** Confidence remains a float in `[0.0, 1.0]`, not a high/medium/low enum. Frontend can bin the value later.
- **D-204:** Normal confidence is `clamp(top_reranker_score, 0.0, 1.0)`. In degraded reranker mode, confidence may be derived from normalized raw Qdrant score, but metadata must make `rerankerUsed=false` clear because raw Qdrant score is not semantically identical to reranker score.
- **D-205:** Citations should include child `chunkId`, `documentId`, `documentTitle`, `sectionPath`, nullable page, display snippet/quote around 200 characters when possible, score, and access level. Exact field names must stay aligned with the OpenAPI contract.

### Degraded-Mode Policy
- **D-206:** Degraded behavior must be explicit and fail-loud. Silent fallback that hides lost dependencies is rejected.
- **D-207:** If OpenRouter answer generation is unavailable, return `answered=false` with error `generation_unavailable` and retrieval metadata populated as far as the pipeline progressed.
- **D-208:** If Qdrant is unavailable for `FACTUAL` or `COMPARISON`, return `answered=false` with error `vector_retrieval_unavailable`.
- **D-209:** If Qdrant is unavailable for `AGGREGATION` or `MULTI_HOP`, soft-degrade to Neo4j-only evidence. Answer only if accessible evidence exists; otherwise return `answered=false`. Set a metadata warning such as `vectorDegraded=true`.
- **D-210:** If Neo4j is unavailable for `FACTUAL`, continue normally because factual retrieval does not depend on graph evidence.
- **D-211:** If Neo4j is unavailable for `AGGREGATION` or `MULTI_HOP`, return `answered=false` with error `graph_retrieval_unavailable`.
- **D-212:** If reranker is unavailable, use the soft-degraded raw retrieval order from D-193.
- **D-213:** If query embedding fails, return `answered=false` with error `embedding_unavailable`.
- **D-214:** Extend `/diagnostics` to include query-readiness indicators such as `reranker_loaded` and `llm_reachable`, while preserving existing Phase 4 diagnostics fields.
- **D-215:** Per-query `retrievalMeta` must expose route, retrievers attempted/used, chunks considered, chunks returned, reranker usage, latency, model ID, and degradation warnings.

### Verification And UAT
- **D-216:** Unit tests must cover the degraded-mode matrix with mocked Qdrant, Neo4j, reranker, embedder, router, and OpenRouter failures.
- **D-217:** Retrieval tests must prove access filters are applied before Qdrant/Neo4j results reach reranker or generation. The forbidden pattern is global retrieval followed by in-memory filtering.
- **D-218:** Add regression coverage for `PH4-UAT-DEF-01`: duplicate upload event IDs must short-circuit before Qdrant, Neo4j, and OpenRouter calls.
- **D-219:** Phase 5 UAT should seed or upload a fresh indexed corpus before query tests because the Phase 4 TechCorp happy-path document was deleted during cleanup.
- **D-220:** Phase 5 UAT should include at least one guarded rejection, one out-of-scope query, one factual cited answer, one aggregation or multi-hop graph answer, one weak/no-evidence refusal, and one degraded-mode scenario. Recommended degraded UAT: stop Qdrant and run an aggregation query that can answer from Neo4j-only evidence with `vectorDegraded=true`.

### Wave 1 Candidates
- **D-221:** First Phase 5 wave should include the Phase 4 duplicate-idempotency fix, query contract alignment, planned ADR creation, compose memory bump, and query runtime configuration defaults before deeper retrieval/generation work.
- **D-222:** Wave 1 should also make the fresh indexed corpus path explicit, either through a seed/upload helper or a documented UAT preflight, so retrieval development is not blocked by missing evidence.

### the agent's Discretion
- Choose exact Python package/module names for query, retrieval, guards, graph traversal, reranking, synthesis, and FastAPI routers if they preserve adapter/service/domain/repository boundaries.
- Choose exact prompt wording for router, guard, and synthesizer prompts within the locked JSON-schema/strict-citation behavior.
- Choose exact test fixture layout and mock implementations, provided the coverage in D-216 through D-220 is met.
- Choose exact Java audit event names and transaction boundaries for query audit rows, as long as guard/degraded outcomes are auditable and the synchronous Java query path stays simple.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning State
- `.planning/PROJECT.md` - project value, service ownership, architecture constraints, locked ADR decisions, and diploma MVP constraints.
- `.planning/REQUIREMENTS.md` - Phase 5 requirements `RET-01` through `RET-04`, `AGT-01` through `AGT-03`, and `SEC-01`.
- `.planning/ROADMAP.md` - Phase 5 goal, success criteria, dependencies, and Phase 6/7 boundaries.
- `.planning/STATE.md` - current project state, Phase 4 handoff, pending fresh-corpus todo, and Phase 4 UAT deferred items.
- `.planning/phases/02-identity-users-access-control/02-CONTEXT.md` - Java-resolved `AccessFilter`, role/policy semantics, public visibility, and Java-to-Python filter passing.
- `.planning/phases/03-documents-events-audit/03-CONTEXT.md` - document visibility rules, Java audit pattern, document metadata ownership, and Java/Python lifecycle boundary.
- `.planning/phases/04-python-ingestion-indexing/04-CONTEXT.md` - parent resolver source, Qdrant payload schema, Neo4j evidence schema, sanitizer flags, and reranker expectation.
- `.planning/phases/04-python-ingestion-indexing/04-UAT-EVIDENCE.md` - Phase 4 UAT results, `PH4-UAT-DEF-01`, memory pressure evidence, deleted demo corpus note, and orphan entity observation.

### Contracts
- `contracts/openapi/ai-service-v1.yaml` - existing Python `/v1/query` contract, access filter schema, query routes, retrieval metadata, guard verdict, citation and chunk-detail schemas.
- `contracts/openapi/api-v1.yaml` - Java `/chat/query` and citation-facing contract that later Phase 6 consumes.
- `contracts/constants.yaml` - shared error codes including `INVALID_QUERY`, `QUERY_BLOCKED_BY_GUARD`, and `RETRIEVAL_ERROR`.
- `contracts/asyncapi/events-v1.yaml` - document lifecycle events and topology remain relevant for the folded duplicate-idempotency fix; query audit should prefer synchronous Java audit rows unless planning proves a contract event is needed.

### Architecture And ADRs
- `docs/ARCHITECTURE.md` - target query pipeline, LangGraph state, Qdrant/Neo4j retrieval assumptions, access-filter rules, XML prompt isolation, and original sanitizer-exclusion assumption that Phase 5 overrides.
- `docs/PATTERNS.md` - contract-first, adapter/service layering, explicit query objects, error contracts, and testability patterns.
- `docs/decisions/ADR-001-embedding-model.md` - bge-m3 dense+sparse embedding decision.
- `docs/decisions/ADR-002-vector-database.md` - Qdrant vector database and payload-filtered retrieval decision.
- `docs/decisions/ADR-003-java-python-split.md` - Java/Python responsibilities, Java access authority, and Python RAG ownership.
- `docs/decisions/ADR-004-llm-provider-deepseek-openrouter.md` - DeepSeek V4 Flash via OpenRouter for router, guards, synthesis, and shared LLM integration.
- `docs/decisions/ADR-template.md` - template for required Phase 5 ADRs `ADR-005` through `ADR-008`.

### Existing Python Code
- `ai-service/src/corp_rag_ai/main.py` - current lifespan wiring, diagnostics endpoint, and direct ingestion handler calls that must be wrapped for `PH4-UAT-DEF-01`.
- `ai-service/src/corp_rag_ai/config.py` - settings surface to extend with router threshold, reranker flags, query timeout knobs, and diagnostics readiness configuration.
- `ai-service/src/corp_rag_ai/pipeline/indexing/embedding.py` - local bge-m3 dense+sparse adapter for query embeddings.
- `ai-service/src/corp_rag_ai/pipeline/indexing/vector_indexer.py` - Qdrant collection name, vector names, payload fields, and schema validation helpers to reuse in retrieval.
- `ai-service/src/corp_rag_ai/pipeline/indexing/graph_indexer.py` - Neo4j Document/Entity/RelationMention schema and evidence edge model for graph retrieval.
- `ai-service/src/corp_rag_ai/pipeline/indexing/entity_extractor.py` - OpenRouter/DeepSeek strict JSON-schema call pattern to reuse for router, guard, and synthesis clients.
- `ai-service/src/corp_rag_ai/pipeline/ingestion/corpus_sanitizer.py` - Tier-0 regex patterns and sanitizer flags to reuse for query input guard and flagged-evidence handling.
- `ai-service/src/corp_rag_ai/repositories/tables.py` - `document_chunks_parent` table definition for parent resolver.
- `ai-service/src/corp_rag_ai/domain/chunks.py` - child/parent chunk data model and Qdrant payload serialization.
- `ai-service/src/corp_rag_ai/adapters/amqp/consumer.py` - `IdempotentEventDispatcher` to wire for duplicate event short-circuiting.

### Existing Java Code
- `backend/corp-rag-app/src/main/java/com/corprag/service/access/AccessFilterResolver.java` - Java-owned access-filter source.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/QueryAccessFilterMapper.java` - Java mapping into generated query `AccessFilter`.
- `backend/corp-rag-app/src/main/java/com/corprag/service/audit/AuditEventWriter.java` - audit writer to reuse for query/guard/degraded outcomes.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/ProblemDetailsExceptionHandler.java` - REST error style for future Java chat query behavior.
- `infra/docker-compose.yml` - Python AI memory contour, model cache volume, and service wiring to update for reranker runtime.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LocalBgeM3Embedder` already loads local `BAAI/bge-m3` and validates dense 1024 plus non-empty sparse lexical weights. Query embedding should reuse this instead of introducing a second embedding path.
- `QdrantVectorIndex` already centralizes `documents_chunks`, vector names `dense`/`sparse`, payload index fields, document delete filters, and Qdrant sparse vector conversion. Retrieval should reuse constants and helper patterns.
- `Neo4jGraphIndex` already creates `Document`, `Entity`, and `RelationMention` indexes and writes evidence edges through `MENTIONED_IN` and `EVIDENCE`. Graph retrieval should filter through these document-backed edges.
- `ParentChunkRepository` and `document_chunks_parent` exist for parent context retrieval; no parent embedding or parent Qdrant collection is needed in Phase 5.
- `CorpusSanitizer` already defines English/Russian prompt-injection and secret-like regex signatures. Query guards can reuse the signatures while mapping to query-specific verdicts.
- `DeepSeekEntityExtractor` already demonstrates strict JSON-schema OpenRouter calls with response-healing and retry behavior. Router, guard, and synthesis clients should follow the same pattern.
- `/diagnostics` exists and currently reports AMQP, Qdrant, and graph runtime wiring. Phase 5 extends it for query readiness.

### Established Patterns
- Root `contracts/` remains the shared source of truth; generated code is build output.
- Java owns auth, RBAC, access filters, frontend-facing APIs, audit rows, and query rate limiting.
- Python owns ML/RAG pipeline code and applies, but does not compute, the user's visibility.
- Retrieval filters must be pushed into Qdrant/Neo4j before evidence reaches reranking or generation.
- Adapters validate/map transport concerns; services own use-case orchestration; repositories own persistence/query mechanics.
- Phase 4 intentionally made parent chunks context units and child chunks retrieval/citation units; Phase 5 preserves that split.

### Integration Points
- Add Python query domain models and FastAPI router for `POST /v1/query` and chunk/citation detail lookup if needed by the existing contract.
- Add retrieval modules for hybrid Qdrant retrieval, Neo4j graph retrieval, parent resolution, reranking, synthesis, and output validation.
- Extend settings with router confidence threshold, reranker enabled flag, context caps, OpenRouter query settings, and runtime diagnostics.
- Add Java-side query client/audit behavior in later Phase 6 chat plans; Phase 5 Python must still return enough metadata for Java audit.
- Update compose memory settings before loading the reranker locally.

</code_context>

<specifics>
## Specific Ideas

### Required ADR Additions
- `docs/decisions/ADR-005-query-routing-model.md` - rules-first router, DeepSeek JSON fallback, five query types, `0.65` cutoff, classifier-unavailable behavior.
- `docs/decisions/ADR-006-degraded-mode-policy.md` - explicit failure matrix, fail-loud rule, and no silent dependency hiding.
- `docs/decisions/ADR-007-citation-contract-and-refusal-rules.md` - inline `[N]` refs, child-level citations, post-generation validation, confidence/refusal thresholds.
- `docs/decisions/ADR-008-guard-architecture.md` - input hard-reject, output validation, downrank-not-exclude for flagged chunks, code constants for guard patterns.

### Query Defaults
- Router threshold: `AI_ROUTER_CONFIDENCE_THRESHOLD=0.65`.
- Weak evidence refusal threshold: confidence `< 0.4`.
- Evidence context cap: 4000 tokens total.
- Qdrant pre-rerank top-K: 20-30.
- Final evidence top-N: 3-5, default not above 5.
- Flagged chunk score multiplier: `0.5`.
- Reranker concurrency: semaphore size 1.
- Compose memory contour: `mem_limit: 6g`, `mem_reservation: 4g`.

### Folded UAT Carry-Forward
- `PH4-UAT-DEF-01` is a Phase 5 prerequisite: wire `IdempotentEventDispatcher` in `main.py` and prove duplicate upload event IDs do not trigger Qdrant, Neo4j, or OpenRouter work.
- Seed or upload a fresh indexed corpus before retrieval UAT; the Phase 4 TechCorp happy-path document was deleted during cleanup.

### Plan-Phase Iteration Details
- Exact Java audit event names are planner-owned, but outcomes must cover rejected, out-of-scope, and degraded query flows.
- Exact prompt text is planner-owned, but router/guard/synthesis outputs must be strict, parseable, and testable.
- Exact graph traversal Cypher is planner-owned, but it must cap multi-hop depth and filter through accessible `Document` evidence.

</specifics>

<deferred>
## Deferred Ideas

- Streaming answers over SSE are deferred beyond Phase 5.
- Concurrent query throughput above one local-reranker critical section is deferred to Phase 7+.
- Trained ML guard or router classifiers are deferred indefinitely unless a real dataset and evaluation plan exist.
- Externalized runtime guard pattern configuration is deferred to Phase 7+.
- OCR for scan-only PDFs remains deferred from Phase 4.
- Orphan Neo4j entity cleanup remains deferred to Phase 7/8 maintenance; Phase 5 retrieval must ignore orphan nodes by filtering through document evidence.
- PDF/OCR dependency-surface cleanup from Phase 4 remains outside the query path unless Phase 5 planning deliberately adds a Wave 1 dependency audit.
- BM25 remains an evaluation/ablation baseline for Phase 7, not production Phase 5 retrieval.
- Java chat persistence and frontend citation UI belong to Phase 6.
- RAGAS, ablation, injection-probe reporting, and Langfuse evaluation dashboards belong to Phase 7.

</deferred>

---

*Phase: 5-Retrieval, Guards & Query API*
*Context gathered: 2026-05-19*
