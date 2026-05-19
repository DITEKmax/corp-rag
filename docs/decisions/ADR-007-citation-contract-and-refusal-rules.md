# ADR-007: Citation Contract And Refusal Rules

- **Status:** Accepted
- **Date:** 2026-05-19
- **Affected components:** OpenAPI contracts, Python retrieval/generation, Java chat API, Phase 06 citation viewer

## Context

Phase 04 stores child chunks as deterministic UUID retrieval units in Qdrant and parent chunks as larger context units in AI Postgres. The older synthetic citation ID shape no longer matches the indexed data. Phase 05 also needs strict refusal behavior so generated answers are grounded and defensible.

## Decision

Citations are child-level references. `Citation.chunkId` is a UUID child chunk ID, not a parent ID or display-only synthetic value.

Required citation fields:

1. `documentId`
2. `documentTitle`
3. `chunkId`
4. `sectionPath`
5. `quote` and optional short `snippet`
6. nullable `pageNumber`
7. `score`
8. `accessLevel`

Generation must use inline `[N]` references that map to the returned citations array. Output validation refuses answers with invalid citation references, missing citations for factual claims, unsafe evidence-only output, weak evidence, unsupported routes, or zero permitted retrieval results.

## Alternatives

### Parent-level citations
- Pro: Parent chunks are easier to read as context.
- Con: Parent chunks are not the retrieval unit or source-viewer key; they blur which exact child evidence supported a claim.
- Verdict: Rejected because Phase 06 needs stable clickable child evidence.

### Synthetic display-only chunk IDs
- Pro: Human-readable examples.
- Con: They do not exist in Phase 04 storage and would require a mapping layer.
- Verdict: Rejected as a stale contract artifact.

### Citationless aggregation answers
- Pro: Counts and lists can look self-evident.
- Con: Aggregations still derive from documents and must remain auditable.
- Verdict: Rejected; all factual answers require citations.

## Consequences

Positive:

- Contract fields match actual Qdrant point IDs.
- Phase 06 can fetch citation detail without ID translation.
- Refusals are deterministic when evidence is absent, weak, or unsafe.

Tradeoffs:

- The LLM prompt and output guard must enforce strict `[N]` citation format.
- Parent context packing must retain child citation provenance.
- Existing generated models and examples must be regenerated after contract changes.

## References

- `.planning/phases/05-retrieval-guards-query-api/05-CONTEXT.md` decisions D-154, D-186 through D-205.
- `contracts/openapi/ai-service-v1.yaml` `Citation`, `ChunkDetail`, and `QueryResponse`.
