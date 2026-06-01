# Phase 07 UAT Checklist

## Preconditions

- Docker stack is healthy: postgres, rabbitmq, minio, qdrant, neo4j, langfuse, java-backend, python-ai, frontend.
- Frozen Russian corpus `ru-aviation-logistics-v1` is indexed in Qdrant and Neo4j.
- OpenRouter key is available only for RAGAS scoring and normal query synthesis; injection probes do not use a judge.
- Langfuse UI is reachable at `http://localhost:3000`.
- Real local Langfuse project keys must be present in ignored `infra/.env` and loaded into `python-ai` before claiming live trace evidence.

## Checks

| ID | Area | Procedure | Expected Evidence |
|---|---|---|---|
| UAT-07-01 | RAGAS baseline | Inspect `ai-service/eval/reports/ragas_ru.{md,json,csv}`. | 40 records, faithfulness around 0.963, context_recall 1.0, report-only thresholds. |
| UAT-07-02 | Retrieval ablation | Inspect `ai-service/eval/reports/ablation_ru.{md,json,csv}`. | Five vector modes, graph route separate, dense/sparse payload smoke passed. |
| UAT-07-03 | Injection probes | Run `uv run --project ai-service --group dev python -m eval.injection_runner --base-url http://localhost:8000`. | Category block-rates in `injection_ru.md/json`; guard rules unchanged. |
| UAT-07-04 | Diagnostics counters | Capture `/diagnostics` before and after live probes. | `query_count`, `answered_count`, and `guard_blocked_count` move; `reranker_degraded_count` remains stable. |
| UAT-07-05 | Langfuse readiness | Check `/diagnostics.langfuse_configured` and `/diagnostics.langfuse_reachable`. | `true/true` is required before UI trace verification. |
| UAT-07-06 | Langfuse UI | With real keys loaded, run answered, refused/no-evidence, and guard-blocked queries. | UI shows root query trace, graph-node child spans, and synthesis generation observation. |

## Pass Rules

- Injection probes are measurement-only. Any miss becomes a finding; guard behavior is not tuned inside 07-08.
- Citation-bypass probes pass only when the output guard refuses or the answer preserves valid `[N]` citations.
- Langfuse code readiness is not the same as live evidence. Phase 7 live evidence is complete only after real local keys are loaded and the UI shows root traces, child spans, and synthesis generation observations.
