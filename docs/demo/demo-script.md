# Phase 8 Demo Script

This script is the recording/narration path for the final local MVP demo. It
must stay honest: the story is high answer quality with limited answer coverage.
Do not claim production readiness, do not invent metrics, and do not hide
safe refusals.

## Pre-flight

Use the committed Phase 8 evidence as the baseline:

- Compose health: `9/9`.
- Seed corpus: 16 Russian logistics/aviation documents.
- Synthesis/router model: `deepseek/deepseek-v4-flash`.
- RAGAS judge: `deepseek/deepseek-chat`.
- Reranker degraded before/after: `0/0`.
- Known limitations: see
  [08-KNOWN-LIMITATIONS.md](../../.planning/phases/08-delivery-polish-demo-readiness/08-KNOWN-LIMITATIONS.md).

Before recording, verify locally:

```powershell
docker compose --env-file infra/.env -f infra/docker-compose.yml ps
Invoke-RestMethod http://localhost:8000/diagnostics
Invoke-RestMethod http://localhost:8080/actuator/health
```

## Opening: architecture boundary

Show [docs/ARCHITECTURE.md](../ARCHITECTURE.md), section 2.1.

Narration:

> The browser talks only to the Java Spring backend. Java owns auth, users,
> access policies, documents, chat, audit, and the browser-facing API. Python is
> the internal AI service: ingestion, retrieval, graph, guards, synthesis, and
> eval. Qdrant, Neo4j, AI Postgres, RabbitMQ, MinIO, and Langfuse support those
> two service boundaries.

Do not introduce another deployment topology. This is the single local compose
demo stack.

## Scene 1: factual answer with citation

Open `http://localhost`, sign in with the local admin account from ignored
`infra/.env`, and use the chat UI.

Ask:

```text
Что требует регламент передачи рейса при передаче рейса между сменами?
```

Expected result:

- `answered=true`
- status `ANSWERED`
- route `FACTUAL`
- reranker used: `true`
- citation document titles include:
  - `Регламент передачи рейса`
  - `Политика планирования экипажей`
  - `Норматив по опасным грузам`
  - `Руководство по таможенному транзиту`
  - `SLA наземного обслуживания`

Narration:

> This is the strong path. The answer is not free-form guessing: it is grounded
> in retrieved context and emits citation references. The final RAGAS run scored
> `faithfulness=0.991`, `answer_relevancy=0.865`, `context_precision=1.0`, and
> `context_recall=1.0` on answered rows.

Open the citation/source view and point to the source text. The expected source
for the first citation is `Регламент передачи рейса`, which states the handoff
timing and responsibility details. Keep the wording grounded in the visible
source; do not paraphrase beyond what the citation supports.

## Scene 2: live Langfuse trace and latency

Open Langfuse at `http://localhost:3000` and select the latest trace generated
by the factual query. The final static regression evidence may have an empty
trace id, so use the live trace shown in Langfuse rather than inventing an id.

Show the node/span breakdown:

- root query span
- input guard
- query routing
- hybrid retrieval or graph retrieval, depending on route
- parent context loading
- rerank
- synthesis
- output guard

Narration:

> The trace makes latency explainable instead of mysterious. Retrieval and
> synthesis are visible, and rerank is the dominant span in this live trace. That
> is expected for the local `BAAI/bge-reranker-v2-m3` cross-encoder path. The
> important regression signal is that reranker degradation stayed `0/0`, so the
> system used the reranker rather than silently falling back.

If exact milliseconds are visible in the trace, read them from the UI. If they
are not visible, do not invent timing numbers; say only that the observed trace
shows rerank as the dominant latency contributor.

## Scene 3: injection and refusal

Use the prepared injection/refusal scene from the final RAGAS output:

```text
ru-out-007
```

Expected result:

- outcome `refused_guard`
- guard tier `TIER_0_REGEX`
- confidence `1.0`
- no retrieval, rerank, or synthesis required for the blocked request

Narration:

> This is a deterministic guard refusal. The attack is blocked before retrieval
> and before synthesis. The system does not expose hidden prompt context, and it
> does not try to answer an unsafe request.

For broader injection evidence, mention
[injection_ru.md](../../ai-service/eval/reports/injection_ru.md): prompt
injection and jailbreak probes are guard-blocked, while data-exfiltration probes
are still blocked from succeeding but are tracked as a future explicit guard
classification improvement.

## Scene 4: multi-hop limitation and safe refusal

Show [08-KNOWN-LIMITATIONS.md](../../.planning/phases/08-delivery-polish-demo-readiness/08-KNOWN-LIMITATIONS.md)
and cite the waived multi-hop rows:

```text
ru-multihop-002
ru-multihop-003
ru-multihop-005
ru-multihop-006
```

Narration:

> This is the honest limitation. Multi-hop graph retrieval is measured and
> waived for Phase 8. The system can route these questions to `MULTI_HOP`, but
> current graph retrieval does not always gather enough text-conditioned
> evidence across Russian documents. The correct behavior is safe refusal:
> `refused_no_evidence`, not a fabricated answer.

Then state the quality-vs-coverage summary:

> Quality is high where the system answers: `faithfulness=0.991`,
> `context_precision=1.0`, `context_recall=1.0`. Coverage is limited:
> `answered=16/30 answerable`, `outcome_accuracy=0.575`, and
> `citation_doc_recall=0.533`. The demo does not hide that. It shows a system
> that is conservative under weak evidence.

## Close

End on the three claims that the evidence supports:

1. The local MVP stack is reproducible through a single compose topology.
2. Factual Russian-corpus questions answer well with citation support.
3. Known coverage gaps are documented and lead to safe refusal instead of
   unsupported synthesis.
