---
phase: "03-documents-events-audit"
plan: "02"
subsystem: database
tags: [postgres, jdbc, documents, outbox, audit, correlation]
requires:
  - phase: "03-01"
    provides: "Phase 3 document REST, event, and constants contract alignment"
provides:
  - "Document metadata schema with active duplicate protection and soft delete"
  - "Transactional outbox and processed-event persistence foundations"
  - "JDBC repositories for document visibility, outbox polling, and idempotent consumers"
  - "Request correlation ID propagation through response headers, ProblemDetail, and audit rows"
affects: ["03-documents-events-audit", "04-python-ingestion-indexing", "java-backend"]
tech-stack:
  added: []
  patterns:
    - "Repository-owned SQL visibility predicates from ResolvedAccessFilter"
    - "MDC-backed correlation ID propagation at the request edge"
key-files:
  created:
    - "backend/corp-rag-app/src/main/resources/db/migration/V11__create_documents_table.sql"
    - "backend/corp-rag-app/src/main/resources/db/migration/V12__create_outbox_events_table.sql"
    - "backend/corp-rag-app/src/main/resources/db/migration/V13__create_processed_events_table.sql"
    - "backend/corp-rag-app/src/main/java/com/corprag/domain/DocumentRecord.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/repository/DocumentRepository.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/repository/OutboxEventRepository.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/repository/ProcessedEventRepository.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/security/CorrelationIdFilter.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/repository/DocumentPersistenceIT.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/security/CorrelationIdFilterTest.java"
  modified:
    - "backend/corp-rag-app/src/main/java/com/corprag/config/SecurityConfig.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/ProblemDetailsWriter.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/audit/AuditEventWriter.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/service/audit/AuditEventWriterTest.java"
key-decisions:
  - "DocumentRepository owns SQL visibility predicates so later controllers and services do not filter documents in memory."
  - "Invalid or absent X-Correlation-Id headers are replaced with generated UUIDs instead of rejecting requests."
  - "Outbox payload and headers stay as JSONB at the persistence boundary; later services will own event-envelope construction."
patterns-established:
  - "Document rows are visible only through active-row, doc type, department, and access-level SQL predicates."
  - "Processed-event inserts use ON CONFLICT DO NOTHING to model duplicate delivery as a boolean result."
  - "ProblemDetail and AuditEventWriter read the same MDC correlationId populated by CorrelationIdFilter."
requirements-completed: ["DOC-01", "DOC-02", "DOC-03", "EVT-01", "EVT-02", "AUD-01"]
duration: "12 min"
completed: "2026-05-13"
---

# Phase 03 Plan 02: Persistence, Repository, and Correlation Foundation Summary

**PostgreSQL document/event schema with JDBC visibility repositories and MDC-backed request correlation**

## Performance

- **Duration:** 12 min
- **Started:** 2026-05-13T22:00:37+03:00
- **Completed:** 2026-05-13T22:12:23+03:00
- **Tasks:** 3
- **Files modified:** 18

## Accomplishments

- Added `documents`, `outbox_events`, and `processed_events` Flyway migrations with partial duplicate protection, soft-delete fields, JSONB outbox payloads, retry/backoff fields, and idempotent consumer ledger keys.
- Added document, outbox, and processed-event domain records plus JDBC repositories that expose focused Phase 3 primitives for later services.
- Centralized document visibility in SQL predicates derived from `ResolvedAccessFilter`, including department wildcard semantics.
- Added `CorrelationIdFilter` and wired MDC correlation IDs into response headers, `ProblemDetail`, and `AuditEventWriter`.

## Task Commits

1. **Task 1: Add document, outbox, and processed-event migrations** - `c5d8eca` (feat)
2. **Task 2: Add domain records and JDBC repository foundations** - `bb48caf` (feat)
3. **Task 3: Add correlation ID filter and MDC-aware audit/problem details** - `7c6c930` (feat)

