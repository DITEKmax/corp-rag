---
phase: "03-documents-events-audit"
verified: "2026-05-13T21:22:58Z"
status: "human_needed"
score: "23/23 must-haves verified"
overrides_applied: 0
human_verification:
  - test: "Run a Docker-backed Phase 3 lifecycle smoke against real PostgreSQL, MinIO, and RabbitMQ."
    expected: "A supported document upload stores the object in MinIO, persists metadata/status in PostgreSQL, emits document.uploaded and document.deleted through the outbox to RabbitMQ, consumes document.indexed and document.indexing.failed messages idempotently, and writes correlated audit rows."
    why_human: "The verifier environment has no valid Docker/Testcontainers runtime, so live MinIO/RabbitMQ integration cannot be proven here. Code, contract generation, unit/slice tests, and Docker-gated lifecycle IT wiring were verified."
---

# Phase 3: Documents, Events & Audit Verification Report

**Phase Goal:** Java owns document metadata, object storage orchestration, document events, indexing status updates, and audit logging.
**Verified:** 2026-05-13T21:22:58Z
**Status:** human_needed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Authorized user can upload a document with metadata and retrieve document listings/details. | VERIFIED | `DocumentController` maps upload/list/detail/raw/delete routes and checks `documents.upload/read/delete` permissions (`DocumentController.java:64-159`). Upload/list/detail behavior is covered by `DocumentControllerTest` and `DocumentLifecycleFlowIT.java:108-121`. |
| 2 | Java stores document files in MinIO and metadata/status in PostgreSQL. | VERIFIED | `DocumentUploadService` checks duplicates, writes MinIO before DB, then inserts metadata/outbox/audit in one transaction (`DocumentUploadService.java:90-116`). `V11__create_documents_table.sql` stores metadata/status/failure/indexing fields and active duplicate index. |
| 3 | Document upload/delete events are persisted through the outbox and published to RabbitMQ. | VERIFIED | Upload/delete services call `OutboxService`; outbox rows are polled with `FOR UPDATE SKIP LOCKED` (`OutboxEventRepository.java:75-85`) and published with `RabbitTemplate`, persistent delivery, and AMQP headers (`OutboxPublisher.java:82-110`). |
| 4 | Java idempotently consumes indexed/failed events and updates document status. | VERIFIED | Consumers route through `IdempotentEventProcessor`, which inserts `processed_events` before handler execution (`IdempotentEventProcessor.java:35-47`), and repository updates only active `UPLOADED` rows (`DocumentRepository.java:194-249`). |
| 5 | Significant auth, document, role, chat, indexing, and guard events are auditable. | VERIFIED | Existing auth/user/role/access/document/indexing call sites write audit rows. `AuditEventWriter.writeEvent` accepts category/type strings and `audit_events` has free-form category/type columns, so future chat/guard call sites are supported when those later-phase features exist. |
| 6 | Phase 3 REST, event, and constants contracts are updated before Java implementation. | VERIFIED | OpenAPI/AsyncAPI/constants contain Phase 3 document endpoints, events, routing names, and error codes; `uv run --project ai-service python scripts/verify-contracts.py` passed. |
| 7 | Document delete is contracted as always-allowed soft delete for visible active documents; no delete-while-indexing 409 remains in REST contract. | VERIFIED | `DELETE /documents/{documentId}` documents status-agnostic soft delete and has only 204/401/403/404 responses (`api-v1.yaml:1017-1036`). |
| 8 | Upload error codes cover unsupported sniffed MIME, duplicate active same-department content, and access levels above caller max level. | VERIFIED | OpenAPI upload responses include `UNSUPPORTED_FILE_TYPE`, `INSUFFICIENT_ACCESS_LEVEL`, and `DUPLICATE_DOCUMENT` with `details.existingDocumentId` (`api-v1.yaml:930-982`); constants define these codes (`constants.yaml:103-106`, `155-158`, `203-206`). |
| 9 | PostgreSQL schema supports visibility, soft delete, duplicate SHA checks, outbox delivery, and idempotent consumers. | VERIFIED | Migrations V11-V13 define `documents`, `outbox_events`, and `processed_events` with soft-delete fields, partial duplicate index, JSONB payload/headers, retry fields, and `event_id` PK. |
| 10 | Correlation ID is available through MDC before JWT handling and reused by ProblemDetails, audit rows, and event metadata. | VERIFIED | `CorrelationIdFilter` sets response header and MDC then clears it; `SecurityConfig` installs it before bearer auth; `ProblemDetailsWriter`, `AuditEventWriter`, and outbox event headers read the same value. |
| 11 | Repositories expose SQL-level visibility primitives instead of controller in-memory filtering. | VERIFIED | `DocumentRepository.findVisibleById/pageVisibleDocuments` build SQL predicates from `ResolvedAccessFilter`, including active row, access level, doc type, and department filters (`DocumentRepository.java:118-150`, `259-276`). |
| 12 | Upload validates sniffed file type, hashes content, stores in MinIO, persists metadata, audits, and creates document.uploaded outbox row. | VERIFIED | Tika/SHA/object-key preparation is in `DocumentUploadPreparer`; upload writes MinIO before metadata/outbox/audit (`DocumentUploadService.java:90-116`) and tests assert ordering (`DocumentUploadServiceTest.java:71-89`). |
| 13 | Original filename is metadata only; object keys are generated from date, document ID, and sniffed MIME extension. | VERIFIED | `DocumentUploadPreparer.objectKey` uses `yyyy/MM/documentId.ext`; allowed MIME mapping covers PDF, DOCX, HTML, Markdown, and text only. |
| 14 | Upload permissions and access-level caps are enforced independently from department/docType visibility filters. | VERIFIED | Controller requires `documents.upload`; service resolves caller access levels and rejects above max before stream/storage work (`DocumentUploadService.java:90-95`, `149-156`). |
| 15 | List, detail, raw URL, and delete all apply the same active-document AccessFilter visibility rule. | VERIFIED | Query, raw URL, and delete services all resolve or reuse `DocumentQueryService.getVisible` / repository `findVisibleById` before returning data or mutating state (`DocumentRawUrlService.java:47-54`, `DocumentDeletionService.java:66-76`). |
| 16 | Invisible existing documents return 404 DOCUMENT_NOT_FOUND for detail, raw, and delete. | VERIFIED | `DocumentQueryService.notFound` returns `DOCUMENT_NOT_FOUND`; controller/service tests cover invisible raw/delete/detail paths. |
| 17 | Delete is immediate soft delete plus document.deleted outbox row and never rejects solely because indexing may be in progress. | VERIFIED | Delete transaction performs visible lookup, `softDeleteVisible`, `createDocumentDeleted`, and audit; repository soft delete has no status predicate (`DocumentDeletionService.java:66-86`, `DocumentRepository.java:175-191`). |
| 18 | Document upload/delete events are published from the outbox with at-least-once delivery, generated routing constants, and correlation headers. | VERIFIED | `AmqpConfig` uses generated `ExchangeNames`, `QueueNames`, and `EventRoutingKeys`; `OutboxPublisher` publishes stored exchange/routing/payload/headers and marks success/failure per row. |
| 19 | Outbox failures are retained with unlimited retry attempts and exponential backoff capped at 5 minutes. | VERIFIED | `markFailure` increments attempts without a terminal cap (`OutboxEventRepository.java:107-121`); publisher backoff doubles and caps at configured 5 minutes (`OutboxPublisherProperties.java:13-14`, `OutboxPublisher.java:124-138`). |
| 20 | Published outbox rows are cleaned up only after the 7-day retention window. | VERIFIED | Publisher cleanup deletes rows before `now - retention`; retention default is 7 days (`application.yml:85-88`, `OutboxPublisher.java:71-80`). |
| 21 | Java consumes document.indexed and document.indexing.failed idempotently by inserting processed_events before state changes. | VERIFIED | Consumers call `idempotentEventProcessor.process` before `DocumentIndexingResultService`; `ProcessedEventRepository` uses `ON CONFLICT (event_id) DO NOTHING`. |
| 22 | Soft-deleted documents are never resurrected by late indexed/failed events; the event is recorded as processed and acknowledged. | VERIFIED | Status updates require `deleted_at IS NULL` and `status = 'UPLOADED'` (`DocumentRepository.java:215-247`); lifecycle IT asserts late event for deleted row leaves it deleted (`DocumentLifecycleFlowIT.java:175-181`). |
| 23 | Phase 3 ends with full Java lifecycle verification covering upload, outbox, delete, consumer status updates, and audit/correlation. | VERIFIED | `DocumentLifecycleFlowIT.java:105-181` covers upload/list/raw/delete/outbox/audit/indexed/failed/duplicate/late-deleted behavior; `mvn verify` passed outside sandbox. |

