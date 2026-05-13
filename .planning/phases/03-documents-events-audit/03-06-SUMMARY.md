---
phase: 03-documents-events-audit
plan: 06
subsystem: events
tags: [rabbitmq, spring-amqp, idempotency, documents, audit]

requires:
  - phase: 03-documents-events-audit
    provides: document lifecycle events, outbox publication, RabbitMQ topology
provides:
  - Transactional processed_events insert-first consumer idempotency
  - Java consumers for document.indexed and document.indexing.failed
  - Terminal document status updates that never resurrect soft-deleted rows
  - DOCUMENT_INDEXED and DOCUMENT_INDEXING_FAILED audit coverage with correlation propagation
  - Full Phase 3 Java lifecycle verification path
affects: [phase-03, phase-04, ai-service-indexing, document-events, audit]

tech-stack:
  added: []
  patterns:
    - transactional idempotent AMQP processing
    - correlation restoration from AMQP headers into MDC
    - terminal document status updates guarded by active-row predicates
    - Docker-gated lifecycle integration tests

key-files:
  created:
    - backend/corp-rag-app/src/main/java/com/corprag/adapter/amqp/AmqpConsumerSupport.java
    - backend/corp-rag-app/src/main/java/com/corprag/adapter/amqp/DocumentIndexedConsumer.java
    - backend/corp-rag-app/src/main/java/com/corprag/adapter/amqp/DocumentIndexingFailedConsumer.java
    - backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentIndexedEvent.java
    - backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentIndexingFailedEvent.java
    - backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentIndexingResultService.java
    - backend/corp-rag-app/src/main/java/com/corprag/service/events/EventEnvelopeMetadata.java
    - backend/corp-rag-app/src/main/java/com/corprag/service/events/IdempotentEventHandler.java
    - backend/corp-rag-app/src/main/java/com/corprag/service/events/IdempotentEventProcessor.java
    - backend/corp-rag-app/src/main/java/com/corprag/service/events/IdempotentEventResult.java
    - backend/corp-rag-app/src/main/java/com/corprag/service/events/InboundEventMetadata.java
    - backend/corp-rag-app/src/test/java/com/corprag/DocumentLifecycleFlowIT.java
    - backend/corp-rag-app/src/test/java/com/corprag/adapter/amqp/DocumentIndexedConsumerTest.java
    - backend/corp-rag-app/src/test/java/com/corprag/adapter/amqp/DocumentIndexingFailedConsumerTest.java
    - backend/corp-rag-app/src/test/java/com/corprag/service/document/DocumentIndexingResultServiceTest.java
    - backend/corp-rag-app/src/test/java/com/corprag/service/events/IdempotentEventProcessorIT.java
    - backend/corp-rag-app/src/test/java/com/corprag/service/events/IdempotentEventProcessorTest.java
  modified:
    - .env.example
    - backend/corp-rag-app/src/main/java/com/corprag/repository/DocumentRepository.java
    - backend/corp-rag-app/src/main/resources/application.yml
    - backend/corp-rag-app/src/test/java/com/corprag/repository/DocumentPersistenceIT.java
    - infra/docker-compose.yml

key-decisions:
  - "Indexing-result consumers are disabled by default and enabled by compose so ordinary tests do not require a live RabbitMQ broker."
  - "Consumer idempotency inserts processed_events before business handling and rolls back that insert on handler failure."
  - "Late terminal events for soft-deleted documents are recorded as processed without changing document status or audit details."
  - "Correlation prefers a valid x-correlation-id AMQP header, then envelope metadata, then a generated UUID."

patterns-established:
  - "IdempotentEventProcessor centralizes insert-first processing, duplicate ACK-safe results, rollback behavior, and retention cleanup."
  - "Document terminal updates use active UPLOADED predicates so deleted or already-terminal rows are not mutated by late events."

requirements-completed: ["DOC-03", "EVT-02", "AUD-01"]

