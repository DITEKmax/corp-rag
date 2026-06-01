# Phase 8 Final Regression Evidence

- Generated at: `2026-06-01T23:52:51.757822+00:00`
- Status: `checkpoint`
- Corpus version: `ru-aviation-logistics-v1`

## Compose Health

- Input evidence: `9/9`
- Live check: `9/9`

## Seed And Index

- Expected documents: `16`
- Java indexed: `16/16`
- Qdrant documents: `16/16`
- Qdrant points: `16`
- Neo4j documents: `16/16`
- Non-seed Java documents: `0`

## Chat Citation Proof

- Question: `Что требует регламент передачи рейса при передаче рейса между сменами?`
- Answered: `true`
- Status: `ANSWERED`
- Route: `FACTUAL`
- Reranker used: `True`
- Citation document titles: `Регламент передачи рейса, Политика планирования экипажей, Норматив по опасным грузам, Руководство по таможенному транзиту, SLA наземного обслуживания`
- Citation document ids: `337f4a65-efdc-4b3a-91a1-f2e3434439ca, 0f7c5f9f-4808-4d86-a8b9-29c3893d03c6, 7b04026e-6663-4d40-b07a-6463b8afd19c, 805c11c2-d915-4ca9-b188-b1116020e13e, 33b3e4ed-755a-4646-8a68-3ea843e1fe24`
- Trace id: ``

Answer excerpt:

> Регламент передачи рейса требует, чтобы передача начиналась за 90 минут до расчетного времени вылета и закрывалась не позднее чем за 45 минут до вылета [1]. Операционный центр отвечает за статус воздушного судна, слот, план загрузки и наличие экипажа [1]. Наземный подрядчик подтверждает готовность трапа, тягача, багажной ленты и команды из четырех человек [1]. При задержке более 30 минут операционный центр открывает карточку исключения и назначает владельца решения [1]. Для медицинского или дипл

## Reranker Degradation

- reranker_degraded_count before: `0`
- reranker_degraded_count after: `0`

## RAGAS Production Eval

- Command: `C:\Users\maksd\IntelliJIDEA\corp-rag\ai-service\.venv\Scripts\python.exe eval/ragas_runner.py --service-base-url http://localhost:8000 --top-k 10 --timeout-seconds 60 --qdrant-url http://localhost:6333 --judge-base-url https://openrouter.ai/api/v1 --judge-model-id deepseek/deepseek-chat --embedding-model-id BAAI/bge-m3 --reports-dir eval\reports --ragas-max-retries 1 --ragas-max-wait 5`
- faithfulness: `0.9911`
- answer_relevancy: `0.8649`
- context_precision: `1.0`
- context_recall: `1.0`
- answered_count: `16`
- outcome_accuracy: `0.575`
- citation_doc_recall: `0.5333`
- route_mix: `{"AGGREGATION": 4, "COMPARISON": 4, "FACTUAL": 14, "MULTI_HOP": 10, "UNSUPPORTED": 8}`

## Known Limitations

- Multi-hop graph retrieval remains waived for Phase 8: `ru-multihop-002`, `ru-multihop-003`, `ru-multihop-005`, `ru-multihop-006`.
- Current safe behavior for those rows is `refused_no_evidence`, not fabricated unsupported answers.
- Data-exfiltration explicit guard classification and `ru-factual-009` router work remain future work.

## Guardrails

- Guard, citation validation, access filters, weak-evidence thresholds, refusal behavior, corpus, golden data, and expected UUIDs were not changed.
- Generated `ai-service/eval/reports/ragas_ru.*` files are checkpoint artifacts and must not be committed before review.