**Score:** 23/23 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `contracts/openapi/api-v1.yaml` | Phase 3 REST contract | VERIFIED | Document upload/list/detail/raw/delete, 5-minute raw URL, duplicate/access/MIME errors, reserved `INDEXING`, and `ProblemDetail.details` are present. |
| `contracts/asyncapi/events-v1.yaml` | Document lifecycle event contract | VERIFIED | Event metadata requires `correlationId`; upload payload includes `title`, `contentSha256`, MinIO metadata, MIME, size, filename, and upload time. |
| `contracts/constants.yaml` | Generated constants source | VERIFIED | Routing keys, exchanges, queues/DLQs, and Phase 3 error codes exist; `documents.reindex` is not present. |
| `V11__create_documents_table.sql` | Document metadata/status schema | VERIFIED | Soft delete, content SHA, storage bucket/key, failure/indexing fields, and active duplicate index exist. |
| `V12__create_outbox_events_table.sql` | Transactional outbox schema | VERIFIED | JSONB payload/headers, correlation, attempts, last error, next attempt, and published timestamp exist. |
| `V13__create_processed_events_table.sql` | Idempotent consumer ledger | VERIFIED | `event_id` primary key and processed cleanup indexes exist. |
| `CorrelationIdFilter.java` | Request correlation lifecycle | VERIFIED | Parses/generates UUID, stores MDC, writes response header, clears MDC. |
| `DocumentStorageClient.java` | MinIO storage boundary | VERIFIED | Interface exposes bucket init, object put, and presigned GET URL. |
| `DocumentUploadService.java` | Upload use case | VERIFIED | Permission input, access cap, MIME/SHA preparation, duplicate check, MinIO put, metadata/outbox/audit. |
| `OutboxService.java` | Transactional outbox creation | VERIFIED | Creates `document.uploaded` and `document.deleted` envelopes and headers. |
| `DocumentQueryService.java` | Visible document read model | VERIFIED | Resolves access filter before repository SQL and returns `DOCUMENT_NOT_FOUND` for invisible rows. |
| `DocumentDeletionService.java` | Soft delete lifecycle | VERIFIED | Transactional visible soft delete, deleted outbox event, and audit. |
| `DocumentController.java` | Document REST API | VERIFIED | Provides GET list/detail/raw, DELETE, and POST upload endpoints. |
| `AmqpConfig.java` | RabbitMQ topology | VERIFIED | Durable topic exchange, DLX, primary queues, DLQs, and bindings from generated constants. |
| `OutboxPublisher.java` | Scheduled outbox publication | VERIFIED | Polls ready rows, publishes through RabbitTemplate, marks success/failure, backs off, and cleans published rows. |
| `EventEnvelopeFactory.java` | Event envelope/header construction | VERIFIED | Builds metadata with eventId/type/version/occurredAt/correlation/source and AMQP headers. |
| `DocumentIndexedConsumer.java` | `document.indexed` listener | VERIFIED | Validates event type, restores correlation, idempotently processes, updates `INDEXED`, audits. |
| `DocumentIndexingFailedConsumer.java` | `document.indexing.failed` listener | VERIFIED | Validates event type, restores correlation, idempotently processes, updates `INDEXING_FAILED`, audits. |
| `IdempotentEventProcessor.java` | Transactional consumer idempotency | VERIFIED | Insert-first processing, duplicate result, rollback on handler exception, retention cleanup. |
| `DocumentLifecycleFlowIT.java` | Phase 3 integrated verification | VERIFIED | Tests upload/list/raw/delete/outbox/audit/indexed/failed/duplicates/late-deleted behavior when Docker/test environment permits. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| OpenAPI | constants | ProblemDetail error codes | WIRED | Upload examples use generated error-code names. |
| AsyncAPI | constants | Routing names | WIRED | AsyncAPI routing/queue/exchange names align with constants and generated code. |
| `CorrelationIdFilter` | `AuditEventWriter`/ProblemDetails | MDC | WIRED | Same `correlationId` MDC key is read by both. |
| `DocumentRepository` | `ResolvedAccessFilter` | SQL predicates | WIRED | Repository binds filter values before query execution. |
| `OutboxEventRepository` | `OutboxPublisher` | Ready-row polling | WIRED | Publisher calls repository poll with row locking. |
| `DocumentUploadService` | `DocumentStorageClient` | MinIO put | WIRED | Service writes object key/content before DB transaction. |
| `DocumentUploadService` | `DocumentRepository` | Metadata and duplicate checks | WIRED | Service checks duplicate and inserts `DocumentRecord`. |
| `DocumentUploadService` | `OutboxService` | `document.uploaded` row | WIRED | Created inside transaction after MinIO put. |
| `DocumentUploadService` | `AuditEventWriter` | Upload success/failure audit | WIRED | Writes `DOCUMENT_UPLOADED` success/failure details. |
| `DocumentController` | query/raw/delete/upload services | REST mapping | WIRED | Controller delegates instead of embedding business logic. |
| `DocumentQueryService` | `AccessFilterResolver` | Visibility resolution | WIRED | Resolves caller access before repository query. |
| `DocumentDeletionService` | `OutboxService` | `document.deleted` row | WIRED | Created in the soft-delete transaction. |
| `DocumentRawUrlService` | `DocumentStorageClient` | Presigned URL | WIRED | Presigns only after visible document lookup. |
| `OutboxPublisher` | `RabbitTemplate` | AMQP publish | WIRED | Publishes stored exchange/routing/payload with persistent headers. |
| `AmqpConfig` | generated constants | Topology names | WIRED | Imports `ExchangeNames`, `QueueNames`, `EventRoutingKeys`. |
| Consumers | generated constants | Listener queues | WIRED | Listeners use backend queue constants. |
| Consumers | `IdempotentEventProcessor` | Insert-first idempotency | WIRED | Both consumers call processor before status service. |
| Consumers | `DocumentRepository` | Terminal updates | WIRED | Status service calls repository guarded active-row update methods. |
| Consumers | `AuditEventWriter` | Indexing audit | WIRED | Status service writes indexed/failed audit details. |
| Consumers | MDC | Correlation restoration | WIRED | Header/envelope/generated UUID fallback sets MDC and clears it in `finally`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `DocumentController` | REST document responses | Upload/query services backed by repository/storage | Yes | FLOWING |
| `DocumentUploadService` | `DocumentRecord` and outbox event | Multipart bytes, Tika/SHA preparation, MinIO put, PostgreSQL insert | Yes | FLOWING |
| `DocumentQueryService` | `DocumentPage`/`DocumentRecord` | `DocumentRepository.pageVisibleDocuments/findVisibleById` SQL | Yes | FLOWING |
| `DocumentRawUrlService` | `DocumentRawUrl` | Visible document storage key plus MinIO presign | Yes | FLOWING |
| `DocumentDeletionService` | soft delete and event | Repository visible update plus outbox/audit transaction | Yes | FLOWING |
| `OutboxPublisher` | AMQP message | `outbox_events` JSON payload/headers and stored routing | Yes | FLOWING |
| `DocumentIndexedConsumer` | indexed status fields | AMQP envelope payload through idempotent processor | Yes | FLOWING |
| `DocumentIndexingFailedConsumer` | failed status fields | AMQP envelope payload through idempotent processor | Yes | FLOWING |
| `AuditEventWriter` | audit rows | Auth/user/role/access/document/indexing call sites | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Contract generation and imports | `$env:MAVEN_CMD='C:\dev\apache-maven-3.9.15\bin\mvn.cmd'; uv run --project ai-service python scripts\verify-contracts.py` | YAML lint, Java constants/OpenAPI generation, Python generation/imports completed | PASS |
| Backend unit/slice tests | `C:\dev\apache-maven-3.9.15\bin\mvn.cmd -q -f backend\pom.xml -pl corp-rag-app -am test` | Exit 0; Docker unavailable warnings from Testcontainers were non-fatal | PASS |
| Backend verify/IT wiring | `C:\dev\apache-maven-3.9.15\bin\mvn.cmd -q -f backend\pom.xml -pl corp-rag-app -am verify` | Initial sandbox run failed with Windows compiler access denial; approved escalated rerun exited 0 | PASS |
| Probe discovery | `Get-ChildItem scripts -Recurse -Filter probe-*.sh` and phase plan/summary probe search | No probes declared or found | SKIP |

