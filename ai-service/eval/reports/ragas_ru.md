# Russian Golden RAGAS Production Evaluation

| Field | Value |
|---|---|
| Corpus version | `ru-aviation-logistics-v1` |
| Corpus hash | `0bea14fee10b2ea99d08159e0684fcb7c9e5b20edd8662528bfa4cb1e9ff6984` |
| Model id | `deepseek/deepseek-chat` |
| Eval timestamp | `2026-06-01T23:52:08.708138+00:00` |
| External judge used | `true` |

## Runner Configuration

```json
{
  "runner": "ragas_production_query",
  "model_id": "deepseek/deepseek-chat",
  "corpus_version": "ru-aviation-logistics-v1",
  "corpus_hash": "0bea14fee10b2ea99d08159e0684fcb7c9e5b20edd8662528bfa4cb1e9ff6984",
  "external_judge_used": true,
  "options": {
    "service_base_url": "http://localhost:8000",
    "top_k": 10,
    "reranker_enabled": true,
    "parent_context_enabled": true,
    "qdrant_url": "http://localhost:6333",
    "judge_model_id": "deepseek/deepseek-chat",
    "judge_base_url": "https://openrouter.ai/api/v1",
    "embedding_model_id": "BAAI/bge-m3",
    "concurrency": 1,
    "batching": "disabled",
    "answer_relevancy_skipped": false,
    "token_usage": null,
    "total_cost": null,
    "ragas_max_retries": 1,
    "ragas_max_wait": 5,
    "ragas_score_failures": [
      {
        "record_id": "ru-aggregation-010",
        "metric": "answer_relevancy",
        "error": "RagasOutputParserException: The output parser failed to parse the output including retries. <- OutputParserException: Failed to parse ResponseRelevanceOutput from completion {}. Got: 2 validation errors for ResponseRelevanceOutput\nquestion\n  Field required [type=missing, input_value={}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/missing\nnoncommittal\n  Field required [type=missing, input_value={}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/missing\nFor troubleshooting, visit: https://python.langchain.com/docs/troubleshooting/errors/OUTPUT_PARSING_FAILURE <- ValidationError: 2 validation errors for ResponseRelevanceOutput\nquestion\n  Field required [type=missing, input_value={}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.13/v/missing\nnoncommittal\n  Field required [ty..."
      }
    ]
  }
}
```

## Metrics

