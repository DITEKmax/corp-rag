# ADR-008: Guard Architecture

- **Status:** Accepted
- **Date:** 2026-05-19
- **Affected components:** Python input guard, output guard, corpus sanitizer reuse, OpenRouter classifier, Java audit metadata

## Context

The system must reject prompt injection and unsafe requests before retrieval, while also validating generated answers before Java returns them to the browser. Phase 04 already has corpus sanitizer regexes; Phase 05 can reuse those signatures but needs query-specific verdicts and output citation checks.

## Decision

Use a two-layer guard architecture.

1. Input guard runs before retrieval. Tier-0 rules detect prompt injection, unsafe policy content, out-of-scope requests, and obvious secret/system-prompt extraction attempts. If rules are inconclusive, optional Tier-1 DeepSeek V4 Flash classification can return a structured guard verdict.
2. Output guard runs after synthesis. It validates citation references, uncited factual claims, unsafe leakage patterns, and evidence safety before returning the response.
3. Guard patterns live as code constants in Phase 05, reusing Phase 04 sanitizer signatures where appropriate.
4. Retrieved chunks with `isSanitized=false` are downranked by `AI_FLAGGED_CHUNK_SCORE_MULTIPLIER` instead of excluded. If final evidence contains only flagged chunks, output guard refuses with `unsafe_evidence_only`.

## Alternatives

### External guard-pattern configuration
- Pro: Operators could tune patterns without deployment.
- Con: Adds runtime configuration risk before the project has guard evaluation tooling.
- Verdict: Rejected for Phase 05; code constants are simpler to test and defend.

### Single pre-retrieval guard only
- Pro: Less implementation work.
- Con: Does not catch uncited or unsafe generated output.
- Verdict: Rejected because answer synthesis can still fail after safe input.

### Exclude flagged chunks from retrieval
- Pro: Conservative and easy to explain.
- Con: Phase 04 decided suspicious-but-indexable chunks should remain searchable with lower trust, not disappear silently.
- Verdict: Rejected; downranking preserves recall while marking risk.

## Consequences

Positive:

- Unsafe inputs avoid storage and LLM work.
- Unsafe or uncited outputs are blocked before Java returns them.
- Guard behavior is testable without live external services.

Tradeoffs:

- Some safe borderline questions may refuse.
- Output guard heuristics must be tuned against false positives.
- Guard metadata must remain visible in `QueryResponse` and Problem Details.

## References

- `.planning/phases/05-retrieval-guards-query-api/05-CONTEXT.md` decisions D-158 through D-169.
- `ai-service/src/corp_rag_ai/pipeline/ingestion/corpus_sanitizer.py`.