duration: 26 min
completed: 2026-05-13
---

# Phase 03 Plan 06: Indexing Result Consumers Summary

**Idempotent Java indexing-result consumers with terminal document updates, audit correlation, and lifecycle verification**

## Performance

- **Duration:** 26 min
- **Started:** 2026-05-13T20:38:40Z
- **Completed:** 2026-05-13T21:04:00Z
- **Tasks:** 3
- **Files modified:** 22

## Accomplishments

- Added a transactional `IdempotentEventProcessor` using `processed_events` insert-first semantics, duplicate detection, rollback on handler failure, and scheduled retention cleanup.
- Added `document.indexed` and `document.indexing.failed` Spring AMQP consumers with event type validation, correlation MDC restoration, idempotent processing, status updates, and detailed audit rows.
- Guarded terminal status updates so active `UPLOADED` rows can move to `INDEXED` or `INDEXING_FAILED`, while deleted or already-terminal rows remain unchanged.
- Added focused unit/integration coverage plus a Phase 3 lifecycle integration test covering upload, visibility, raw URL audit, delete/outbox, indexed/failed consumers, duplicates, and late deleted events.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement idempotent event processing support** - `161dcb5` (feat)
2. **Task 2: Implement indexed and failed consumers with status/audit updates** - `842ce2d` (feat)
3. **Task 3: Add full Phase 3 lifecycle verification** - `289bce7` (test)

**Plan metadata:** this summary commit

## Files Created/Modified

