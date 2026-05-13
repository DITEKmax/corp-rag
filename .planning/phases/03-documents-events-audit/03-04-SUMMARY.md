---
phase: "03-documents-events-audit"
plan: "04"
subsystem: "documents"
tags: ["spring-boot", "documents", "rbac", "minio", "outbox", "audit"]
requires:
  - phase: "03-documents-events-audit/03-03"
    provides: "document upload, MinIO storage metadata, presign support, outbox service, and audit foundations"
provides:
  - "Visible document list/detail APIs with SQL access filtering and contract filters"
  - "Audited raw document URL issuance through 5-minute MinIO presigned URLs"
  - "Immediate soft delete with document.deleted outbox rows and delete audit details"
affects: ["03-05-outbox-publisher", "03-06-indexing-consumers", "04-ai-indexing", "frontend-documents"]
tech-stack:
  added: []
  patterns:
    - "Service-owned document read/delete use cases backed by repository SQL visibility"
    - "Permission-aware HATEOAS link assembly"
    - "Outbox event construction for upload and delete lifecycle events"
key-files:
  created:
    - "backend/corp-rag-app/src/main/java/com/corprag/domain/DocumentSearchCriteria.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentQueryService.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentRawUrl.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentRawUrlService.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentDeletionService.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/service/document/DocumentQueryServiceTest.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/service/document/DocumentRawUrlServiceTest.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/service/document/DocumentDeletionServiceTest.java"
  modified:
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/DocumentController.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/DocumentAssembler.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/repository/DocumentRepository.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/outbox/OutboxService.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/DocumentControllerTest.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/service/outbox/OutboxServiceTest.java"
key-decisions:
  - "List/detail/raw/delete all reuse repository SQL visibility derived from ResolvedAccessFilter."
  - "Raw URL issuance is audited at presign time; Java does not stream or proxy object bytes."
  - "Delete never checks document status and emits document.deleted in the same transaction as the soft delete."
patterns-established:
  - "DocumentSearchCriteria layers contract filters inside the visible active set before pagination/counting."
  - "DocumentDeletionService captures the pre-delete document record for audit/outbox details before soft deletion."
  - "OutboxService now emits document.deleted envelopes and event-specific AMQP headers."
requirements-completed: ["DOC-02", "EVT-01", "AUD-01"]
duration: "21 min"
completed: "2026-05-13"
---

# Phase 03 Plan 04 Summary: Document Read, Raw URL, and Delete APIs

**Visible document management APIs with audited raw URL issuance and transactional soft-delete events**

## Performance

- **Duration:** 21 min
- **Started:** 2026-05-13T19:52:00Z
- **Completed:** 2026-05-13T20:13:27Z
- **Tasks:** 3
- **Files modified:** 14

## Accomplishments

- Added `GET /api/v1/documents` and `GET /api/v1/documents/{documentId}` with `documents.read`, SQL visibility filtering, contract query filters, paging totals, and permission-aware links.
- Added `GET /api/v1/documents/{documentId}/raw` with the same visibility check, 5-minute MinIO presigned URLs, and `DOCUMENT_RAW_URL_ISSUED` audit rows.
- Added `DELETE /api/v1/documents/{documentId}` with `documents.delete`, immediate soft delete, `document.deleted` outbox envelopes, and `DOCUMENT_DELETED` audit details.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement visible document list and detail** - `54ec6f3` (feat)
2. **Task 2: Implement raw document presigned URL endpoint** - `eae3414` (feat)
3. **Task 3: Implement soft delete and document.deleted outbox event** - `d5f9dc5` (feat)

**Plan metadata:** this summary commit

## Files Created/Modified

- `DocumentSearchCriteria.java` - Contract list filters applied inside the visible document set.
- `DocumentQueryService.java` - List/detail use case resolving `ResolvedAccessFilter` before repository reads.
- `DocumentRawUrlService.java` - Visible raw URL issuance, storage presign call, 5-minute expiry, and audit event.
- `DocumentDeletionService.java` - Transactional visible soft delete, `document.deleted` outbox row, and delete audit event.
- `DocumentRepository.java` - Visible paging now supports status, department, doc type, language, and title/filename search filters.
- `OutboxService.java` - Adds AsyncAPI-compatible `document.deleted` envelope/header creation.
- `DocumentController.java` - Exposes list/detail/raw/delete endpoints with contract permissions and responses.
- `DocumentAssembler.java` - Builds permission-aware document links and paged document responses.

## Decisions Made

- Followed the existing Phase 3 decision set: repository SQL is the single visibility enforcement point for document reads and deletes.
- Presigned raw URL auditing records issuance only, not downstream MinIO download completion.
- Delete remains status-agnostic; uploaded, indexed, and indexing-failed documents all soft-delete through the same path.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The direct `python scripts\verify-contracts.py` command cannot run in this Windows environment because `python.exe` is unavailable. The same contract verifier passed through the repo `uv` environment with `MAVEN_CMD` set to the local Maven binary.
- The full Maven test gate logs Docker/Testcontainers discovery warnings because Docker is not available to this runner. Docker-disabled Testcontainers tests are skipped and the Maven suite exits successfully.
- Spring needed explicit `@Autowired` on services with both production and package-private test constructors; this was fixed before the relevant task commits.

## Verification

- PASS: `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test` after Task 1.
- PASS: `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test` after Task 2.
- PASS: `$env:MAVEN_CMD='C:\dev\apache-maven-3.9.15\bin\mvn.cmd'; uv run --project ai-service python scripts\verify-contracts.py`.
- PASS: `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test` after Task 3.
- PASS: List/detail/raw/delete tests cover hidden documents returning `DOCUMENT_NOT_FOUND`.
- PASS: Delete tests cover `UPLOADED`, `INDEXED`, and `INDEXING_FAILED` without status-based conflicts.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 03-05 can publish both `document.uploaded` and `document.deleted` rows from the outbox using generated routing constants and the existing RabbitMQ compose service. Plan 03-06 can rely on soft-deleted documents disappearing immediately from list/detail/raw while late indexing events remain a consumer concern.

## Self-Check: PASSED

- All three plan tasks have production commits.
- `03-04-SUMMARY.md` documents commits, verification, deviations, issues, and next-plan readiness.
- The required plan verification commands passed using the available local toolchain.

---
*Phase: 03-documents-events-audit*
*Completed: 2026-05-13*