### Probe Execution

| Probe | Command | Result | Status |
|---|---|---|---|
| None | N/A | No `probe-*.sh` files declared or discovered for Phase 3 | SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| DOC-01 | 03-01, 03-02, 03-03 | Authorized user can upload file with metadata and store file in MinIO. | SATISFIED | Upload endpoint permission check, Tika/SHA preparation, MinIO put, metadata insert, outbox/audit transaction, and tests. |
| DOC-02 | 03-01, 03-02, 03-04 | User can list, filter, inspect, delete, and open raw documents according to permissions. | SATISFIED | Controller list/detail/raw/delete endpoints, SQL visibility predicates, raw URL service, soft delete service, and lifecycle tests. |
| DOC-03 | 03-01, 03-02, 03-06 | Java tracks indexing status, failure reason, chunk count, and indexed timestamp. | SATISFIED | Schema status/failure/indexing fields plus indexed/failed consumer status updates. |
| EVT-01 | 03-01, 03-02, 03-03, 03-04, 03-05 | Java publishes upload/delete through outbox-backed RabbitMQ topology. | SATISFIED | Outbox schema/service, event envelope factory, RabbitMQ topology, and scheduled publisher are wired and tested. |
| EVT-02 | 03-01, 03-02, 03-06 | Java consumes indexed/failed events idempotently and updates status. | SATISFIED | Processed-event ledger, idempotent processor, consumers, active-row guarded updates, duplicate/rollback tests. |
| AUD-01 | 03-01 through 03-06 | Java records audit events for login, document, chat, user, role, indexing, and guard actions. | SATISFIED WITH SCOPE NOTE | Auth/user/role/access/document/indexing call sites write audit rows; generic audit writer/schema supports future chat/guard call sites when those Phase 5/6 actions exist. |

