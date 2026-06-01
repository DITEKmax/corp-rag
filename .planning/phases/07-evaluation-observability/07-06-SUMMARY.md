---
phase: 07-evaluation-observability
plan: "06"
subsystem: evaluation
tags: [eval, ragas, production-query, russian, baseline]
requires:
  - phase: 07-evaluation-observability
    provides: "07-05 corpus-bound Russian golden dataset"
provides:
  - "production /v1/query RAGAS baseline over all 40 Russian golden records"
  - "score-only-safe query-phase cache before RAGAS scoring"
  - "full parent-context extraction for RAGAS retrieved_contexts"
  - "committed Markdown/JSON/CSV RAGAS reports"
affects: [phase-07-evaluation, ragas-eval, query-quality-baseline]
key-files:
  created:
    - ai-service/eval/reports/ragas_ru.md
    - ai-service/eval/reports/ragas_ru.json
    - ai-service/eval/reports/ragas_ru.csv
  modified:
    - ai-service/eval/query_client.py
    - ai-service/eval/ragas_runner.py
    - ai-service/tests/test_eval_query_client.py
    - ai-service/tests/test_eval_ragas_runner.py
key-decisions:
  - "Persist the query-phase report immediately after collection and before RAGAS scoring so score-only can recover from scoring failures."
  - "Use eval-only topK override defaults without changing production /v1/query defaults."
  - "Feed RAGAS full parent contexts from Qdrant parentChunkId plus AI Postgres document_chunks_parent, not citation snippets."
  - "Keep RAGAS thresholds as report flags; no CI gate was added."
requirements-completed: ["EVAL-02"]
completed: 2026-06-01
---

# Phase 07 Plan 06: Production RAGAS Baseline Summary

**Production `/v1/query` quality baseline recorded over all 40 Russian golden questions**

## Performance

- **Completed:** 2026-06-01
- **Records:** 40
- **Scored answered rows:** 15
- **Concurrency:** 1
- **Final eval topK:** 10

## Accomplishments

- Added a production query client and RAGAS runner for the full 40-record Russian golden set.
- Added query-phase cache persistence before scoring. If RAGAS scoring fails, `ragas_ru.json` still contains the freshly collected per-question production answers, retrieved contexts, outcomes, reranker usage, and degradation warnings.
- Added score-only support for re-scoring an existing report without rerunning `/v1/query`.
- Added local `BAAI/bge-m3` embedding support for RAGAS answer relevancy.
- Corrected the RAGAS `retrieved_contexts` source from short citation quote/snippet text to full parent contexts resolved through Qdrant `chunkId -> parentChunkId` and AI Postgres `document_chunks_parent`.
- Removed six non-golden Phase 5/UAT leftovers from the live Qdrant `documents_chunks` collection before the final baseline run:
  - `Acme Remote Work Policy`
  - `TechCorp Approved Vendor List`
  - `TechCorp Phase 5 Query Policy`
  - `TechCorp Q1 2026 Security Incident Report`
  - `Politica`
  - `Title`
- Verified Qdrant after cleanup: 16 remaining document IDs, all from `golden_ru.meta.json`, with no missing golden documents and no extra non-golden documents.

## Final Live Command

```powershell
cd ai-service
uv run --env-file ../infra/.env python eval/ragas_runner.py --top-k 10 --timeout-seconds 180 --judge-base-url https://openrouter.ai/api/v1 --judge-model-id deepseek/deepseek-chat --embedding-model-id BAAI/bge-m3
```

## Final RAGAS Report

- **Report JSON:** `ai-service/eval/reports/ragas_ru.json`
- **Report Markdown:** `ai-service/eval/reports/ragas_ru.md`
- **Report CSV:** `ai-service/eval/reports/ragas_ru.csv`
- **Corpus version:** `ru-aviation-logistics-v1`
- **Corpus hash:** `0bea14fee10b2ea99d08159e0684fcb7c9e5b20edd8662528bfa4cb1e9ff6984`
- **Judge model:** `deepseek/deepseek-chat`
- **Embedding model:** `BAAI/bge-m3`
- **External judge used:** true
- **Langfuse:** disabled/unreachable in this local run; trace IDs are optional evidence and did not block report generation.

## Final Metrics

| Metric | Value | Threshold | Passed |
|--------|------:|----------:|--------|
| `record_count` | 40 | - | - |
| `answered_count` | 15 | - | - |
| `outcome_accuracy` | 0.55 | 0.80 | false |
| `citation_doc_recall` | 0.50 | 0.70 | false |
| `faithfulness` | 0.9167 | 0.75 | true |
| `answer_relevancy` | 0.8561 | 0.75 | true |
| `context_precision` | 0.9889 | 0.60 | true |
| `context_recall` | 1.0000 | 0.60 | true |

## Diagnostics Delta

Baseline before the final topK=10 run had already recorded the earlier topK=5 run:

| Diagnostic | Before | After | Delta |
|------------|-------:|------:|------:|
| `query_count` | 40 | 80 | +40 |
| `answered_count` | 17 | 32 | +15 |
| `reranker_degraded_count` | 0 | 0 | +0 |
| `mean_latency_ms` | 10488 | 11478 | cumulative |

## Findings Deferred

The final report is a valid RAGAS baseline after fixing eval context extraction, but production answerability remains weak for graph/router paths:

- 30 answerable golden questions produced 15 answers and 15 `refused_no_evidence` outcomes.
- Refused answerable questions by route:
  - `MULTI_HOP`: 8
  - `UNSUPPORTED`: 5
  - `AGGREGATION`: 1
  - `FACTUAL`: 1
- The `UNSUPPORTED` answerable cases are likely router classification bugs, because the questions are answerable from golden corpus documents.
- The graph-empty cases require separate Neo4j/entity-extraction diagnostics before fixes. This is deferred outside Plan 07-06 and should be handled as a separate graph/router quality task.

## Verification

- PASS: `uv run pytest tests/test_eval_query_client.py tests/test_eval_ragas_runner.py` - 9 passed.
- PASS: `uv run pytest` in `ai-service` - 262 passed, 12 skipped.
- PASS: live RAGAS report contains all 40 golden IDs.
- PASS: final report has non-skipped RAGAS metrics for all four required metrics.
- PASS: `reranker_degraded_count` stayed at 0 during the final topK=10 run.
- PASS: Qdrant live collection contains exactly the 16 golden metadata document IDs after cleanup.

## Self-Check: PASSED

- The baseline uses production `/v1/query`; no internal retrieval shortcut was used.
- RAGAS scoring uses full parent contexts rather than citation snippets.
- Reports are committed as baseline artifacts, but no CI gate was introduced.
- Graph/router remediation is explicitly deferred and not mixed into this baseline.

---
*Phase: 07-evaluation-observability*
*Plan: 06*
*Completed: 2026-06-01*
