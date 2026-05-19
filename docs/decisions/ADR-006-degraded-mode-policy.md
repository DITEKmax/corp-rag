# ADR-006: Degraded Mode Policy

- **Status:** Accepted
- **Date:** 2026-05-19
- **Affected components:** Python AI Service, retrieval pipeline, answer synthesis, diagnostics, Java audit metadata

## Context

The query path depends on Qdrant, Neo4j, local embedding and reranking models, and OpenRouter. Some failures can still produce a trustworthy answer; others would create a false sense of correctness. Phase 05 must make this matrix explicit instead of hiding missing dependencies behind vague answers.

## Decision

Use fail-loud degraded mode. Every dependency loss either produces an explicit `answered=false` reason or a response with `retrievalMeta.degradationWarnings`.

Concrete matrix:

1. OpenRouter synthesis unavailable: `answered=false`, error `generation_unavailable`.
2. Query embedding unavailable: `answered=false`, error `embedding_unavailable`.
3. Qdrant unavailable for `FACTUAL` or `COMPARISON`: `answered=false`, error `vector_retrieval_unavailable`.
4. Qdrant unavailable for `AGGREGATION` or `MULTI_HOP`: soft-degrade to Neo4j-only evidence and warn if accessible graph evidence exists.
5. Neo4j unavailable for `FACTUAL`: continue because factual retrieval is Qdrant-primary.
6. Neo4j unavailable for `AGGREGATION` or `MULTI_HOP`: `answered=false`, error `graph_retrieval_unavailable`.
7. Reranker unavailable: use raw retrieval order sliced to final top-N, set `rerankerUsed=false`, and warn.

## Alternatives

### Silent fallback
- Pro: Higher apparent availability.
- Con: Users cannot tell when answer quality is lower, and Java audit cannot distinguish normal from degraded results.
- Verdict: Rejected because it undermines trust and makes UAT misleading.

### Hard fail on any dependency loss
- Pro: Simple to reason about.
- Con: Throws away valid graph-only aggregation and factual-without-Neo4j cases.
- Verdict: Rejected because some degradation is safe when it is explicit.

### Best-effort generation with weak evidence
- Pro: More answered queries.
- Con: Encourages hallucination when evidence is thin or unavailable.
- Verdict: Rejected; weak evidence below confidence threshold must refuse.

## Consequences

Positive:

- Degraded answers are auditable.
- Verification can test each failure mode with mocks.
- Demo behavior is easier to explain because every fallback has a reason.

Tradeoffs:

- More `answered=false` responses in local development.
- UI and Java audit must preserve warning metadata.
- Tests need to cover the full matrix.

## References

- `.planning/phases/05-retrieval-guards-query-api/05-CONTEXT.md` decisions D-206 through D-215.
- `contracts/openapi/ai-service-v1.yaml` `RetrievalMeta`.