- `backend/corp-rag-app/src/main/java/com/corprag/service/events/IdempotentEventProcessor.java` - Central transactional idempotency coordinator for inbound events.
- `backend/corp-rag-app/src/main/java/com/corprag/service/events/InboundEventMetadata.java` - Inbound event identity, type, source, and correlation metadata.
- `backend/corp-rag-app/src/main/java/com/corprag/service/events/IdempotentEventResult.java` - Indicates processed versus duplicate outcomes.
- `backend/corp-rag-app/src/main/java/com/corprag/service/events/IdempotentEventHandler.java` - Functional handler contract executed only for first-seen events.
- `backend/corp-rag-app/src/main/java/com/corprag/service/events/EventEnvelopeMetadata.java` - Shared event envelope metadata parser model.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/amqp/AmqpConsumerSupport.java` - Shared JSON parsing, event-type validation, correlation fallback, and MDC handling.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/amqp/DocumentIndexedConsumer.java` - Consumes `document.indexed` events from the generated backend indexed queue.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/amqp/DocumentIndexingFailedConsumer.java` - Consumes `document.indexing.failed` events from the generated backend failed queue.
- `backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentIndexedEvent.java` - Parsed indexed-event payload record.
- `backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentIndexingFailedEvent.java` - Parsed indexing-failed-event payload record.
- `backend/corp-rag-app/src/main/java/com/corprag/service/document/DocumentIndexingResultService.java` - Applies terminal status transitions and writes indexed/failed audit events.
- `backend/corp-rag-app/src/main/java/com/corprag/repository/DocumentRepository.java` - Adds active-row terminal update methods guarded by `status = 'UPLOADED'` and `deleted_at IS NULL`.
- `backend/corp-rag-app/src/main/resources/application.yml` - Adds processed-event retention and indexing consumer enablement settings.
- `backend/corp-rag-app/src/test/java/com/corprag/DocumentLifecycleFlowIT.java` - End-to-end Java lifecycle verification for Phase 3.
- `backend/corp-rag-app/src/test/java/com/corprag/adapter/amqp/DocumentIndexedConsumerTest.java` - Covers indexed consumer parsing, correlation, duplicates, and MDC cleanup.
- `backend/corp-rag-app/src/test/java/com/corprag/adapter/amqp/DocumentIndexingFailedConsumerTest.java` - Covers failed consumer parsing, correlation fallback, and validation behavior.
- `backend/corp-rag-app/src/test/java/com/corprag/service/document/DocumentIndexingResultServiceTest.java` - Covers terminal update and audit details.
- `backend/corp-rag-app/src/test/java/com/corprag/service/events/IdempotentEventProcessorIT.java` - Verifies transactional processed_events insert and rollback behavior.
- `backend/corp-rag-app/src/test/java/com/corprag/service/events/IdempotentEventProcessorTest.java` - Verifies duplicate skip and retention cutoff behavior.
- `backend/corp-rag-app/src/test/java/com/corprag/repository/DocumentPersistenceIT.java` - Extends persistence coverage for terminal indexing updates and deleted-row guards.
- `.env.example` and `infra/docker-compose.yml` - Wire compose-time enablement for Java indexing-result consumers.

## Decisions Made

- Indexing-result consumers are disabled by default and enabled in compose so unit and slice tests do not attempt RabbitMQ connections unless explicitly configured.
- `processed_events` insert-first idempotency is centralized in one service so both current consumers and future inbound event handlers share duplicate and rollback behavior.
- Soft-deleted documents are treated as terminal from the Java side: late Python results are recorded as processed but cannot update status or resurrect visibility.
- A valid AMQP `x-correlation-id` header wins over envelope metadata to preserve the HTTP-to-outbox-to-Python-to-Java audit chain.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added explicit consumer enablement wiring**
- **Found during:** Task 2 (Implement indexed and failed consumers with status/audit updates)
- **Issue:** New `@RabbitListener` beans would otherwise try to connect in ordinary backend test contexts, while compose needed an explicit way to turn them on.
- **Fix:** Added `app.document-indexing-consumers.enabled`, disabled it by default, and enabled it through `.env.example` and `infra/docker-compose.yml`.
- **Files modified:** `backend/corp-rag-app/src/main/resources/application.yml`, `.env.example`, `infra/docker-compose.yml`, consumer classes
- **Verification:** `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test` and `verify` passed.
- **Committed in:** `842ce2d`

---

**Total deviations:** 1 auto-fixed (1 missing critical functionality).
**Impact on plan:** The toggle is operational wiring required for correct test and compose behavior; no feature scope was added.

## Issues Encountered

- Plain `python.exe` is not available in this Windows runner, so the contract verifier was run through the repository Python environment with `uv run --project ai-service python scripts\verify-contracts.py`.
- Docker is unavailable to Testcontainers in this runner. Docker-gated integration tests are compiled and wired with `@Testcontainers(disabledWithoutDocker = true)`; they will execute when Docker is available and are not silently skipped in that environment.

## Verification

- `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test` passed.
- `$env:MAVEN_CMD='C:\dev\apache-maven-3.9.15\bin\mvn.cmd'; uv run --project ai-service python scripts\verify-contracts.py` passed.
- `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am verify` passed.
- Stub scan across created/modified production and test files found no TODO, FIXME, placeholder, or mock-empty data left in the implemented path.

## Threat Flags

None - the new RabbitMQ-to-Java consumer trust boundary, duplicate-delivery handling, correlation audit, rollback behavior, and deleted-document race were all covered by the plan threat model.

## Known Stubs

None.

## User Setup Required

None - compose and `.env.example` include the indexing consumer enablement setting.

## Next Phase Readiness

Phase 4 can publish Python indexing results to the generated backend queues and rely on Java idempotency, correlation propagation, terminal status updates, and audit details. Phase 3 is ready for verify-work; full Docker-backed lifecycle execution should be rerun in an environment with Docker available.

## Self-Check: PASSED

- Summary file exists at `.planning/phases/03-documents-events-audit/03-06-SUMMARY.md`.
- Task commits found: `161dcb5`, `842ce2d`, `289bce7`.
- Requirements copied from PLAN frontmatter.
- Automated verification passed within the runner limitations documented above.

---
*Phase: 03-documents-events-audit*
*Completed: 2026-05-13*
