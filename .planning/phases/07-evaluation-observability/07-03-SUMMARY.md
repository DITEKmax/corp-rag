---
phase: 07-evaluation-observability
plan: "03"
subsystem: evaluation
tags: [eval, corpus, russian, reporting, golden-metadata]
requires:
  - phase: 07-evaluation-observability
    provides: "07-01 runtime contour and 07-02 observability hooks"
provides:
  - "import-safe ai-service/eval package"
  - "frozen 16-document Russian aviation/logistics corpus"
  - "corpus hash metadata for golden dataset binding"
  - "shared Markdown/JSON/CSV report writer"
affects: [phase-07-evaluation, golden-dataset, reports]
tech-stack:
  added: []
  patterns:
    - "Eval runners live under ai-service/eval and are packaged separately from corp_rag_ai runtime code"
    - "Corpus hash is computed from committed document paths and bytes in manifest order"
key-files:
  created:
    - ai-service/eval/schema.py
    - ai-service/eval/io.py
    - ai-service/eval/validate_corpus.py
    - ai-service/eval/reporting.py
    - ai-service/eval/corpus/manifest.json
    - ai-service/eval/corpus/documents/*.md
    - ai-service/eval/golden/golden_ru.meta.json
    - ai-service/eval/reports/README.md
    - ai-service/tests/test_eval_schema.py
    - ai-service/tests/test_eval_reporting.py
  modified:
    - ai-service/pyproject.toml
key-decisions:
  - "Use committed Markdown documents plus manifest.json as the frozen corpus source, not a runtime generator."
  - "Set golden_ru.meta.json indexed=false until the Docker indexing smoke proves Qdrant/Neo4j contain the snapshot."
  - "Package ai-service/eval in the ai-service wheel so tests run from the repository root can import eval helpers."
patterns-established:
  - "Report helpers enforce common metadata: corpus version/hash, model id, timestamp, runner config, and external judge usage."
requirements-completed: ["EVAL-01", "EVAL-02"]
duration: 8 min
completed: 2026-06-01
---

# Phase 07 Plan 03: Eval Corpus Foundation Summary

**Frozen Russian aviation/logistics corpus and reusable evaluation report contract**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-01T08:14:57Z
- **Completed:** 2026-06-01T08:22:31Z
- **Tasks:** 4
- **Files modified:** 27

## Accomplishments

- Added the import-safe `ai-service/eval` package with typed golden-record, corpus, runner, metric, and report schemas.
- Committed a 16-document Russian aviation/logistics corpus under `ai-service/eval/corpus/documents/` with manifest metadata.
- Bound `golden_ru.meta.json` to corpus hash `0bea14fee10b2ea99d08159e0684fcb7c9e5b20edd8662528bfa4cb1e9ff6984`.
- Added reusable report writing for Markdown, JSON, and optional CSV outputs under `ai-service/eval/reports/`.

## Task Commits

1. **Task 1: Add eval package skeleton and schemas** - `ca3b977` (`feat(07-03): add eval harness schemas`)
2. **Task 2: Author and freeze the Russian corpus snapshot** - `b487148` (`feat(07-03): freeze russian aviation corpus`)
3. **Task 3: Add shared report writer** - `695b5ef` (`feat(07-03): add eval report writer`)
4. **Task 4: Index the frozen corpus for downstream plans** - documented as blocked because the Docker stack is not running.

## Corpus Snapshot

- **Version:** `ru-aviation-logistics-v1`
- **Hash:** `0bea14fee10b2ea99d08159e0684fcb7c9e5b20edd8662528bfa4cb1e9ff6984`
- **Document count:** 16
- **Language:** Russian
- **Indexed:** `false`

Document ids:
`CORP-RU-AV-001`, `CORP-RU-AV-002`, `CORP-RU-AV-003`, `CORP-RU-AV-004`, `CORP-RU-AV-005`, `CORP-RU-AV-006`, `CORP-RU-AV-007`, `CORP-RU-AV-008`, `CORP-RU-AV-009`, `CORP-RU-AV-010`, `CORP-RU-AV-011`, `CORP-RU-AV-012`, `CORP-RU-AV-013`, `CORP-RU-AV-014`, `CORP-RU-AV-015`, `CORP-RU-AV-016`.

## Files Created/Modified

- `ai-service/eval/schema.py` - Pydantic schemas for golden records, corpus metadata, runner config, metrics, and reports.
- `ai-service/eval/io.py` - JSON/JSONL helpers plus deterministic corpus hash calculation.
- `ai-service/eval/validate_corpus.py` - CLI validator for the frozen corpus snapshot.
- `ai-service/eval/corpus/` - committed Russian demo corpus and manifest.
- `ai-service/eval/golden/golden_ru.meta.json` - corpus version/hash metadata and indexing status.
- `ai-service/eval/reporting.py` - shared report writer.
- `ai-service/pyproject.toml` - packages `eval` with the ai-service project.

## Decisions Made

- Kept the corpus as hand-written Markdown documents to avoid hidden regeneration drift.
- Used document-level ids as the stable binding target for later golden records; exact chunk ids remain advisory and will be discovered after indexing.
- Left `golden_ru.meta.json.indexed=false` because indexing could not be executed without a running local stack.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The Docker stack is not running, so Task 4 indexing could not be completed. Plan 07-05 golden answer authoring is blocked until the frozen corpus is indexed and `golden_ru.meta.json` is updated with indexed document ids/evidence. Plan 07-04 code work can still proceed because it only adds eval-only retrieval modes.

## Verification

- PASS: `uv run python -m eval.validate_corpus` from `ai-service/`
- PASS: `uv run --project ai-service --group dev pytest ai-service/tests` — 236 passed, 12 skipped, 1 warning.

## User Setup Required

Before Plan 07-05, start the local stack and index the frozen corpus:

```powershell
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build
uv run python -m eval.validate_corpus
```

The actual upload/indexing commands depend on the live Java auth/session path and should record returned document ids in the Phase 7 UAT evidence.

## Next Phase Readiness

Plan 07-04 can proceed with eval-only retrieval mode and BM25 harness code. Plan 07-05 must wait for corpus indexing evidence.

## Self-Check: PASSED

- Summary exists and references all 07-03 production commits.
- Corpus validator confirms exactly 16 Russian documents and matching manifest hash.
- Report writer tests pass and report paths stay under `ai-service/eval/reports/`.
- No golden answers were authored before indexing.

---
*Phase: 07-evaluation-observability*
*Completed: 2026-06-01*
