# Phase 7: Evaluation & Observability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-06-01
**Phase:** 7-Evaluation & Observability
**Areas discussed:** Golden dataset shape, Metric/report contract, Ablation variants, Observability surface

---

## Golden Dataset Shape

| Option | Description | Selected |
|--------|-------------|----------|
| Russian-first monolingual | Score the real demo story: Russian aviation/logistics corpus, Russian questions, Russian reference answers. | yes |
| Bilingual scored set | Mix Russian and English scored examples. Rejected because English Phase 5 docs are not part of the demo story. | |
| English sanity smoke | Optional non-scored English smoke file outside the golden dataset. | |
| Exact chunk-id assertions | Hard-match expected chunks. Rejected as brittle across re-indexing and synthetic corpus regeneration. | |

**User's choice:** Russian-first monolingual scored dataset, 40 questions total, split 10 factual / 10 aggregation / 10 multi-hop / 10 out-of-scope. Out-of-scope splits approximately 6 absent/no-evidence and 4 guard-refusal cases.

**Notes:** Expected document IDs are authoritative for recall@k/MRR. `expected_chunk_hint` is advisory only. Dataset lives at `ai-service/eval/golden/golden_ru.jsonl`; corpus version/hash lives in `golden_ru.meta.json`. Corpus freeze sequence is locked: regenerate 16 docs, commit them, index them, then author golden answers.

---

## Metric/Report Contract

| Option | Description | Selected |
|--------|-------------|----------|
| Demo artifact and regression baseline | Emit reports and JSON summaries; flag deviations without hard-failing stochastic judge metrics. | yes |
| Hard CI gate for all metrics | Rejected because RAGAS depends on a non-deterministic paid/network LLM judge. | |
| Deterministic gate only | Retrieval metrics and injection block-rate may be asserted by non-LLM tests if useful. | partial |

**User's choice:** Reports are committed demo artifacts and regression baselines, not hard CI gates.

**Notes:** Initial targets: faithfulness >= 0.85, answer relevancy >= 0.80, context precision/recall reported without hard floors, recall@5/recall@10/MRR over expected docs, prompt-injection/exfil block-rate target >= 95%, citation-bypass target 100%. The guard must never be tuned unsafely just to hit a number. Code/data live under `ai-service/eval/`; reports under `ai-service/eval/reports/`; phase narrative summary under `.planning/phases/07-evaluation-observability/07-EVAL-SUMMARY.md`.

---

## Ablation Variants

| Option | Description | Selected |
|--------|-------------|----------|
| Five-vector retrieval matrix | `bm25`, `dense`, `sparse`, `hybrid`, `hybrid+reranker` on retrieval metrics. | yes |
| Full RAGAS across every variant | Rejected due to 5x LLM-judge cost for little narrative value. | |
| Production retrieval-mode toggle | Rejected because eval modes must not leak into `/v1/query` or production behavior. | |
| Separate graph-route report | Evaluate graph routes independently from vector ablation. | yes |

**User's choice:** Build eval-only retrieval mode support and BM25 harness, run cheap retrieval metrics across five vector variants, and run RAGAS once on production `hybrid+reranker`.

**Notes:** Current query retrieval is hardcoded dense+sparse+RRF, so code work is required before ablation can run. BM25 stays eval-only. Learned sparse and BM25 remain distinct. Graph routes use different mechanics and must not be averaged into vector ablation scores.

---

## Observability Surface

| Option | Description | Selected |
|--------|-------------|----------|
| Langfuse plus lightweight diagnostics | Add full query graph spans and minimal counters through `/diagnostics`. | yes |
| Prometheus/Grafana stack | Rejected as out of scope for MVP OPS-01. | |
| Frontend admin observability screen | Rejected as Phase 6 scope creep; use Langfuse UI at `:3000`. | |

**User's choice:** Add Langfuse dependency/client and one root trace per `/v1/query`, with child spans for each query graph node and LLM synthesis traced as a generation.

**Notes:** Span attributes carry retrieval metadata and guard verdicts. Prefer explicit async span context managers over decorators if LangGraph nodes do not cooperate. Verify in Docker. Expand `/diagnostics` with aggregate counters and Langfuse health, but keep it read-only and unauthenticated-internal.

---

## Cross-Cutting Sequence

| Wave | Description | Selected |
|------|-------------|----------|
| Wave 0 stability | Memory contour around 8-9 GiB, first-turn cold-start diagnosis, model pre-warm. | yes |
| Code wave before eval execution | Langfuse instrumentation, eval-only ablation modes, BM25 harness, corpus regen/freeze/index. | yes |
| Eval execution waves | Golden authoring, RAGAS run, ablation run, injection run, report assembly. | yes |

**User's choice:** Do not schedule "run RAGAS" or ablation execution before the corpus is frozen and judge/instrumentation wiring is ready.

**Notes:** This sequence should shape the downstream plan waves.

---

## the agent's Discretion

- Exact eval runner CLI names, module boundaries, JSON summary shape, and report filenames.
- Exact BM25 library or implementation, provided it stays eval-only and uses the same frozen corpus.
- Exact Langfuse helper/client abstraction, provided required spans appear in Docker.
- Exact memory value within the 8-9 GiB range and pre-warm mechanics based on observed behavior.

## Deferred Ideas

- Bilingual or English scored evaluation dataset.
- Hard CI gates for stochastic RAGAS judge metrics.
- Exact chunk-id assertions as hard golden requirements.
- Production retrieval-mode API or global env toggle.
- Full RAGAS run across all five variants.
- Prometheus/Grafana stack.
- New frontend/admin observability screen.
- Guard tuning solely to satisfy injection probe percentages.
