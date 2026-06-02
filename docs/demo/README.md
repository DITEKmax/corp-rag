# Demo Assets

Phase 8 demo materials for the local MVP. The demo is Russian-corpus-first and
frames the system honestly as quality-vs-coverage: answered rows are highly
grounded, while known coverage gaps produce safe refusal instead of fabrication.

## Demo posture

Final corpus and model facts:

- Corpus: `ru-aviation-logistics-v1`, 16 indexed Russian logistics/aviation documents.
- Synthesis/router model: `deepseek/deepseek-v4-flash`.
- RAGAS judge: `deepseek/deepseek-chat`.
- Answer quality: `faithfulness=0.991`, `answer_relevancy=0.865`,
  `context_precision=1.0`, `context_recall=1.0`.
- Coverage limits: `answered=16/30 answerable`, `outcome_accuracy=0.575`,
  `citation_doc_recall=0.533`.
- Reranker degradation evidence: `0/0`.
- Injection scene: `ru-out-007` blocked by `TIER_0_REGEX`, confidence `1.0`.

## Assets

| Asset | Purpose |
|---|---|
| [demo-script.md](demo-script.md) | Concrete narrated walkthrough: factual answer, citations, Langfuse latency, injection/refusal, multi-hop limitation. |
| [video-checklist.md](video-checklist.md) | Ready-to-record checklist and video waiver status. |
| [../ARCHITECTURE.md](../ARCHITECTURE.md) | Architecture diagram showing frontend-to-Java only and Java/Python ownership. |
| [../../infra/README.md](../../infra/README.md) | Local compose runbook. |
| [../../README.md](../../README.md) | Top-level demo quickstart. |

## Evidence links

| Evidence | What it proves |
|---|---|
| [08-COMPOSE-EVIDENCE.md](../../.planning/phases/08-delivery-polish-demo-readiness/08-COMPOSE-EVIDENCE.md) | Local compose readiness, `9/9` healthy services, Langfuse reachable. |
| [08-SEED-EVIDENCE.md](../../.planning/phases/08-delivery-polish-demo-readiness/08-SEED-EVIDENCE.md) | Clean 16-document seed corpus in Java, Qdrant, and Neo4j. |
| [08-FINAL-REGRESSION.md](../../.planning/phases/08-delivery-polish-demo-readiness/08-FINAL-REGRESSION.md) | Final chat/citation proof, RAGAS metrics, reranker degradation `0/0`. |
| [ragas_ru.md](../../ai-service/eval/reports/ragas_ru.md) | Production RAGAS report with quality and coverage metrics. |
| [injection_ru.md](../../ai-service/eval/reports/injection_ru.md) | Injection probe report; attacks are blocked or safely refused. |
| [08-KNOWN-LIMITATIONS.md](../../.planning/phases/08-delivery-polish-demo-readiness/08-KNOWN-LIMITATIONS.md) | Multi-hop waiver, router false-`MULTI_HOP`, and safe refusal framing. |

## Demo route

1. Start from the architecture boundary: frontend calls Java only; Java owns
   auth/documents/chat/audit; Python owns ingestion/retrieval/graph/guards/synthesis/eval.
2. Open the chat UI and ask a factual Russian question from the seeded corpus.
3. Inspect citation chips/source text and call out that answers carry sources.
4. Open the live Langfuse trace and show latency breakdown; rerank is the
   dominant span in the observed trace.
5. Submit the injection/refusal example and show the guard result.
6. Submit or explain a multi-hop limitation example and explicitly state that
   safe refusal is preferred to unsupported synthesis.
