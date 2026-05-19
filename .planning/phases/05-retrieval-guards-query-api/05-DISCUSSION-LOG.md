# Phase 5: Retrieval, Guards & Query API - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-05-19
**Phase:** 5-Retrieval, Guards & Query API
**Areas discussed:** Guard strictness and unsafe evidence, Hybrid plus graph routing shape, Citation and refusal rules, Reranker and degraded-mode behavior

---

## Guard Strictness And Unsafe Evidence

| Option | Description | Selected |
|--------|-------------|----------|
| Audit + code constants | Python returns guard/degraded metadata, Java audits rejected/out-of-scope/degraded query outcomes, and guard patterns stay code constants in Phase 5. | yes |
| Response only | Python returns metadata, but Java audit integration waits for a later phase. | |
| Configurable guards | Externalize guard patterns now through runtime config. | |

**User's choice:** Audit + code constants.

**Notes:** The user and architect input confirmed a two-layer guard model. Input guard hard-rejects prompt injection and toxic/policy requests, marks non-corporate requests as out of scope, and performs no retrieval for rejected/out-of-scope queries. Output guard validates citation coverage and leak risk. Retrieved chunks with `isSanitized=false` are downranked by a default `0.5` score multiplier rather than excluded, overriding the original architecture assumption that retrieval filters `isSanitized=true`. If final evidence contains only flagged chunks, the answer is forced to `answered=false` with reason `unsafe_evidence_only`. Java should audit query/guard/degraded outcomes inline on the synchronous query path; guard patterns stay code constants, consistent with Phase 4 sanitizer behavior.

---

## Hybrid Plus Graph Routing Shape

| Option | Description | Selected |
|--------|-------------|----------|
| 0.65 balanced cutoff | Rules-based matches route directly; DeepSeek fallback below `0.65` becomes `UNSUPPORTED`. | yes |
| 0.50 permissive cutoff | Fewer refusals, but higher wrong-route risk. | |
| 0.80 strict cutoff | More defensive routing, but likely too many refusals for demo questions. | |

**User's choice:** Rules-based primary router plus DeepSeek JSON fallback with `AI_ROUTER_CONFIDENCE_THRESHOLD=0.65`.

**Notes:** Rules-based matches are implicit confidence `1.0`. LLM fallback returns `{query_type, confidence}` through JSON schema. If confidence is below `0.65`, Python returns `UNSUPPORTED`, `answered=false`, no retrieval, and no generation. If DeepSeek classifier is unavailable, Python degrades to rules-only routing; if rules do not match, the query is unsupported. The five query types are `FACTUAL`, `AGGREGATION`, `MULTI_HOP`, `COMPARISON`, and `UNSUPPORTED`. Factual uses Qdrant hybrid retrieval only; aggregation and multi-hop use Neo4j first; comparison uses parallel factual paths with optional Neo4j disambiguation; unsupported short-circuits.

---

## Citation And Refusal Rules

| Option | Description | Selected |
|--------|-------------|----------|
| Concat + float | Resolve all final child hits to parents, concatenate parents by score under a token cap, and expose float confidence from top reranker score. | yes |
| Best parent only | Use only the highest-scored parent, producing tighter context but weaker multi-evidence answers. | |
| Concat + binned confidence | Concatenate parents, but expose high/medium/low instead of a float. | |

**User's choice:** Concat + float.

**Notes:** Parent context is fetched from AI Postgres by `parentChunkId`, deduped, ordered by max child score, and concatenated under a 4000-token cap. Citations are per child chunk, not per parent, because child chunks are retrieval units and UI source keys. Strict inline `[N]` citations are required; output validation rejects invalid or missing refs. `confidence` remains a float and is normally `clamp(top_reranker_score, 0.0, 1.0)`. Evidence below `0.4` forces `answered=false`. Aggregation and comparison answers still require citations.

---

## Reranker And Degraded-Mode Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| MVP single concurrency + 6GB | Reranker on by default, one local reranker critical section, and Wave 1 bumps `python-ai` to 6GB/4GB memory contour. | yes |
| Small concurrency + 8GB | Allow 2-3 concurrent queries with a larger local runtime footprint. | |
| Keep 4GB | Avoid compose change, but keep the Phase 4 memory risk. | |

**User's choice:** MVP single concurrency + 6GB.

**Notes:** Phase 5 should use `bge-reranker-v2-m3` locally through FlagEmbedding/FlagReranker as anticipated by Phase 4 D-148. Reranker is enabled by default in compose and mockable/disabled in CI. Runtime should use a semaphore size 1 around the reranker critical section. `infra/docker-compose.yml` should move `python-ai` to `mem_limit: 6g` and `mem_reservation: 4g` in Wave 1 because Phase 4 UAT observed about 94 percent memory usage on embedding-only work. Degraded mode is explicit: OpenRouter generation failure, Qdrant failure in factual/comparison, Neo4j failure in graph routes, and embedding failure are hard failures; Qdrant failure in aggregation/multi-hop may degrade to Neo4j-only; reranker failure may degrade to raw retrieval order with metadata.

---

## Drafting Notes Accepted

| Item | Description | Selected |
|------|-------------|----------|
| Continue D-numbering | Phase 4 highest decision is D-148, so Phase 5 starts at D-149. | yes |
| ADR-005 through ADR-008 | Required additions for query routing, degraded mode, citation/refusal, and guard architecture. | yes |
| Fold PH4-UAT-DEF-01 into Wave 1 | Duplicate ingestion idempotency fix is a Phase 5 prerequisite, not deferred backlog. | yes |
| Record explicit out-of-scope items | Streaming, throughput, ML classifiers, external guard config, OCR, graph cleanup, frontend/chat, and eval are outside Phase 5. | yes |

**User's choice:** Write the context with these drafting constraints.

**Notes:** The user asked to mirror the Phase 4 context structure, continue decision numbering, verify ADR numbering, record out-of-scope items, and explicitly call out `PH4-UAT-DEF-01` as a Wave 1 Phase 5 task.

---

## the agent's Discretion

- Exact module names and prompt wording are left to planning/execution as long as the locked behavior is preserved.
- Exact Java audit event names are left to planning/execution, but guard and degraded outcomes must be auditable.
- Exact graph traversal Cypher and tests are planner-owned, provided access filters are pushed into Neo4j before evidence returns.

## Deferred Ideas

- Streaming answers over SSE.
- Query concurrency above one reranker critical section.
- Trained ML guard/router classifiers.
- Externalized guard pattern configuration.
- OCR for scanned PDFs.
- Orphan Neo4j entity cleanup.
- BM25 production retrieval.
- Java chat persistence and frontend citation UI.
- RAGAS, ablation, injection-probe reporting, and observability dashboards.
