# Phase 7 Research: Evaluation And Observability

**Researched:** 2026-06-01
**Status:** Ready for planning

## Local Findings

- The Python query graph already exposes the node boundaries Phase 7 needs to trace: `input_guard`, `route`, `hybrid_retrieval`, `graph_retrieval`, `parent_resolve`, `rerank`, `pack_context`, `synthesize`, `output_guard`, and `finalize`.
- `QdrantVectorIndex.query_hybrid` is currently hardcoded to dense and sparse `Prefetch` calls with RRF fusion. Eval-only dense/sparse/hybrid switches need a small internal mode surface, but `/v1/query` should keep production behavior.
- `/diagnostics` is cheap and read-only today. It reports wiring/readiness booleans and can be extended with in-process counters without adding a new admin surface.
- `config.py` already has Langfuse host/public/secret settings, but `ai-service/pyproject.toml` has no Langfuse client dependency. `infra/docker-compose.yml` runs `langfuse/langfuse:2.95.11`.
- The current graph route implementation sends factual/comparison to hybrid retrieval and aggregation/multi-hop to graph retrieval. The ablation runner must identify the vector-routed subset from actual route/retrieval metadata instead of assuming type alone.

## External References

- Ragas stable docs list RAG metrics including context precision, context recall, response relevancy, and faithfulness, and its `evaluate()` API runs metrics against an evaluation dataset with optional LLM/embedding overrides. This supports a report runner, not a hard CI gate, because judge-backed metrics can call an LLM.
- Langfuse instrumentation docs recommend context managers for manual spans and child observations. Observation types include `span`, `generation`, `retriever`, and `guardrail`, which map cleanly to the query graph nodes and the synthesis LLM call.
- Current Langfuse Python SDK docs describe SDK v3 and state a self-hosted platform requirement of Langfuse platform `>=3.125.0`. Because compose currently pins `langfuse/langfuse:2.95.11`, Phase 7 should default to the legacy Python SDK v2 line (`langfuse~=2.x`) and must not upgrade the container to v3. A v3 Langfuse platform upgrade brings new infrastructure concerns and belongs to a later delivery-polish phase.
- Qdrant hybrid query docs show dense and sparse prefetches combined with fusion queries such as RRF. The current implementation follows this pattern; eval-only dense and sparse modes can reuse the same embedding and access-filter plumbing while omitting the other prefetch.
- `bm25s` is a lightweight Python BM25 implementation with in-memory indexing and retrieval APIs. It matches the architecture note that BM25 is an eval-only baseline and avoids introducing Elasticsearch or a production lexical service.

## Planning Implications

- Corpus freeze must precede golden authoring. The plan sequence should author and commit the 16 Russian demo documents, hash/freeze that committed snapshot, index it, and only then author `golden_ru.jsonl`.
- RAGAS quality evaluation runs once over the full 40-question golden set through production `/v1/query`; it must not be limited to vector questions. "Hybrid+reranker" in this context means the normal production query configuration with reranker enabled for vector routes, while graph-routed questions still use graph retrieval.
- The five-way retrieval ablation is a cheap retrieval-only matrix for vector-routed records. Graph route quality is reported separately because graph retrieval uses a different mechanism.
- Langfuse and diagnostics code should land early so eval reports can include trace/latency evidence when available. RAGAS quality evaluation remains independent of Langfuse and must still produce its report if tracing is disabled or blocked.
- Generated reports should be committed under `ai-service/eval/reports/`, while the narrative closeout should live in `.planning/phases/07-evaluation-observability/07-EVAL-SUMMARY.md`.

## Sources

- Ragas available metrics: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/
- Ragas `evaluate()`: https://docs.ragas.io/en/stable/references/evaluate/
- Langfuse SDK instrumentation: https://langfuse.com/docs/observability/sdk/instrumentation
- Langfuse SDK overview and self-hosting note: https://langfuse.com/docs/observability/sdk/overview
- Langfuse observation types: https://langfuse.com/docs/observability/features/observation-types
- Qdrant hybrid queries: https://qdrant.tech/documentation/search/hybrid-queries/
- `bm25s`: https://github.com/xhluca/bm25s

## Research Complete

The plan should be split into a stability wave, code/instrumentation/harness waves, and eval execution waves. Do not run RAGAS or ablation before the frozen corpus, retrieval-mode code, and judge/tracing wiring are present.
