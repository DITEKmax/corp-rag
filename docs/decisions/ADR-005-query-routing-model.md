# ADR-005: Query Routing Model

- **Status:** Accepted
- **Date:** 2026-05-19
- **Affected components:** Python AI Service, query pipeline, OpenRouter integration, retrieval routing

## Context

Phase 05 must route user questions before retrieval so unsupported, unsafe, or low-confidence requests do not waste Qdrant, Neo4j, reranker, or LLM synthesis work. The project also needs routing behavior that can be explained in a diploma defense and tested without a labeled classifier dataset.

The supported routes are the contract routes: `FACTUAL`, `AGGREGATION`, `MULTI_HOP`, `COMPARISON`, and `UNSUPPORTED`. Java remains the authority for identity and access; Python only receives the resolved `AccessFilter` and decides which retrieval path to attempt under that filter.

## Decision

Use a rules-first router with DeepSeek V4 Flash JSON-schema fallback.

Concrete behavior:

1. Deterministic rules classify obvious factual, aggregation, multi-hop, comparison, and unsupported requests with confidence `1.0`.
2. If rules cannot classify the request, call DeepSeek V4 Flash through OpenRouter with a strict JSON schema returning `{query_type, confidence}`.
3. If fallback confidence is below `AI_ROUTER_CONFIDENCE_THRESHOLD` (default `0.65`), route as `UNSUPPORTED`.
4. If the classifier dependency is unavailable, degrade to rules-only routing; if rules still cannot decide, return `UNSUPPORTED` before retrieval.

## Alternatives

### Trained classifier
- Pro: Fast and independent from hosted LLM availability.
- Con: This project does not have a defended labeled dataset, evaluation corpus, or model-ops budget.
- Verdict: Rejected for Phase 05; trained classifier work would look more scientific while being less defensible.

### LLM-only routing
- Pro: Simple to implement.
- Con: Every query pays external latency and quota, and deterministic cases become harder to test.
- Verdict: Rejected because rules cover common MVP cases more cheaply and predictably.

### Retrieve first, route later
- Pro: Can use evidence to disambiguate questions.
- Con: Violates the requirement that unsupported or unsafe queries short-circuit before storage and LLM work.
- Verdict: Rejected.

## Consequences

Positive:

- The common path is deterministic and unit-testable.
- Hosted LLM failures do not break obvious routes.
- Unsupported requests avoid retrieval and generation.

Tradeoffs:

- Rules need maintenance as query patterns evolve.
- Borderline questions may be classified as `UNSUPPORTED` rather than answered.
- Router metadata must expose whether fallback was used so Java audit and UAT can explain degraded outcomes.

## References

- `.planning/phases/05-retrieval-guards-query-api/05-CONTEXT.md` decisions D-170 through D-180.
- `contracts/openapi/ai-service-v1.yaml` `QueryRoute` and `RetrievalMeta`.