| Metric | Value | Threshold | Passed | Notes |
|---|---:|---:|---|---|
| record_count | 40 |  |  | Golden validation record_count=40 |
| answered_count | 16 |  |  | {"answered": 16, "refused_guard": 1, "refused_no_evidence": 23} |
| outcome_accuracy | 0.575 | 0.8 | false | Actual outcome is compared to expected_outcome for all 40 records. |
| citation_doc_recall | 0.5333 | 0.7 | false | Document-level expected_doc_ids present in returned citations for answerable records. |
| route_mix | {"AGGREGATION": 4, "COMPARISON": 4, "FACTUAL": 14, "MULTI_HOP": 10, "UNSUPPORTED": 8} |  |  | Production /v1/query route distribution. |
| faithfulness | 0.9911 | 0.75 | true | RAGAS metric over 16/16 scored rows. |
| answer_relevancy | 0.8649 | 0.75 | true | RAGAS metric over 15/16 scored rows. Failed rows: ru-aggregation-010: RagasOutputParserException: The output parser failed to parse the output including retries. <- OutputParserException: Failed to parse ResponseRelevanceOutput from completion {}. Got: 2 validation errors for ResponseRelevanceOutput
question
  Field required [type=missing, input_value={}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
noncommittal
  Field required [type=missing, input_value={}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
For troubleshooting, visit: https://python.langchain.com/docs/troubleshooting/errors/OUTPUT_PARSING_FAILURE <- ValidationError: 2 validation errors for ResponseRelevanceOutput
question
  Field required [type=missing, input_value={}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/missing
noncommittal
  Field required [ty... |
| context_precision | 1.0 | 0.6 | true | RAGAS metric over 16/16 scored rows. |
| context_recall | 1.0 | 0.6 | true | RAGAS metric over 16/16 scored rows. |

## Details

| ID | Expected | Actual | Correct | Route | Citation Docs | Trace ID |
|---|---|---|---|---|---|---|
| ru-factual-001 | answered | answered | True | COMPARISON | 337f4a65-efdc-4b3a-91a1-f2e3434439ca, 0f7c5f9f-4808-4d86-a8b9-29c3893d03c6, 805c11c2-d915-4ca9-b188-b1116020e13e, 7b04026e-6663-4d40-b07a-6463b8afd19c, 33b3e4ed-755a-4646-8a68-3ea843e1fe24 | None |
| ru-factual-002 | answered | answered | True | FACTUAL | 1c45b64f-5aaa-451c-b675-1079181ff069, 1e07115f-b79a-4f2b-a2b2-88e3e7460fe6, 805c11c2-d915-4ca9-b188-b1116020e13e, dfae45b9-e8f6-4f25-919f-8572ca1f894b, 0f7c5f9f-4808-4d86-a8b9-29c3893d03c6 | None |
| ru-factual-003 | answered | answered | True | FACTUAL | e6d8207a-460b-4f4f-a986-3dc143e51271, 0f7c5f9f-4808-4d86-a8b9-29c3893d03c6, 7b953631-a816-494e-acc6-ac539086b9b4, 7b04026e-6663-4d40-b07a-6463b8afd19c, 1c45b64f-5aaa-451c-b675-1079181ff069 | None |
| ru-factual-004 | answered | answered | True | COMPARISON | 22618bcb-ada0-497a-916c-e072110c70c5, 0f7c5f9f-4808-4d86-a8b9-29c3893d03c6, 337f4a65-efdc-4b3a-91a1-f2e3434439ca, 33b3e4ed-755a-4646-8a68-3ea843e1fe24, 1e07115f-b79a-4f2b-a2b2-88e3e7460fe6 | None |
| ru-factual-005 | answered | refused_no_evidence | False | MULTI_HOP | 0f7c5f9f-4808-4d86-a8b9-29c3893d03c6 | None |
| ru-factual-006 | answered | answered | True | FACTUAL | 43da091e-fcb9-4fde-8615-82518f4d452f, 33b3e4ed-755a-4646-8a68-3ea843e1fe24, fa5c99e6-33d2-42ec-bb31-57630a765734, 337f4a65-efdc-4b3a-91a1-f2e3434439ca, e30b55fe-d647-4563-99ce-d8820417f0c8 | None |
| ru-factual-007 | answered | refused_no_evidence | False | UNSUPPORTED | 1e07115f-b79a-4f2b-a2b2-88e3e7460fe6 | None |
| ru-factual-008 | answered | answered | True | COMPARISON | 33b3e4ed-755a-4646-8a68-3ea843e1fe24, 337f4a65-efdc-4b3a-91a1-f2e3434439ca, 1b7d28c7-3a05-4501-826f-ba36b8e8aaf4, 0f7c5f9f-4808-4d86-a8b9-29c3893d03c6, 22618bcb-ada0-497a-916c-e072110c70c5 | None |
| ru-factual-009 | answered | refused_no_evidence | False | UNSUPPORTED | 7b04026e-6663-4d40-b07a-6463b8afd19c | None |
| ru-factual-010 | answered | answered | True | AGGREGATION | dfae45b9-e8f6-4f25-919f-8572ca1f894b, 7b04026e-6663-4d40-b07a-6463b8afd19c, 33b3e4ed-755a-4646-8a68-3ea843e1fe24, 1b7d28c7-3a05-4501-826f-ba36b8e8aaf4 | None |
| ru-aggregation-001 | answered | answered | True | AGGREGATION | 22618bcb-ada0-497a-916c-e072110c70c5, 33b3e4ed-755a-4646-8a68-3ea843e1fe24, 82ae8890-6b63-4cff-9937-96ff72dbc25b | None |
| ru-aggregation-002 | answered | refused_no_evidence | False | MULTI_HOP | 1c45b64f-5aaa-451c-b675-1079181ff069, 1e07115f-b79a-4f2b-a2b2-88e3e7460fe6, 0f7c5f9f-4808-4d86-a8b9-29c3893d03c6, dfae45b9-e8f6-4f25-919f-8572ca1f894b | None |
| ru-aggregation-003 | answered | answered | True | AGGREGATION | 7b953631-a816-494e-acc6-ac539086b9b4 | None |
| ru-aggregation-004 | answered | answered | True | FACTUAL | e30b55fe-d647-4563-99ce-d8820417f0c8, 22618bcb-ada0-497a-916c-e072110c70c5, 7b953631-a816-494e-acc6-ac539086b9b4, fa5c99e6-33d2-42ec-bb31-57630a765734, 43da091e-fcb9-4fde-8615-82518f4d452f | None |
| ru-aggregation-005 | answered | refused_no_evidence | False | MULTI_HOP | 0f7c5f9f-4808-4d86-a8b9-29c3893d03c6 | None |
| ru-aggregation-006 | answered | answered | True | FACTUAL | 33b3e4ed-755a-4646-8a68-3ea843e1fe24, 337f4a65-efdc-4b3a-91a1-f2e3434439ca, fa5c99e6-33d2-42ec-bb31-57630a765734, 805c11c2-d915-4ca9-b188-b1116020e13e, 43da091e-fcb9-4fde-8615-82518f4d452f | None |
| ru-aggregation-007 | answered | answered | True | AGGREGATION | 7b04026e-6663-4d40-b07a-6463b8afd19c, 1c45b64f-5aaa-451c-b675-1079181ff069, 82ae8890-6b63-4cff-9937-96ff72dbc25b | None |
| ru-aggregation-008 | answered | refused_no_evidence | False | MULTI_HOP | 805c11c2-d915-4ca9-b188-b1116020e13e | None |
| ru-aggregation-009 | answered | answered | True | COMPARISON | fa5c99e6-33d2-42ec-bb31-57630a765734, 82ae8890-6b63-4cff-9937-96ff72dbc25b, 33b3e4ed-755a-4646-8a68-3ea843e1fe24, 43da091e-fcb9-4fde-8615-82518f4d452f, 0f7c5f9f-4808-4d86-a8b9-29c3893d03c6 | None |
| ru-aggregation-010 | answered | answered | True | FACTUAL | 82ae8890-6b63-4cff-9937-96ff72dbc25b, fa5c99e6-33d2-42ec-bb31-57630a765734, 337f4a65-efdc-4b3a-91a1-f2e3434439ca, 33b3e4ed-755a-4646-8a68-3ea843e1fe24, 805c11c2-d915-4ca9-b188-b1116020e13e | None |
| ru-multihop-001 | answered | refused_no_evidence | False | MULTI_HOP | 337f4a65-efdc-4b3a-91a1-f2e3434439ca, 1e07115f-b79a-4f2b-a2b2-88e3e7460fe6 | None |
| ru-multihop-002 | answered | refused_no_evidence | False | MULTI_HOP | 22618bcb-ada0-497a-916c-e072110c70c5, 43da091e-fcb9-4fde-8615-82518f4d452f | None |
| ru-multihop-003 | answered | refused_no_evidence | False | MULTI_HOP | 33b3e4ed-755a-4646-8a68-3ea843e1fe24, 7b953631-a816-494e-acc6-ac539086b9b4 | None |
| ru-multihop-004 | answered | refused_no_evidence | False | UNSUPPORTED | 82ae8890-6b63-4cff-9937-96ff72dbc25b, e30b55fe-d647-4563-99ce-d8820417f0c8 | None |
| ru-multihop-005 | answered | refused_no_evidence | False | MULTI_HOP | 1c45b64f-5aaa-451c-b675-1079181ff069, dfae45b9-e8f6-4f25-919f-8572ca1f894b | None |
| ru-multihop-006 | answered | refused_no_evidence | False | MULTI_HOP | fa5c99e6-33d2-42ec-bb31-57630a765734, 7b953631-a816-494e-acc6-ac539086b9b4 | None |
| ru-multihop-007 | answered | refused_no_evidence | False | FACTUAL | e6d8207a-460b-4f4f-a986-3dc143e51271, e30b55fe-d647-4563-99ce-d8820417f0c8, 7b953631-a816-494e-acc6-ac539086b9b4 | None |
| ru-multihop-008 | answered | answered | True | FACTUAL | 805c11c2-d915-4ca9-b188-b1116020e13e, 337f4a65-efdc-4b3a-91a1-f2e3434439ca, 1c45b64f-5aaa-451c-b675-1079181ff069, 1e07115f-b79a-4f2b-a2b2-88e3e7460fe6, fa5c99e6-33d2-42ec-bb31-57630a765734 | None |
| ru-multihop-009 | answered | answered | True | FACTUAL | 1b7d28c7-3a05-4501-826f-ba36b8e8aaf4, 0f7c5f9f-4808-4d86-a8b9-29c3893d03c6, 337f4a65-efdc-4b3a-91a1-f2e3434439ca, fa5c99e6-33d2-42ec-bb31-57630a765734, 33b3e4ed-755a-4646-8a68-3ea843e1fe24 | None |
| ru-multihop-010 | answered | refused_no_evidence | False | MULTI_HOP | 7b04026e-6663-4d40-b07a-6463b8afd19c, fa5c99e6-33d2-42ec-bb31-57630a765734 | None |
| ru-out-001 | refused_no_evidence | refused_no_evidence | True | FACTUAL |  | None |
| ru-out-002 | refused_no_evidence | refused_no_evidence | True | FACTUAL |  | None |
| ru-out-003 | refused_no_evidence | refused_no_evidence | True | FACTUAL |  | None |
| ru-out-004 | refused_no_evidence | refused_no_evidence | True | FACTUAL |  | None |
| ru-out-005 | refused_no_evidence | refused_no_evidence | True | FACTUAL |  | None |
| ru-out-006 | refused_no_evidence | refused_no_evidence | True | UNSUPPORTED |  | None |
| ru-out-007 | refused_guard | refused_guard | True | UNSUPPORTED |  | None |
| ru-out-008 | refused_guard | refused_no_evidence | False | UNSUPPORTED |  | None |
| ru-out-009 | refused_guard | refused_no_evidence | False | UNSUPPORTED |  | None |
| ru-out-010 | refused_guard | refused_no_evidence | False | UNSUPPORTED |  | None |
