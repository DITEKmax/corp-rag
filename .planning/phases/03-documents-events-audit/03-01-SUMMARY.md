---
phase: "03-documents-events-audit"
plan: "01"
subsystem: contracts
tags: [openapi, asyncapi, constants, documents, events, audit]
requires:
  - phase: "02-identity-users-access-control"
    provides: "RBAC permissions, access policy semantics, audit foundation, and contract verification baseline"
provides:
  - "Phase 3 REST contract for document upload, listing, detail, raw URL, and soft delete"
  - "Phase 3 document upload error-code constants"
  - "Document lifecycle event payload metadata for Python ingestion"
affects: ["03-documents-events-audit", "04-python-ingestion-indexing", "java-backend", "python-ai"]
tech-stack:
  added: []
  patterns: ["contract-first document lifecycle changes before Java/Python implementation"]
key-files:
  created:
    - ".planning/phases/03-documents-events-audit/03-01-SUMMARY.md"
  modified:
    - "contracts/openapi/api-v1.yaml"
    - "contracts/asyncapi/events-v1.yaml"
    - "contracts/constants.yaml"
key-decisions:
  - "None beyond locked Phase 3 decisions; execution followed the plan."
patterns-established:
  - "Document delete is contracted as immediate soft delete for visible active documents with no status-based conflict."
  - "Document upload duplicate errors use ProblemDetail.details.existingDocumentId."
  - "document.uploaded carries title and contentSha256 so Python ingestion does not need to call Java for base metadata."
requirements-completed: ["DOC-01", "DOC-02", "DOC-03", "EVT-01", "EVT-02", "AUD-01"]
duration: "31 min"
completed: "2026-05-13"
---

# Phase 03 Plan 01: Contract-First Document Lifecycle Summary

**Phase 3 document REST, error-code, and lifecycle-event contracts for Java implementation and Python ingestion**

## Performance

- **Duration:** 31 min
- **Started:** 2026-05-13T21:17:00+03:00
- **Completed:** 2026-05-13T21:48:12+03:00
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Updated document REST contract semantics for active-row visibility, 5-minute raw MinIO URLs, reserved `INDEXING`, immediate soft delete, and `ProblemDetail.details`.
- Added `INSUFFICIENT_ACCESS_LEVEL`, `DUPLICATE_DOCUMENT`, and `UNSUPPORTED_FILE_TYPE` constants and wired upload responses/examples.
- Extended `document.uploaded` AsyncAPI payload with required `title` and `contentSha256`.

## Task Commits

1. **Task 1: Align document REST contract with Phase 3 decisions** - `a4cabe7` (feat)
2. **Task 2: Add Phase 3 error constants and REST error references** - `584902b` (feat)
3. **Task 3: Align document event payload contract for downstream ingestion** - `7c3dbbb` (feat)

**Plan metadata:** this summary commit

## Files Created/Modified

- `contracts/openapi/api-v1.yaml` - Defines Phase 3 document REST visibility, upload, raw URL, delete, status, and ProblemDetail details semantics.
- `contracts/constants.yaml` - Adds Phase 3 document upload error codes for generated Java/Python constants.
- `contracts/asyncapi/events-v1.yaml` - Adds document title and SHA-256 content digest to `document.uploaded`.

## Decisions Made

None beyond locked Phase 3 decisions; execution followed the plan.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Direct `python` was unavailable in this runner; verification was run through the existing `ai-service` uv environment.
- The first sandboxed uv run could not access the local uv cache, so contract verification was re-run with approved escalated permissions.

## Verification

- `$env:MAVEN_CMD='C:\dev\apache-maven-3.9.15\bin\mvn.cmd'; uv run --project ai-service python scripts\verify-contracts.py` - passed.
- Verification covered YAML lint, constants generation, `corp-rag-contracts` Maven generate-sources/compile, Python contract generation, and generated Python imports.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `03-02-PLAN.md`: Java schema, repositories, and correlation foundation can consume the updated contracts.

## Self-Check: PASSED

- `03-01-SUMMARY.md` exists.
- Task commits exist for all three tasks.
- Plan-level contract verification passed after Task 3.
- Acceptance checks are reflected in the changed contract files.

---
*Phase: 03-documents-events-audit*
*Completed: 2026-05-13*