No orphaned Phase 3 requirements were found: all Phase 3 requirement IDs in `.planning/REQUIREMENTS.md` appear in at least one Phase 03 plan frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `contracts/constants.yaml` | 86 | `placeholder host` | INFO | Intentional local ProblemDetail URI host comment, not a stub or unimplemented behavior. |
| `AmqpConsumerSupport.java` | 75, 78 | `return null` | INFO | Legitimate optional UUID parse fallback used before envelope/generated correlation fallback. |

No `TODO`, `FIXME`, `XXX`, placeholder UI/API stubs, empty handlers, or hardcoded empty runtime data were found in Phase 3 production paths.

### Human Verification Required

#### 1. Docker-backed external integration

**Test:** Start the full local infrastructure stack with Docker Compose, enable Java MinIO bucket initialization, outbox publisher, and indexing consumers, then exercise an upload/delete/indexed/failed lifecycle using real MinIO and RabbitMQ.

**Expected:** Upload writes the source object to MinIO and metadata to PostgreSQL; `document.uploaded` and `document.deleted` outbox rows publish to the configured RabbitMQ queues; synthetic `document.indexed` and `document.indexing.failed` messages update active documents once; duplicate and late deleted events do not duplicate audit/status or resurrect soft-deleted rows; correlation IDs remain present in audit rows and AMQP headers.

**Why human:** Current verifier environment reports no valid Docker/Testcontainers runtime. Automated code/test evidence verifies wiring and behavior with mocks/slices, but live external service integration remains environment-dependent.

### Gaps Summary

No blocking implementation gaps were found. The phase goal is achieved in code, contracts, persistence, event wiring, idempotent consumers, and automated tests. Overall status is `human_needed` only because real MinIO/RabbitMQ integration could not be executed in this verifier environment.

Planning metadata note: `ROADMAP.md` still contains stale progress text for Phase 3 (`4/6 plans executed` in the section and `2/6` in the progress table), while the phase directory has six plans and six summaries and the code evidence verifies all Phase 3 must-haves. This is not a Phase 3 implementation gap.

---

_Verified: 2026-05-13T21:22:58Z_
_Verifier: the agent (gsd-verifier)_
