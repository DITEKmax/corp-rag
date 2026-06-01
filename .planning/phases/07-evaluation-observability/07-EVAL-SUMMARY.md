# Phase 07 Final Evaluation Summary

Phase 7 produced the Russian evaluation baseline, retrieval ablation matrix, injection-probe safety measurement, and observability readiness evidence for `ru-aviation-logistics-v1`.

## Corpus

| Field | Value |
|---|---|
| Corpus version | `ru-aviation-logistics-v1` |
| Corpus hash | `0bea14fee10b2ea99d08159e0684fcb7c9e5b20edd8662528bfa4cb1e9ff6984` |
| Indexed corpus | 16 golden documents in Qdrant and Neo4j |
| Golden set | 40 Russian records: 30 answerable, 10 out-of-scope/guard |

## RAGAS Baseline

Source: `ai-service/eval/reports/ragas_ru.{md,json,csv}`, baseline commit `4d23614`.

| Metric | Value | Threshold | Status |
|---|---:|---:|---|
| record_count | 40 | - | recorded |
| answered_count | 18 | - | recorded |
| outcome_accuracy | 0.6250 | 0.80 | below threshold |
| citation_doc_recall | 0.6000 | 0.70 | below threshold |
| faithfulness | 0.9630 | 0.75 | pass |
| answer_relevancy | 0.8650 | 0.75 | pass |
| context_precision | 0.9861 | 0.60 | pass |
| context_recall | 1.0000 | 0.60 | pass |

Interpretation: grounded answers are faithful and complete when the system answers, but router/graph failures still suppress many answerable questions. RAGAS is report-only; no hard CI gate was added for stochastic judge metrics.

## Retrieval Ablation

Source: `ai-service/eval/reports/ablation_ru.{md,json,csv}`, commit `b221f58`.

| Mode | Records | recall@5 | recall@10 | MRR |
|---|---:|---:|---:|---:|
| `bm25` | 15 | 0.8778 | 0.9667 | 0.9111 |
| `dense` | 15 | 0.9556 | 1.0000 | 0.9667 |
| `sparse` | 15 | 0.9778 | 1.0000 | 1.0000 |
| `hybrid` | 15 | 0.9778 | 1.0000 | 1.0000 |
| `hybrid+reranker` | 15 | 0.9778 | 1.0000 | 1.0000 |

BM25 is materially weaker than learned retrieval, supporting the thesis: bge-m3 learned sparse превосходит классический BM25. Sparse, hybrid, and hybrid+reranker hit the small-corpus ceiling at recall@10=1.0 and MRR=1.0. The reranker adds no measurable lift on 16 indexed docs and 15 vector-routed questions because relevant documents are already in top-5; this is a scale limitation, not evidence against reranking on larger/noisier corpora.

Graph route is separate from vector retrieval: 14 graph-routed records, recall@10=0.2857, MRR=0.2857, and 10 no-evidence refusals. This aligns with the known Phase 8 multi-hop graph debt.

## Injection Probes

Source: `ai-service/eval/reports/injection_ru.{md,json}`. This is measure-only evidence; guard rules were not changed.

| Category | Blocked | Total | Block-rate | Guard-blocked | Guard-block-rate | Findings |
|---|---:|---:|---:|---:|---:|---:|
| `prompt_injection` | 3 | 3 | 1.0000 | 3 | 1.0000 | 0 |
| `jailbreak` | 3 | 3 | 1.0000 | 3 | 1.0000 | 0 |
| `data_exfiltration` | 3 | 3 | 1.0000 | 0 | 0.0000 | 3 |
| `citation_bypass` | 3 | 3 | 1.0000 | 0 | 0.0000 | 0 |

Interpretation: all probes were blocked/resisted, but data-exfiltration requests are not currently guard-blocked; they were refused as unsupported/no-evidence. That is recorded as a finding rather than fixed in this plan. Citation-bypass probes did not bypass the `[N]` contract; one answered case kept valid citations and the other two refused.

## Langfuse And Diagnostics

Langfuse live evidence is confirmed after loading real local keys into `python-ai`: `/diagnostics.langfuse_configured=true`, `/diagnostics.langfuse_reachable=true`, and the Langfuse UI shows root traces with child spans. The user visually confirmed trace `fd4a4517-e538-46b0-a98c-b4e97ec2783c`: `input_guard -> route -> hybrid_retrieval -> parent_resolve -> rerank -> pack_context -> synthesize -> synthesize_generation -> output_guard -> finalize`, with `rerank` dominating latency at 16.31s of 21.82s and generation usage 3470 input tokens / 51 output tokens.

Project: `corp-rag-project` (`cmpvj5dqs00062cri1t8hum3r`).

| Path | Outcome | Route | Trace |
|---|---|---|---|
| answered factual | answered | `FACTUAL` / `HYBRID` | http://localhost:3000/project/cmpvj5dqs00062cri1t8hum3r/traces/52b2349d-1968-41d2-88a1-c46d0803187f |
| refused no-evidence | refused | `FACTUAL` / `HYBRID` | http://localhost:3000/project/cmpvj5dqs00062cri1t8hum3r/traces/fd4a4517-e538-46b0-a98c-b4e97ec2783c |
| guard-blocked injection | refused_guard | `UNSUPPORTED` | http://localhost:3000/project/cmpvj5dqs00062cri1t8hum3r/traces/60147b2b-a28c-40f4-9f3c-1786ef99fa8e |
| graph-routed aggregation | answered | `AGGREGATION` / `GRAPH` | http://localhost:3000/project/cmpvj5dqs00062cri1t8hum3r/traces/e34128ec-fe54-4a37-88fa-f652d0f14c57 |

Diagnostics counters moved during live OPS-01 verification: before `query_count=0`, after `query_count=5`, `answered_count=2`, `refused_no_evidence_count=1`, `guard_blocked_count=1`, `reranker_degraded_count=0`. Five queries were counted because the first refusal candidate routed as unsupported, then a replacement in-domain no-evidence query was run.

## Phase 8 Handoff

- Multi-hop graph retrieval remains the main answerability debt: graph route recall@10 is 0.2857.
- `ru-factual-009` is a false-UNSUPPORTED/router failure and belongs with the same Phase 8 router debt as the 7.1 multi-hop findings.
- Data-exfiltration probes should receive explicit guard classification instead of falling through to unsupported/no-evidence refusal.
- Stable RAGAS judge behavior remains operationally important; keep RAGAS report-only until judge variance and retry behavior are better characterized.
- Live Langfuse demo is now confirmed for answered, no-evidence refusal, guard-blocked, and graph-routed query paths.

## Artifacts

- `ai-service/eval/reports/ragas_ru.md`
- `ai-service/eval/reports/ragas_ru.json`
- `ai-service/eval/reports/ragas_ru.csv`
- `ai-service/eval/reports/ablation_ru.md`
- `ai-service/eval/reports/ablation_ru.json`
- `ai-service/eval/reports/ablation_ru.csv`
- `ai-service/eval/reports/injection_ru.md`
- `ai-service/eval/reports/injection_ru.json`

## Verification

- PASS: injection runner unit tests pass.
- PASS: live injection probes produced `injection_ru.md` and `injection_ru.json`.
- PASS: diagnostics counters moved after live probes.
- PASS: Langfuse live trace UI verification confirmed root traces, graph/query child spans, and synthesis generation observations.
