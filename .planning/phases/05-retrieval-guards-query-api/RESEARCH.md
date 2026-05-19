# Phase 05 Research - Retrieval, Guards and Query API

Date: 2026-05-19

This research validates the implementation surface for Phase 05 against current
repository state and primary external docs. The phase is large enough that the
plan should be split by stable contracts, retrieval primitives, generation
safety, and final orchestration rather than by one monolithic query endpoint.

## A. Current Repository State

### Implemented assets to reuse

- Python already has local `BAAI/bge-m3` dense+sparse embeddings through
  `LocalBgeM3Embedder` in `ai-service/src/corp_rag_ai/pipeline/indexing/embedding.py`.
- Qdrant indexing already owns collection `documents_chunks`, named vectors
  `dense` and `sparse`, payload fields `documentId`, `parentChunkId`,
  `documentTitle`, `sectionPath`, `content`, `language`, `docType`,
  `department`, `accessLevel`, `isSanitized`, and `sanitizerFlags`.
- Neo4j indexing already writes `Document`, `Entity`, and `RelationMention`
  nodes plus document-backed `MENTIONED_IN` and `EVIDENCE` edges. Retrieval must
  filter through accessible `Document` nodes and ignore orphan entities.
- AI Postgres already stores parent context in `document_chunks_parent`; Phase
  05 should add read methods instead of creating a second parent store.
- `CorpusSanitizer` contains prompt-injection and secret-like regex constants
  that should become the source for query input/output guards where applicable.
- `DeepSeekEntityExtractor` demonstrates the OpenRouter/OpenAI-compatible
  strict JSON schema call pattern, bounded retry, response healing, and schema
  sanitization that router, guard, and synthesizer clients can reuse.
- Python generated contract models already exist under
  `corp_rag_ai.contracts.generated.ai_service_v1`.

### Gaps and mismatches to fix first

- `contracts/openapi/ai-service-v1.yaml` and `contracts/openapi/api-v1.yaml`
  still define citation `chunkId` with the old `ch-NNN-MMM` pattern, but Phase
  04 creates deterministic UUID child chunk IDs.
- The generated Python model currently types `QueryResponse.guardVerdict` and
  `ProblemDetail.guardVerdict` as `str | None` because the generator does not
  handle nullable/allOf property schemas. The contract/codegen wave should fix
  this before query adapters are implemented.
- `ai-service/src/corp_rag_ai/main.py` still calls ingestion handlers directly.
  `IdempotentEventDispatcher` exists but is not wired, which caused Phase 04
  duplicate redelivery to redo Qdrant and OpenRouter work.
- Compose still caps `python-ai` at 4 GiB while Phase 04 UAT saw about 94
  percent memory use before adding a reranker. Phase 05 should bump the local
  contour to 6 GiB limit and 4 GiB reservation before loading the reranker.
- `langgraph` is not yet a dependency. Add it only when wiring the full graph,
  after query primitives have deterministic unit coverage.

## B. External API Notes

### Qdrant hybrid queries

Qdrant's current hybrid query docs show dense+sparse retrieval by issuing two
`Prefetch` queries against named vectors, then fusing them with
`models.FusionQuery(fusion=models.Fusion.RRF)` through `query_points`. Filters
must be supplied at retrieval time, not after the candidates are returned.

Implication: extend the current `QdrantVectorIndex` with an access-filtered
query method that embeds the query once, sends dense and sparse prefetches with
the same access filter, requests payloads, and returns pre-rerank candidates.
Do not retrieve globally and filter in memory.

Primary source:

- Qdrant hybrid queries: https://qdrant.tech/documentation/search/hybrid-queries/

### Local BGE reranker

The BAAI model card for `BAAI/bge-reranker-v2-m3` documents `FlagReranker` for
query/passage scoring. `compute_score(..., normalize=True)` maps scores into
`[0, 1]`, which fits the Phase 05 confidence policy.

Implication: add a small adapter around `FlagReranker` with lazy loading,
`asyncio.to_thread`, a FastAPI-level semaphore size 1, and a soft-degrade path
when the reranker is disabled or unavailable.

Primary source:

- BAAI bge-reranker-v2-m3 model card: https://huggingface.co/BAAI/bge-reranker-v2-m3

### LangGraph orchestration

LangGraph's Graph API uses a typed state schema, node functions that return
state updates, `add_conditional_edges` for dynamic routing, and a required
`compile()` step before invocation. The docs explicitly support `TypedDict` and
Pydantic states.

Implication: use a small internal `TypedDict`/dataclass state for the query
graph. Keep the graph as orchestration only; guards, retrievers, reranker, and
synthesizer should stay testable outside LangGraph.

Primary source:

- LangGraph Graph API overview: https://docs.langchain.com/oss/python/langgraph/graph-api

### OpenRouter structured outputs

OpenRouter documents `response_format: {type: "json_schema", json_schema:
{name, strict, schema}}` and recommends strict mode. It also documents
`require_parameters: true` for provider selection and response healing for
non-streaming structured output.

Implication: use the existing OpenAI-compatible client pattern from entity
extraction for router fallback, optional guard classification, and synthesis.
All such calls must validate with Pydantic after the provider returns.

Primary source:

- OpenRouter structured outputs: https://openrouter.ai/docs/guides/features/structured-outputs

## C. Planning Implications

1. Start contract-first. Fix citation UUIDs, generated `GuardVerdict` typing,
   retrieval metadata warnings, ADRs, Phase 04 idempotency, and runtime contour
   before implementation waves depend on them.
2. Implement input guard and query routing before retrieval so unsupported,
   unsafe, and out-of-scope requests can short-circuit without Qdrant, Neo4j, or
   OpenRouter synthesis work.
3. Build hybrid and graph retrieval independently behind shared domain models
   and access-filter helpers. Both must prove filters are pushed into storage.
4. Keep parent resolution and reranking as a separate plan. It bridges child
   retrieval units to parent context units and owns the reranker degradation
   metadata.
5. Keep answer synthesis/output guard separate. It owns strict citations,
   refusal reasons, confidence, and the degraded-mode matrix.
6. Wire LangGraph only after the primitives are tested. This keeps the graph
   integration thin and avoids hiding bugs inside orchestration.
7. Finish with UAT and live smoke evidence: guarded rejection, out-of-scope,
   factual cited answer, graph answer, weak/no-evidence refusal, and degraded
   Qdrant-off aggregation.

## Recommended Plan Split

| Plan | Wave | Purpose |
|---|---:|---|
| 05-01 | 1 | Contract, ADR, runtime, and Phase 04 idempotency prerequisites |
| 05-02 | 2 | Query domain, input guard, and rules/LLM query router |
| 05-03 | 3 | Access-filtered Qdrant hybrid retrieval |
| 05-04 | 3 | Access-filtered Neo4j graph retrieval |
| 05-05 | 4 | Parent resolution, reranking, context packing, and citation lookup |
| 05-06 | 5 | DeepSeek synthesis, output guard, confidence, and degradation policy |
| 05-07 | 6 | LangGraph orchestration and `/v1/query` wiring |
| 05-08 | 7 | Phase 05 verification, UAT docs, and live smoke helpers |

## RESEARCH COMPLETE

