---
phase: "04-python-ingestion-indexing"
plan: "03"
subsystem: "ingestion-parsing"
tags: ["python", "parsing", "docling", "markdown-it-py", "trafilatura", "pydantic"]

requires:
  - phase: "04-02"
    provides: "AI ingestion state, AMQP adapters, and safe StageFailure reporting"
provides:
  - "Normalized ParsedDocument and ParsedBlock domain contract with deterministic positions and section paths"
  - "MIME dispatcher for PDF, DOCX, HTML, Markdown, and plain text parser routes"
  - "Markdown, HTML, plain-text, and Docling-backed parser adapters with StageFailure mapping"
affects: ["04-04", "04-07", "phase-5-retrieval"]

tech-stack:
  added: ["markdown-it-py>=4.2.0,<5.0.0", "trafilatura>=2.0.0,<3.0.0", "docling>=2.93.0,<3.0.0"]
  patterns: ["normalized sectioned document model", "safe parser-stage failure mapping", "Docling Markdown export fallback"]

key-files:
  created:
    - "ai-service/src/corp_rag_ai/domain/document.py"
    - "ai-service/src/corp_rag_ai/pipeline/ingestion/parsers/base.py"
    - "ai-service/src/corp_rag_ai/pipeline/ingestion/parsers/markdown.py"
    - "ai-service/src/corp_rag_ai/pipeline/ingestion/parsers/html.py"
    - "ai-service/src/corp_rag_ai/pipeline/ingestion/parsers/plain_text.py"
    - "ai-service/src/corp_rag_ai/pipeline/ingestion/parsers/docling_parser.py"
    - "ai-service/tests/test_document_parser_contract.py"
    - "ai-service/tests/test_text_document_parsers.py"
    - "ai-service/tests/test_docling_parser.py"
  modified:
    - "ai-service/pyproject.toml"
    - "ai-service/uv.lock"
    - "ai-service/src/corp_rag_ai/domain/exceptions.py"

key-decisions:
  - "StageFailure is now raiseable so parser adapters can fail with the same object later used for safe failed-event payloads."
  - "Docling PDF/DOCX parsing uses Markdown export plus the shared Markdown normalizer; this keeps block normalization deterministic while recording that direct page metadata is not retained."
  - "Parser outputs are normalized into the locked ParsedBlock fields only, with parser-native metadata excluded from the domain model."

patterns-established:
  - "Parser adapters raise StageFailure at the adapter boundary instead of leaking library exceptions."
  - "Section paths are assigned in one normalization pass using heading-level truncation."
  - "Text-like parser paths share the same ParsedBlockDraft to ParsedDocument normalization."

requirements-completed: ["ING-02"]

duration: "8 min"
completed: 2026-05-17
---

# Phase 04 Plan 03: Normalized Document Parsing Summary

**Sectioned ParsedDocument pipeline for PDF, DOCX, HTML, Markdown, and plain-text ingestion**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-17T18:24:14+03:00
- **Completed:** 2026-05-17T18:31:38+03:00
- **Tasks:** 3
- **Files modified:** 16

## Accomplishments

- Added Pydantic `ParsedBlock` and `ParsedDocument` models plus deterministic block normalization for 0-based positions and nested `section_path` assignment.
- Added a MIME dispatcher covering PDF, DOCX, HTML, Markdown, and plain text, with unsupported MIME mapped to `PARSING / UNSUPPORTED_FILE_TYPE`.
- Implemented Markdown, HTML, plain-text, and Docling-backed parser adapters with safe `PARSING / INVALID_FILE_FORMAT` failure mapping.
- Added parser coverage for nested sections, list items, tables, boilerplate removal, empty-text rejection, Docling fallback behavior, and sanitized conversion errors.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add ParsedDocument domain model and parser registry** - `df7c034` (feat)
2. **Task 2: Implement Markdown, HTML, and plain-text parsers** - `420bf13` (feat)
3. **Task 3: Spike and implement Docling parser path** - `bde4f28` (feat)

## Files Created/Modified

- `ai-service/src/corp_rag_ai/domain/document.py` - Locked parsed document/block models and normalization helper.
- `ai-service/src/corp_rag_ai/pipeline/ingestion/parsers/base.py` - Parser protocol and MIME dispatcher.
- `ai-service/src/corp_rag_ai/pipeline/ingestion/parsers/markdown.py` - Markdown block extraction for headings, paragraphs, list items, preformatted blocks, and tables.
- `ai-service/src/corp_rag_ai/pipeline/ingestion/parsers/html.py` - Trafilatura main-content extraction routed through Markdown normalization.
- `ai-service/src/corp_rag_ai/pipeline/ingestion/parsers/plain_text.py` - Plain-text parser with empty-content rejection.
- `ai-service/src/corp_rag_ai/pipeline/ingestion/parsers/docling_parser.py` - Docling PDF/DOCX adapter using Markdown export fallback.
- `ai-service/tests/test_document_parser_contract.py` - Domain contract, normalization, and unsupported MIME coverage.
- `ai-service/tests/test_text_document_parsers.py` - Markdown, HTML, and plain-text parser coverage.
- `ai-service/tests/test_docling_parser.py` - Docling fallback and sanitized error mapping coverage.
- `ai-service/pyproject.toml` and `ai-service/uv.lock` - Parser dependency additions.

## Decisions Made

- StageFailure now subclasses `Exception` so parser code can raise it directly while preserving the existing safe payload formatting API.
- Docling structured traversal was not locked into the adapter because the stable documented path is whole-document Markdown export; the adapter records the page metadata tradeoff in `parse_warnings`.
- Markdown export from HTML and Docling is normalized through the same Markdown parser so downstream chunking sees one consistent sectioned block model.

## Deviations from Plan

None - plan executed within the documented fallback path.

## Issues Encountered

None.

## Verification

- `uv run pytest tests` - 28 passed.
- `uv run python -c "from corp_rag_ai.pipeline.ingestion.parsers import build_default_parser_dispatcher; dispatcher=build_default_parser_dispatcher(); print('\\n'.join(sorted(dispatcher.supported_mime_types)))"` - passed; dispatcher exposes PDF, DOCX, HTML, XHTML, Markdown, and plain text routes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `04-04-PLAN.md`: chunking can consume normalized `ParsedDocument` blocks with deterministic positions, section paths, block types, and parser-stage failures already mapped.

---
*Phase: 04-python-ingestion-indexing*
*Completed: 2026-05-17*