**Plan metadata:** this summary commit

## Files Created/Modified

- `backend/corp-rag-app/src/main/resources/db/migration/V11__create_documents_table.sql` - Creates document metadata, status, indexing, storage, and soft-delete schema with active duplicate partial unique index.
- `backend/corp-rag-app/src/main/resources/db/migration/V12__create_outbox_events_table.sql` - Creates transactional outbox rows with JSONB payload/headers and retry/backoff columns.
- `backend/corp-rag-app/src/main/resources/db/migration/V13__create_processed_events_table.sql` - Creates processed-event idempotency ledger keyed by `event_id`.
- `backend/corp-rag-app/src/main/java/com/corprag/repository/DocumentRepository.java` - Provides insert, visible lookup/page, active duplicate lookup, soft delete, indexed, and indexing-failed updates.
- `backend/corp-rag-app/src/main/java/com/corprag/repository/OutboxEventRepository.java` - Provides insert, ready unpublished polling with `FOR UPDATE SKIP LOCKED`, publish/failure marking, and cleanup.
- `backend/corp-rag-app/src/main/java/com/corprag/repository/ProcessedEventRepository.java` - Provides insert-if-absent and cleanup support for idempotent consumers.
- `backend/corp-rag-app/src/main/java/com/corprag/security/CorrelationIdFilter.java` - Normalizes or generates request correlation IDs, writes response headers, and clears MDC.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/ProblemDetailsWriter.java` - Adds MDC correlation ID to generated problem details.
- `backend/corp-rag-app/src/main/java/com/corprag/service/audit/AuditEventWriter.java` - Reuses MDC correlation ID for audit rows with fallback generation for background/system work.
- `backend/corp-rag-app/src/test/java/com/corprag/repository/DocumentPersistenceIT.java` - Covers duplicate constraints, SQL visibility, outbox polling, and processed-event idempotency.
- `backend/corp-rag-app/src/test/java/com/corprag/security/CorrelationIdFilterTest.java` - Covers valid, missing, invalid, and cleanup correlation behavior.

## Decisions Made

- Document visibility stays in repository SQL and is not left for controllers or services to apply after pagination/counting.
- Invalid caller correlation IDs are sanitized by replacement to preserve request processing while keeping trace IDs valid UUIDs.
- Outbox repository stores raw JSONB payload/header documents; later event services will own typed payload construction and AMQP metadata decisions.

## Deviations from Plan

None - plan executed within the intended schema, repository, and correlation foundation scope.

## Issues Encountered

- Task 2 initially had a test helper constructor arity mismatch after adding the full document record shape. It was corrected before the task commit and the Maven gate passed afterward.
- The Maven test target logs a local Docker/Testcontainers discovery warning in this environment. Tests still completed successfully with exit code 0.

## Verification

- PASS: `cd backend; C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test`
- PASS: migration files exist as V11, V12, and V13 after the existing V10 sequence.
- PASS: `documents` includes `deleted_at`, `deleted_by`, and the active duplicate partial unique index.
- PASS: `outbox_events` includes JSONB payload/headers, retry/backoff columns, and ready unpublished indexes.
- PASS: `processed_events.event_id` is the primary key and repository insert uses `ON CONFLICT DO NOTHING`.
- PASS: correlation ID tests cover response header reuse/generation, `ProblemDetail.correlationId`, audit MDC reuse, and MDC cleanup.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 03-03 can build the upload pipeline on top of stable document metadata inserts, duplicate detection, storage fields, transactional outbox inserts, and request correlation. Later outbox publisher and indexing-result consumer plans have the required persistence primitives in place.

## Self-Check: PASSED

- All three plan tasks have production commits.
- `03-02-SUMMARY.md` documents commits, verification, deviations, issues, and next-plan readiness.
- The required plan verification command passed after all code changes.

---
*Phase: 03-documents-events-audit*
*Completed: 2026-05-13*
