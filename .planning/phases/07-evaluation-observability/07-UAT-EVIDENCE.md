# Phase 07 UAT Evidence

Evidence captured on 2026-06-01 against the local Docker stack.

## Stack

`docker compose -f infra/docker-compose.yml ps` showed all nine services running and healthy:

- frontend
- java-backend
- langfuse
- minio
- neo4j
- postgres
- python-ai
- qdrant
- rabbitmq

## RAGAS

Baseline report: `ai-service/eval/reports/ragas_ru.{md,json,csv}`.

| Metric | Value |
|---|---:|
| record_count | 40 |
| answered_count | 18 |
| faithfulness | 0.9630 |
| answer_relevancy | 0.8650 |
| context_precision | 0.9861 |
| context_recall | 1.0000 |

No hard CI gate was added for RAGAS metrics.

## Ablation

Ablation report: `ai-service/eval/reports/ablation_ru.{md,json,csv}`.

| Mode | recall@5 | recall@10 | MRR |
|---|---:|---:|---:|
| `bm25` | 0.8778 | 0.9667 | 0.9111 |
| `dense` | 0.9556 | 1.0000 | 0.9667 |
| `sparse` | 0.9778 | 1.0000 | 1.0000 |
| `hybrid` | 0.9778 | 1.0000 | 1.0000 |
| `hybrid+reranker` | 0.9778 | 1.0000 | 1.0000 |

Graph route was reported separately: recall@10=0.2857, MRR=0.2857.

## Injection Probes

Command:

```powershell
uv run --project ai-service --group dev python -m eval.injection_runner --base-url http://localhost:8000
```

Output reports:

- `ai-service/eval/reports/injection_ru.md`
- `ai-service/eval/reports/injection_ru.json`

| Category | Blocked | Total | Block-rate | Guard-block-rate | Finding |
|---|---:|---:|---:|---:|---|
| `prompt_injection` | 3 | 3 | 1.0000 | 1.0000 | none |
| `jailbreak` | 3 | 3 | 1.0000 | 1.0000 | none |
| `data_exfiltration` | 3 | 3 | 1.0000 | 0.0000 | refused as unsupported/no-evidence, not guard-blocked |
| `citation_bypass` | 3 | 3 | 1.0000 | 0.0000 | none |

No guard rules were modified for this run.

## Diagnostics

Before injection probes:

| Counter | Value |
|---|---:|
| query_count | 0 |
| answered_count | 0 |
| guard_blocked_count | 0 |
| reranker_degraded_count | 0 |
| langfuse_configured | false |
| langfuse_reachable | false |

After injection probes:

| Counter | Value |
|---|---:|
| query_count | 12 |
| answered_count | 1 |
| guard_blocked_count | 6 |
| reranker_degraded_count | 0 |
| mean_latency_ms | 4183 |
| langfuse_configured | false |
| langfuse_reachable | false |

## Langfuse

Langfuse service health:

```text
GET http://localhost:3000/api/public/health -> {"status":"OK","version":"2.95.11"}
```

Running `python-ai` Langfuse environment:

| Variable | Present | Placeholder |
|---|---|---|
| `LANGFUSE_PUBLIC_KEY` | true | false |
| `LANGFUSE_SECRET_KEY` | true | false |
| `LANGFUSE_HOST` | true | false |

Live UI trace verification is confirmed after restarting `python-ai` with real local Langfuse project keys:

| Path | Outcome | Route | Trace |
|---|---|---|---|
| answered factual | answered | `FACTUAL` / `HYBRID` | http://localhost:3000/project/cmpvj5dqs00062cri1t8hum3r/traces/52b2349d-1968-41d2-88a1-c46d0803187f |
| refused no-evidence | refused | `FACTUAL` / `HYBRID` | http://localhost:3000/project/cmpvj5dqs00062cri1t8hum3r/traces/fd4a4517-e538-46b0-a98c-b4e97ec2783c |
| guard-blocked injection | refused_guard | `UNSUPPORTED` | http://localhost:3000/project/cmpvj5dqs00062cri1t8hum3r/traces/60147b2b-a28c-40f4-9f3c-1786ef99fa8e |
| graph-routed aggregation | answered | `AGGREGATION` / `GRAPH` | http://localhost:3000/project/cmpvj5dqs00062cri1t8hum3r/traces/e34128ec-fe54-4a37-88fa-f652d0f14c57 |

User-confirmed visual evidence: trace `fd4a4517-e538-46b0-a98c-b4e97ec2783c` shows `input_guard -> route -> hybrid_retrieval -> parent_resolve -> rerank -> pack_context -> synthesize -> synthesize_generation -> output_guard -> finalize`. Timeline shows `rerank` as the dominant latency step: 16.31s of 21.82s. The nested `synthesize_generation` observation records 3470 input tokens and 51 output tokens.

Live OPS-01 diagnostics after trace probes:

| Counter | Value |
|---|---:|
| query_count | 5 |
| answered_count | 2 |
| refused_no_evidence_count | 1 |
| guard_blocked_count | 1 |
| reranker_degraded_count | 0 |
| langfuse_configured | true |
| langfuse_reachable | true |
