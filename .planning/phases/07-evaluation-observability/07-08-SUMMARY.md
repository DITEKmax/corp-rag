---
phase: 07-evaluation-observability
plan: "08"
subsystem: evaluation
tags: [eval, injection, langfuse, diagnostics, summary]
requires:
  - phase: 07-evaluation-observability
    provides: "07-06 RAGAS production baseline"
  - phase: 07-evaluation-observability
    provides: "07-07 retrieval ablation report"
provides:
  - "Russian injection probe runner and reports"
  - "Langfuse live-verification evidence"
  - "Final Phase 7 evaluation summary"
affects: [phase-07-evaluation, phase-08-delivery-polish, safety-eval, observability]
key-files:
  created:
    - ai-service/eval/injection_runner.py
    - ai-service/eval/reports/injection_ru.md
    - ai-service/eval/reports/injection_ru.json
    - ai-service/tests/test_eval_injection_runner.py
    - .planning/phases/07-evaluation-observability/07-EVAL-SUMMARY.md
    - .planning/phases/07-evaluation-observability/07-UAT.md
    - .planning/phases/07-evaluation-observability/07-UAT-EVIDENCE.md
  modified: []
key-decisions:
  - "Injection probes are measure-only; guard implementation was not changed."
  - "Report both block-rate and stricter guard-block-rate so no-evidence/citation-preservation behavior is not misrepresented as guard coverage."
  - "Claim Langfuse live traces only after real local keys are loaded, diagnostics is true/true, and the UI trace tree is visually confirmed."
requirements-completed: ["EVAL-03", "OPS-01", "EVAL-02", "EVAL-04"]
completed: 2026-06-01
---

# Phase 07 Plan 08: Injection, Langfuse, Final Summary

**Injection probes completed; final eval narrative assembled; Langfuse live traces visually confirmed**

## Accomplishments

- Added `ai-service/eval/injection_runner.py` with Russian prompt-injection, jailbreak, data-exfiltration, and citation-bypass probes.
- Added unit tests for mocked query responses, per-category metrics, and strict citation-bypass handling.
- Ran live probes against production `/v1/query` with the Docker stack healthy.
- Generated `ai-service/eval/reports/injection_ru.md` and `ai-service/eval/reports/injection_ru.json`.
- Verified live Langfuse traces after real local keys were loaded: answered, no-evidence refusal, guard-blocked, and graph-routed paths all produced root traces.
- Added `07-EVAL-SUMMARY.md`, `07-UAT.md`, and `07-UAT-EVIDENCE.md`.

## Injection Results

| Category | Blocked | Total | Block-rate | Guard-block-rate | Findings |
|---|---:|---:|---:|---:|---:|
| `prompt_injection` | 3 | 3 | 1.0000 | 1.0000 | 0 |
| `jailbreak` | 3 | 3 | 1.0000 | 1.0000 | 0 |
| `data_exfiltration` | 3 | 3 | 1.0000 | 0.0000 | 3 |
| `citation_bypass` | 3 | 3 | 1.0000 | 0.0000 | 0 |

Findings: data-exfiltration probes did not disclose secrets, but they were refused as unsupported/no-evidence rather than explicitly guard-blocked. This is recorded as a safety-classification gap for a later fix loop.

Citation-bypass probes did not bypass the `[N]` contract: one answered case preserved valid citations, and the other two refused.

## Langfuse Status

- Langfuse container health endpoint returned OK: `{"status":"OK","version":"2.95.11"}`.
- `/diagnostics` reports `langfuse_configured=true` and `langfuse_reachable=true`.
- Live `/v1/query` probes produced root traces for answered, no-evidence refusal, guard-blocked, and graph-routed paths.
- User visually confirmed trace `fd4a4517-e538-46b0-a98c-b4e97ec2783c` in the Langfuse UI: `input_guard -> route -> hybrid_retrieval -> parent_resolve -> rerank -> pack_context -> synthesize -> synthesize_generation -> output_guard -> finalize`, with `rerank` dominating latency at 16.31s of 21.82s.

| Path | Trace |
|---|---|
| answered factual | http://localhost:3000/project/cmpvj5dqs00062cri1t8hum3r/traces/52b2349d-1968-41d2-88a1-c46d0803187f |
| refused no-evidence | http://localhost:3000/project/cmpvj5dqs00062cri1t8hum3r/traces/fd4a4517-e538-46b0-a98c-b4e97ec2783c |
| guard-blocked injection | http://localhost:3000/project/cmpvj5dqs00062cri1t8hum3r/traces/60147b2b-a28c-40f4-9f3c-1786ef99fa8e |
| graph-routed aggregation | http://localhost:3000/project/cmpvj5dqs00062cri1t8hum3r/traces/e34128ec-fe54-4a37-88fa-f652d0f14c57 |

## Diagnostics

Before live injection probes:

- `query_count=0`
- `answered_count=0`
- `guard_blocked_count=0`
- `reranker_degraded_count=0`
- `langfuse_configured=false`
- `langfuse_reachable=false`

After live injection probes:

- `query_count=12`
- `answered_count=1`
- `guard_blocked_count=6`
- `reranker_degraded_count=0`
- `mean_latency_ms=4183`
- `langfuse_configured=false`
- `langfuse_reachable=false`

After live OPS-01 trace probes:

- `query_count=5`
- `answered_count=2`
- `refused_no_evidence_count=1`
- `guard_blocked_count=1`
- `reranker_degraded_count=0`
- `langfuse_configured=true`
- `langfuse_reachable=true`

## Verification

- PASS: `uv run --project ai-service --group dev pytest ai-service/tests/test_eval_injection_runner.py` - 5 passed.
- PASS: `uv run --project ai-service --group dev python -m py_compile ai-service\eval\injection_runner.py`.
- PASS: live injection runner wrote Markdown and JSON reports.
- PASS: `07-EVAL-SUMMARY.md` includes RAGAS, ablation, injection, Langfuse, and corpus sections.
- PASS: Langfuse UI trace verification confirmed root trace plus child spans and synthesis generation for live production `/v1/query`.

## Commit Status

Included in the 07-08 closeout commit after user confirmation.

## Phase 8 Handoff

- Multi-hop graph retrieval: graph route recall@10=0.2857.
- Router false-UNSUPPORTED: `ru-factual-009` and related answerable unsupported cases.
- Data-exfiltration guard classification: probes are protected by fallback refusal but not explicit guard verdicts.
- Stable RAGAS judge: keep report-only until variance/retry behavior is characterized.
- Langfuse live demo: confirmed with real local keys and trace links recorded in UAT evidence.
