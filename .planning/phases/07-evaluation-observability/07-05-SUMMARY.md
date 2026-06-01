---
phase: 07-evaluation-observability
plan: "05"
subsystem: evaluation
tags: [eval, golden, russian, corpus-binding, validation]
requires:
  - phase: 07-evaluation-observability
    provides: "07-03 frozen Russian aviation corpus"
  - phase: 07-evaluation-observability
    provides: "07-04 retrieval metrics consume expected_doc_ids"
provides:
  - "40-record Russian golden JSONL dataset"
  - "validator for golden dataset schema and corpus binding"
  - "indexed corpus metadata with live document UUID mapping"
affects: [phase-07-evaluation, ragas-eval, retrieval-eval]
key-files:
  created:
    - ai-service/eval/validate_golden.py
    - ai-service/tests/test_eval_golden_schema.py
    - ai-service/eval/golden/golden_ru.jsonl
  modified:
    - ai-service/eval/golden/golden_ru.meta.json
key-decisions:
  - "Score retrieval expectations at document-id granularity; expected_chunk_hint is advisory only."
  - "Bind the golden dataset to the frozen corpus hash and the live indexed document UUIDs."
  - "Keep out-of-scope records in the scored dataset with explicit refused_no_evidence/refused_guard outcomes."
patterns-established:
  - "Golden validation is a CLI gate before any RAGAS or retrieval runner consumes scored records."
requirements-completed: ["EVAL-01"]
duration: 29 min
completed: 2026-06-01
---

# Phase 07 Plan 05: Russian Golden Dataset Summary

**Russian-only golden dataset validated against the frozen indexed corpus**

## Performance

- **Duration:** 29 min
- **Completed:** 2026-06-01
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `eval.validate_golden`, a CLI and importable validator for JSONL syntax, record schema, unique ids, type/outcome distribution, Russian text fields, corpus hash consistency, indexed metadata, and expected document id membership.
- Authored `golden_ru.jsonl` with exactly 40 Russian scored records:
  - 10 factual
  - 10 aggregation
  - 10 multi-hop
  - 10 out-of-scope
- Captured the out-of-scope split required by the plan: 6 `refused_no_evidence` records and 4 `refused_guard` records. The guard records are ready for the Plan 07-08 injection block-rate measurement, but EVAL-03 is not complete until that report is produced.
- Updated `golden_ru.meta.json` from blocked to ready after live indexing of all 16 frozen corpus documents.
- Recorded the manifest-to-indexed UUID mapping for all frozen corpus documents without changing the corpus hash.

## Task Commits

1. **Task 1: Add golden validator** - `219968d` (`feat(07-05): add golden dataset validator`)
2. **Task 2: Author 40 Russian golden records** - `1a631b9` (`feat(07-05): author russian golden dataset`)

## Corpus Binding

- **Corpus version:** `ru-aviation-logistics-v1`
- **Corpus hash:** `0bea14fee10b2ea99d08159e0684fcb7c9e5b20edd8662528bfa4cb1e9ff6984`
- **Expected document count:** 16
- **Indexed document count:** 16
- **Indexed source:** live Java upload through `/api/v1/documents` against the local Docker stack.
- **Queue state at readiness:** `ai.document.uploaded` had `0` ready and `0` unacknowledged messages.

## Validator Output

```json
{
  "advisory_chunk_hints": 30,
  "corpus_hash": "0bea14fee10b2ea99d08159e0684fcb7c9e5b20edd8662528bfa4cb1e9ff6984",
  "corpus_version": "ru-aviation-logistics-v1",
  "expected_document_count": 16,
  "outcome_counts": {
    "answered": 30,
    "refused_guard": 4,
    "refused_no_evidence": 6
  },
  "record_count": 40,
  "type_counts": {
    "aggregation": 10,
    "factual": 10,
    "multi_hop": 10,
    "out_of_scope": 10
  }
}
```

## Files Created/Modified

- `ai-service/eval/validate_golden.py` - validator and CLI for corpus-bound golden JSONL checks.
- `ai-service/tests/test_eval_golden_schema.py` - validator coverage for JSONL line errors, missing doc ids, advisory hints, chunk-id rejection, corpus binding, and distribution checks.
- `ai-service/eval/golden/golden_ru.jsonl` - 40 Russian scored records.
- `ai-service/eval/golden/golden_ru.meta.json` - ready metadata with indexed corpus UUIDs and manifest mapping.

## Issues Encountered

- The local Docker stack was initially stopped; the build attempt timed out, but starting existing images succeeded.
- The Java upload API rejected the first cookie-authenticated upload without an `Origin` header. Retrying with `Origin: http://localhost` succeeded.
- The AI worker restarted once while processing the final corpus message; after startup completed, the remaining document indexed and the queue drained.

## Verification

- PASS: `uv run --project ai-service --group dev pytest ai-service/tests/test_eval_golden_schema.py` - 6 passed.
- PASS: `cd ai-service; uv run --group dev python -m eval.validate_golden eval/golden/golden_ru.jsonl`.
- PASS: live database check showed all 16 uploaded frozen corpus documents in `INDEXED` status.
- PASS: RabbitMQ check showed `ai.document.uploaded` drained with `0` ready and `0` unacknowledged messages.

## Next Phase Readiness

The golden dataset is ready for Plan 07-06 RAGAS and retrieval evaluation runners. The dataset is Russian-only, corpus-hash-bound, and uses document UUIDs that exist in the local indexed corpus.

## Self-Check: PASSED

- Summary states exact type and outcome counts.
- Validator passes against the committed corpus manifest and golden metadata.
- No exact chunk id hard requirements are present.
- No English Phase 5 smoke documents are counted in the scored dataset.

---
*Phase: 07-evaluation-observability*
*Completed: 2026-06-01*
