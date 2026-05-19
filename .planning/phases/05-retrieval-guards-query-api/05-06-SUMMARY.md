---
phase: 05-retrieval-guards-query-api
plan: "06"
subsystem: answer-synthesis
tags: [openrouter, deepseek, synthesis, output-guard, degradation-policy, citations]
requires:
  - phase: 05-retrieval-guards-query-api
    provides: "05-05 PackedContext, CitationDrafts, reranker metadata, and retrieval failure states"
provides:
  - "DeepSeek/OpenRouter strict-schema cited answer synthesizer"
  - "Output guard for citation refs, uncited factual claims, leak patterns, and unsafe evidence-only answers"
  - "Central degradation policy matrix for dependency/evidence states"
affects: [phase-05-query-api, phase-06-chat, phase-07-evaluation]
tech-stack:
  added: []
  patterns: [escaped evidence sentinels, strict JSON synthesis, citation compliance guard, executable degraded-mode matrix]
key-files:
  created:
    - ai-service/src/corp_rag_ai/pipeline/generation/synthesizer.py
    - ai-service/src/corp_rag_ai/pipeline/generation/degradation_policy.py
    - ai-service/src/corp_rag_ai/pipeline/generation/prompts/synthesis_v1.md
    - ai-service/src/corp_rag_ai/pipeline/guards/output_guard.py
    - ai-service/tests/test_synthesizer.py
    - ai-service/tests/test_output_guard.py
    - ai-service/tests/test_query_degradation_policy.py
  modified:
    - ai-service/src/corp_rag_ai/domain/query.py
    - ai-service/src/corp_rag_ai/domain/guard.py
key-decisions:
  - "Synthesis prompt assembly uses per-request sentinel markers plus HTML-escaped packed evidence."
  - "Malformed or unavailable OpenRouter synthesis fails closed with generation_unavailable."
  - "Output guard blocks answered=true for invalid refs, missing refs, leak-like output, or unsafe-evidence-only context."
  - "Degraded-mode decisions are centralized in apply_degradation rather than scattered through generation code."
patterns-established:
  - "SynthesisResult is the pre-guard generated answer candidate."
  - "OutputGuard returns GuardVerdict with OUTPUT_CHECK tier for post-generation failures."
  - "DependencyState and EvidenceState drive a testable D-207 through D-213 matrix."
requirements-completed: ["AGT-03", "SEC-01", "RET-04"]
duration: 5 min
completed: 2026-05-19
---

# Phase 05 Plan 06: Synthesis, Output Guard, And Degradation Summary

**Strict cited answer synthesis with output citation checks and executable degradation policy**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-19T21:04:23Z
- **Completed:** 2026-05-19T21:09:05Z
- **Tasks:** 3 completed
- **Files modified:** 10 tracked files

## Accomplishments

- Added a DeepSeek/OpenRouter answer synthesizer using strict JSON schema and response-healing, returning `{answered, answer, citation_indexes, confidence_hint}`.
- Escaped packed evidence and wrapped it in unique sentinels so retrieved XML-like text cannot break prompt boundaries.
- Added output guard checks for invalid citation refs, uncited factual/aggregation answers, secret-like leakage, and unsafe-evidence-only final context.
- Added `apply_degradation` with named dependency/evidence states covering generation, vector, graph, reranker, embedding, no-evidence, and weak-evidence decisions.
- Added tests for every D-207 through D-213 degraded-mode row and for invalid/uncited generated answers.

## Task Commits

1. **Task 1: OpenRouter synthesis client and citation schema** - `4ba4eb9` (`feat(05-06): add cited answer synthesizer`)
2. **Task 2: Output guard and citation compliance** - `3a95f2f` (`feat(05-06): add output guard`)
3. **Task 3: Confidence, refusal, and degraded-mode matrix** - `45513c6` (`feat(05-06): add degradation policy`)

## Files Created/Modified

- `ai-service/src/corp_rag_ai/pipeline/generation/synthesizer.py` - strict-schema DeepSeek answer synthesis and prompt rendering.
- `ai-service/src/corp_rag_ai/pipeline/guards/output_guard.py` - post-generation citation/leak/evidence guard.
- `ai-service/src/corp_rag_ai/pipeline/generation/degradation_policy.py` - executable dependency/evidence matrix.
- `ai-service/src/corp_rag_ai/domain/query.py` and `domain/guard.py` - new refusal/guard reasons.
- Focused tests for synthesizer, output guard, and degradation policy.

## Decisions Made

- Synthesis failures return a safe domain result rather than raising raw provider exceptions.
- The uncited-claim heuristic is deliberately simple for MVP: answered factual-looking text without refs is blocked.
- Weak evidence below 0.4 refuses with an actionable message instead of generating a fragile answer.

## Deviations from Plan

None - plan executed as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

None.

## Verification

- `uv run --project ai-service --group dev pytest ai-service/tests/test_synthesizer.py ai-service/tests/test_entity_extractor.py ai-service/tests/test_output_guard.py ai-service/tests/test_query_input_guard.py ai-service/tests/test_query_degradation_policy.py` - 41 passed.
- `uv run --project ai-service --group dev pytest ai-service/tests/test_synthesizer.py ai-service/tests/test_output_guard.py ai-service/tests/test_query_degradation_policy.py` - 19 passed.

## User Setup Required

None - no new external service configuration required.

## Next Phase Readiness

Plan 05-07 can wire the full Python `/v1/query` path by combining input guard, router, retrievers, parent/rerank/context, synthesizer, output guard, and contract response mapping.

---
*Phase: 05-retrieval-guards-query-api*
*Completed: 2026-05-19*
