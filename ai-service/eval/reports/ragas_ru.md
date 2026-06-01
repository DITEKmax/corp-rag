# Russian Golden RAGAS Production Evaluation

| Field | Value |
|---|---|
| Corpus version | `ru-aviation-logistics-v1` |
| Corpus hash | `0bea14fee10b2ea99d08159e0684fcb7c9e5b20edd8662528bfa4cb1e9ff6984` |
| Model id | `deepseek/deepseek-chat` |
| Eval timestamp | `2026-06-01T14:12:10.570901+00:00` |
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
    "total_cost": null
  }
}
```

## Metrics

| Metric | Value | Threshold | Passed | Notes |
|---|---:|---:|---|---|
| record_count | 40 |  |  | Golden validation record_count=40 |
| answered_count | 15 |  |  | {"answered": 15, "refused_guard": 1, "refused_no_evidence": 24} |
| outcome_accuracy | 0.55 | 0.8 | false | Actual outcome is compared to expected_outcome for all 40 records. |
| citation_doc_recall | 0.5 | 0.7 | false | Document-level expected_doc_ids present in returned citations for answerable records. |
| route_mix | {"AGGREGATION": 2, "COMPARISON": 2, "FACTUAL": 16, "MULTI_HOP": 8, "UNSUPPORTED": 12} |  |  | Production /v1/query route distribution. |
| faithfulness | 0.9167 | 0.75 | true | RAGAS metric over 15 scored rows. |
| answer_relevancy | 0.8561 | 0.75 | true | RAGAS metric over 15 scored rows. |
| context_precision | 0.9889 | 0.6 | true | RAGAS metric over 15 scored rows. |
| context_recall | 1.0 | 0.6 | true | RAGAS metric over 15 scored rows. |

## Details

| ID | Expected | Actual | Correct | Route | Citation Docs | Trace ID |
|---|---|---|---|---|---|---|
| ru-factual-001 | answered | refused_no_evidence | False | MULTI_HOP | 87b81f3b-357b-4599-9aea-36920cffccc9 | None |
| ru-factual-002 | answered | answered | True | FACTUAL | 116a0b8e-fad3-4299-8f1b-fa48e2e4fd2a, a411dd48-2862-43f1-99c2-199c18e26c48, 2e675573-1262-4546-9e50-d5ef5df93a36, 78227564-0c5a-4dfc-9a45-78d7cee2d6aa, aa939285-1629-450d-b1f4-0e63ec6ba1c6 | None |
| ru-factual-003 | answered | answered | True | FACTUAL | bf07dc98-da4b-47c7-aed2-66e0ff04f7f1, aa939285-1629-450d-b1f4-0e63ec6ba1c6, d649c134-dd26-4c4d-bd18-772cb4f46b73, 5cba5417-0b01-48d1-8d4c-67b74197a4db, 116a0b8e-fad3-4299-8f1b-fa48e2e4fd2a | None |
| ru-factual-004 | answered | answered | True | COMPARISON | d3b8329b-f10b-4873-806d-a22427067eca, aa939285-1629-450d-b1f4-0e63ec6ba1c6, 87b81f3b-357b-4599-9aea-36920cffccc9, 13d8e22d-524b-410f-8d28-5e4830527841, a411dd48-2862-43f1-99c2-199c18e26c48 | None |
| ru-factual-005 | answered | refused_no_evidence | False | MULTI_HOP | aa939285-1629-450d-b1f4-0e63ec6ba1c6 | None |
| ru-factual-006 | answered | answered | True | FACTUAL | fd602b4c-494c-4b5c-9994-bb9addc4d89a, 13d8e22d-524b-410f-8d28-5e4830527841, e077eb72-0e27-4e1e-9b63-34316e88b546, 87b81f3b-357b-4599-9aea-36920cffccc9, b457b292-de31-491e-8535-df3a31ab5c8c | None |
| ru-factual-007 | answered | answered | True | FACTUAL | a411dd48-2862-43f1-99c2-199c18e26c48, 5cba5417-0b01-48d1-8d4c-67b74197a4db, bf07dc98-da4b-47c7-aed2-66e0ff04f7f1, 87b81f3b-357b-4599-9aea-36920cffccc9, 13d8e22d-524b-410f-8d28-5e4830527841 | None |
| ru-factual-008 | answered | answered | True | FACTUAL | 13d8e22d-524b-410f-8d28-5e4830527841, 87b81f3b-357b-4599-9aea-36920cffccc9, 46b8b66b-8509-4c9f-8d8d-fdd7eb52cb47, aa939285-1629-450d-b1f4-0e63ec6ba1c6, d3b8329b-f10b-4873-806d-a22427067eca | None |
| ru-factual-009 | answered | answered | True | FACTUAL | 5cba5417-0b01-48d1-8d4c-67b74197a4db, bf07dc98-da4b-47c7-aed2-66e0ff04f7f1, e077eb72-0e27-4e1e-9b63-34316e88b546, 78227564-0c5a-4dfc-9a45-78d7cee2d6aa, 46b8b66b-8509-4c9f-8d8d-fdd7eb52cb47 | None |
| ru-factual-010 | answered | answered | True | FACTUAL | 78227564-0c5a-4dfc-9a45-78d7cee2d6aa, 2e675573-1262-4546-9e50-d5ef5df93a36, 116a0b8e-fad3-4299-8f1b-fa48e2e4fd2a, 5cba5417-0b01-48d1-8d4c-67b74197a4db, 13d8e22d-524b-410f-8d28-5e4830527841 | None |
| ru-aggregation-001 | answered | refused_no_evidence | False | AGGREGATION | d3b8329b-f10b-4873-806d-a22427067eca | None |
| ru-aggregation-002 | answered | refused_no_evidence | False | MULTI_HOP | 116a0b8e-fad3-4299-8f1b-fa48e2e4fd2a, a411dd48-2862-43f1-99c2-199c18e26c48, aa939285-1629-450d-b1f4-0e63ec6ba1c6, 78227564-0c5a-4dfc-9a45-78d7cee2d6aa | None |
| ru-aggregation-003 | answered | refused_no_evidence | False | UNSUPPORTED | d649c134-dd26-4c4d-bd18-772cb4f46b73 | None |
| ru-aggregation-004 | answered | answered | True | FACTUAL | b457b292-de31-491e-8535-df3a31ab5c8c, d3b8329b-f10b-4873-806d-a22427067eca, d649c134-dd26-4c4d-bd18-772cb4f46b73, bf07dc98-da4b-47c7-aed2-66e0ff04f7f1, e077eb72-0e27-4e1e-9b63-34316e88b546 | None |
| ru-aggregation-005 | answered | answered | True | FACTUAL | aa939285-1629-450d-b1f4-0e63ec6ba1c6, 13d8e22d-524b-410f-8d28-5e4830527841, 46b8b66b-8509-4c9f-8d8d-fdd7eb52cb47, bf07dc98-da4b-47c7-aed2-66e0ff04f7f1, 5cba5417-0b01-48d1-8d4c-67b74197a4db | None |
| ru-aggregation-006 | answered | answered | True | FACTUAL | 13d8e22d-524b-410f-8d28-5e4830527841, 87b81f3b-357b-4599-9aea-36920cffccc9, e077eb72-0e27-4e1e-9b63-34316e88b546, 2e675573-1262-4546-9e50-d5ef5df93a36, fd602b4c-494c-4b5c-9994-bb9addc4d89a | None |
| ru-aggregation-007 | answered | refused_no_evidence | False | MULTI_HOP | 5cba5417-0b01-48d1-8d4c-67b74197a4db | None |
| ru-aggregation-008 | answered | refused_no_evidence | False | MULTI_HOP | 2e675573-1262-4546-9e50-d5ef5df93a36 | None |
| ru-aggregation-009 | answered | answered | True | COMPARISON | e077eb72-0e27-4e1e-9b63-34316e88b546, 1f81ef52-3447-4166-ae1d-030cc3fb4cb2, 13d8e22d-524b-410f-8d28-5e4830527841, fd602b4c-494c-4b5c-9994-bb9addc4d89a, aa939285-1629-450d-b1f4-0e63ec6ba1c6 | None |
| ru-aggregation-010 | answered | answered | True | FACTUAL | 1f81ef52-3447-4166-ae1d-030cc3fb4cb2, e077eb72-0e27-4e1e-9b63-34316e88b546, 87b81f3b-357b-4599-9aea-36920cffccc9, 13d8e22d-524b-410f-8d28-5e4830527841, 2e675573-1262-4546-9e50-d5ef5df93a36 | None |
| ru-multihop-001 | answered | refused_no_evidence | False | MULTI_HOP | 87b81f3b-357b-4599-9aea-36920cffccc9, a411dd48-2862-43f1-99c2-199c18e26c48 | None |
| ru-multihop-002 | answered | refused_no_evidence | False | UNSUPPORTED | d3b8329b-f10b-4873-806d-a22427067eca, fd602b4c-494c-4b5c-9994-bb9addc4d89a | None |
| ru-multihop-003 | answered | refused_no_evidence | False | UNSUPPORTED | 13d8e22d-524b-410f-8d28-5e4830527841, d649c134-dd26-4c4d-bd18-772cb4f46b73 | None |
| ru-multihop-004 | answered | refused_no_evidence | False | MULTI_HOP | 1f81ef52-3447-4166-ae1d-030cc3fb4cb2, b457b292-de31-491e-8535-df3a31ab5c8c | None |
| ru-multihop-005 | answered | refused_no_evidence | False | UNSUPPORTED | 116a0b8e-fad3-4299-8f1b-fa48e2e4fd2a, 78227564-0c5a-4dfc-9a45-78d7cee2d6aa | None |
| ru-multihop-006 | answered | refused_no_evidence | False | UNSUPPORTED | e077eb72-0e27-4e1e-9b63-34316e88b546, d649c134-dd26-4c4d-bd18-772cb4f46b73 | None |
| ru-multihop-007 | answered | refused_no_evidence | False | FACTUAL | bf07dc98-da4b-47c7-aed2-66e0ff04f7f1, b457b292-de31-491e-8535-df3a31ab5c8c, d649c134-dd26-4c4d-bd18-772cb4f46b73 | None |
| ru-multihop-008 | answered | refused_no_evidence | False | MULTI_HOP | 116a0b8e-fad3-4299-8f1b-fa48e2e4fd2a, 87b81f3b-357b-4599-9aea-36920cffccc9, 2e675573-1262-4546-9e50-d5ef5df93a36 | None |
| ru-multihop-009 | answered | answered | True | FACTUAL | 46b8b66b-8509-4c9f-8d8d-fdd7eb52cb47, aa939285-1629-450d-b1f4-0e63ec6ba1c6, 87b81f3b-357b-4599-9aea-36920cffccc9, e077eb72-0e27-4e1e-9b63-34316e88b546, 13d8e22d-524b-410f-8d28-5e4830527841 | None |
| ru-multihop-010 | answered | answered | True | FACTUAL | 5cba5417-0b01-48d1-8d4c-67b74197a4db, e077eb72-0e27-4e1e-9b63-34316e88b546, 2e675573-1262-4546-9e50-d5ef5df93a36, 116a0b8e-fad3-4299-8f1b-fa48e2e4fd2a, 1f81ef52-3447-4166-ae1d-030cc3fb4cb2 | None |
| ru-out-001 | refused_no_evidence | refused_no_evidence | True | FACTUAL |  | None |
| ru-out-002 | refused_no_evidence | refused_no_evidence | True | AGGREGATION |  | None |
| ru-out-003 | refused_no_evidence | refused_no_evidence | True | UNSUPPORTED |  | None |
| ru-out-004 | refused_no_evidence | refused_no_evidence | True | FACTUAL |  | None |
| ru-out-005 | refused_no_evidence | refused_no_evidence | True | UNSUPPORTED |  | None |
| ru-out-006 | refused_no_evidence | refused_no_evidence | True | UNSUPPORTED |  | None |
| ru-out-007 | refused_guard | refused_guard | True | UNSUPPORTED |  | None |
| ru-out-008 | refused_guard | refused_no_evidence | False | UNSUPPORTED |  | None |
| ru-out-009 | refused_guard | refused_no_evidence | False | UNSUPPORTED |  | None |
| ru-out-010 | refused_guard | refused_no_evidence | False | UNSUPPORTED |  | None |
