# Phase 3: Documents, Events & Audit - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 delivers Java-owned document metadata, MinIO file orchestration, document upload/list/detail/raw/delete APIs, outbox-backed RabbitMQ lifecycle events, idempotent Java consumers for Python indexing results, and expanded audit/correlation behavior. It does not implement Python ingestion/indexing, frontend document screens, hard-delete retention, automated retry/backoff for failed documents, department dictionary CRUD, or production cleanup jobs beyond bounded MVP housekeeping.

</domain>

<decisions>
## Implementation Decisions

### Document Visibility Rules
- **D-01:** `AccessFilter` resolved from Phase 2 roles/access policies is the only source of truth for document visibility. Document ownership never bypasses access filtering.
- **D-02:** Read operations (`GET /documents`, `GET /documents/{id}`, `GET /documents/{id}/raw`) apply the same visibility rules: active document only (`deleted_at IS NULL`), `docType` contained in `filter.docTypes`, `department` contained in `filter.departments` unless `filter.departments` is empty as wildcard, and `accessLevel` allowed by the resolved max access level. `PUBLIC` documents remain visible according to Phase 2 public-visibility semantics.
- **D-03:** `GET /documents` applies visibility in SQL/PostgreSQL before pagination and total counts. Java must map `ResolvedAccessFilter` into a JDBC predicate that mirrors the payload filter Python will later apply in Qdrant.
- **D-04:** `GET /documents/{id}` and `GET /documents/{id}/raw` return `404 DOCUMENT_NOT_FOUND` when a document exists but is outside the caller's visibility. Do not return `403` for invisible documents because that leaks existence.
- **D-05:** `GET /documents/{id}/raw` issues a 5-minute MinIO presigned URL only after the same visibility check as detail. Java does not proxy binary file bytes.
- **D-06:** `POST /documents` requires `documents.upload`. The uploaded document's `accessLevel` must be less than or equal to the uploader's resolved effective max access level. Uploading a higher access level returns `403 INSUFFICIENT_ACCESS_LEVEL`.
- **D-07:** Upload has no department/docType visibility restriction beyond contract validation. A user with `documents.upload` may create a document for any regex-valid department and valid doc type, even if their current filter will not let them see the document after upload. This supports workflows such as an assistant uploading on behalf of another department.
- **D-08:** `DELETE /documents/{id}` requires `documents.delete` and also applies `AccessFilter`. If the caller cannot see the document, return `404 DOCUMENT_NOT_FOUND`. Ownership does not grant delete access.
- **D-09:** Reject owner-bypass visibility because it would introduce a second visibility axis, break Java/Python symmetry, and complicate audit. Bootstrap/admin full-visibility recovery is sufficient for the MVP.

### Upload Lifecycle And Storage
- **D-10:** Store source files in a single MinIO bucket named `corp-rag-documents`.
- **D-11:** Java idempotently ensures the `corp-rag-documents` bucket exists at startup through the MinIO Java SDK. If the bucket already exists, startup does nothing.
- **D-12:** MinIO object keys use `{yyyy}/{MM}/{documentId}.{ext}`. The extension is resolved from the sniffed MIME type, never from the raw original filename.
- **D-13:** MIME-to-extension mapping is fixed: `application/pdf -> pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document -> docx`, `text/html -> html`, `text/markdown -> md`, and `text/plain -> txt`.
- **D-14:** Preserve the original filename in `documents.original_filename` for UI/audit only. The original filename never participates in the MinIO object key.
- **D-15:** Java computes `content_sha256` for every upload and stores it as `CHAR(64) NOT NULL`.
- **D-16:** Active duplicate detection is scoped by department: enforce a partial unique index equivalent to `(content_sha256, department) WHERE deleted_at IS NULL`.
- **D-17:** If the same file content is uploaded to the same department while an active document already exists, return `409 DUPLICATE_DOCUMENT` with `details.existingDocumentId`.
- **D-18:** The same file content may be uploaded to a different department. The same file content may also be uploaded again to the same department after the previous document was soft-deleted.
- **D-19:** Upload validation uses Apache Tika sniffing plus an allowlist. Client `Content-Type` is only a hint and is not trusted.
- **D-20:** Allowed sniffed MIME types are PDF, DOCX, HTML, Markdown, and plain text. A sniffed MIME outside the allowlist returns `400 UNSUPPORTED_FILE_TYPE`.
- **D-21:** If client-declared `Content-Type` differs from the sniffed MIME but the sniffed MIME is allowed, do not block the upload. Record the mismatch as an audit warning/details field.
- **D-22:** File size limit is 50 MB as already documented in the contract. Enforce it through Spring multipart configuration before MIME sniffing.

### Delete Lifecycle
- **D-23:** Delete is always allowed for visible documents regardless of current indexing status. `DELETE /documents/{id}` must not return `409` merely because indexing may be in progress.
- **D-24:** Delete performs an immediate soft delete by setting `deleted_at` and `deleted_by` in the same transaction that creates the `document.deleted` outbox event.
- **D-25:** Soft-deleted documents are invisible everywhere: list, detail, and raw return no deleted rows.
- **D-26:** Phase 3 does not physically delete MinIO objects. Previously issued presigned URLs may remain valid until their 5-minute expiry; this is an accepted MVP limitation.
- **D-27:** Python handles `document.deleted` later by removing Qdrant points and Neo4j document/chunk nodes. Python does not delete the MinIO object in Phase 4.
- **D-28:** Hard delete, GDPR-style purge, MinIO lifecycle retention, and physical object cleanup are deferred to Phase 7 or Phase 8.
- **D-29:** Java always publishes `document.deleted` for delete of an active visible document, even if status is `UPLOADED` and Python may still be processing an earlier upload event.
- **D-30:** If Java later receives `document.indexed` or `document.indexing.failed` for a soft-deleted document, it records the event as processed for idempotency but must not update the deleted document row or resurrect status.

### Document Status And Failed Indexing
- **D-31:** Phase 3 Java uses only terminal status transitions: `UPLOADED -> INDEXED` on `document.indexed`, and `UPLOADED -> INDEXING_FAILED` on `document.indexing.failed`.
- **D-32:** Java does not set `INDEXING` in Phase 3. After upload, status remains `UPLOADED` until Python sends a terminal event.
- **D-33:** The `INDEXING` enum value remains in the contract as reserved/no-breaking-change. Phase 6 frontend may display "indexing in progress" heuristically when a document is recent and still `UPLOADED`.
- **D-34:** `document.indexing.failed.retryable` is recorded for audit/debug information only in Phase 3. It does not trigger automatic retry.
- **D-35:** Failed documents are terminal in Phase 3. The operational recovery path is admin delete plus re-upload, producing a new `documentId` and a clean pipeline.
- **D-36:** Do not add `POST /documents/{id}/reindex`, `documents.reindex`, `DOCUMENT_REINDEX_FORBIDDEN`, retry counters, or reindex seed logic in Phase 3. Reindex/manual retry is deferred to Phase 7+.

### Events, Outbox, And Idempotency
- **D-37:** Java publishes `document.uploaded` and `document.deleted` through an outbox table in the same transaction as the document metadata change.
- **D-38:** Outbox schema must include at least: `id`, `aggregate_type`, `aggregate_id`, `event_type`, `routing_key`, `exchange_name`, `payload JSONB`, `headers JSONB`, `correlation_id`, `created_at`, `published_at`, `publish_attempts`, `last_error`, and `next_attempt_at`.
- **D-39:** Outbox publisher uses scheduled polling with row locking (`FOR UPDATE SKIP LOCKED`) and a small batch size such as 50. It marks `published_at` on success.
- **D-40:** Outbox publish failure increments `publish_attempts`, stores `last_error`, and schedules `next_attempt_at` using exponential backoff from about 1 second up to a 5-minute cap. Attempts are unlimited for at-least-once delivery.
- **D-41:** Published outbox rows may be cleaned up after 7 days by a scheduled job.
- **D-42:** Java consumers for `document.indexed` and `document.indexing.failed` are idempotent using a `processed_events` table keyed by `event_id`.
- **D-43:** Consumer processing pattern is transactional: insert `processed_events` with `ON CONFLICT DO NOTHING`; if already present, ACK and return; otherwise update document state and write audit; commit before ACK.
- **D-44:** On business failure during consumer processing, roll back the transaction so `processed_events` is not recorded, then NACK/requeue according to RabbitMQ retry/DLQ behavior.
- **D-45:** `processed_events` cleanup may remove rows older than 30 days through a scheduled job.
- **D-46:** Phase 3 Java is not responsible for Python-side tombstone mechanics. Phase 4 must ensure that if delete reaches Python before upload, the later upload event is skipped or cleaned up idempotently.

### Audit And Correlation
- **D-47:** Reuse and extend the Phase 2 `audit_events` table and `AuditEventWriter`; do not create a new audit system.
- **D-48:** Add `DOCUMENT` category audit events: `DOCUMENT_UPLOADED`, `DOCUMENT_DELETED`, `DOCUMENT_RAW_URL_ISSUED`, `DOCUMENT_INDEXED`, and `DOCUMENT_INDEXING_FAILED`.
- **D-49:** Do not audit ordinary read operations such as list and detail. Audit write actions plus the sensitive raw-file URL issuance.
- **D-50:** `DOCUMENT_UPLOADED` details include title, original filename, size, sniffed MIME, declared MIME if present, MIME mismatch warning when applicable, access level, department, doc type, language, and content SHA-256.
- **D-51:** `DOCUMENT_DELETED` details include title, access level, department, doc type, previous status, and whether indexed chunks were known to exist.
- **D-52:** `DOCUMENT_RAW_URL_ISSUED` details include access level and department. Java cannot know whether the user actually downloaded the file from MinIO; that limitation is accepted for MVP.
- **D-53:** `DOCUMENT_INDEXED` details include chunk count, duration, Qdrant collection, and Neo4j entity count from the Python event.
- **D-54:** `DOCUMENT_INDEXING_FAILED` details include stage, error code, error message, retryable, and retry count from the Python event.
- **D-55:** Implement full correlation ID cleanup in Phase 3. Add a Spring `CorrelationIdFilter` before JWT handling to read `X-Correlation-Id` or generate a UUID and store it in MDC.
- **D-56:** `AuditEventWriter` must use MDC `correlationId` when present and fall back to a generated UUID for system jobs.
- **D-57:** Outbox event metadata and AMQP headers carry the same correlation ID. Phase 3 consumers set MDC from incoming `x-correlation-id` before processing.
- **D-58:** Existing Phase 2 audit call sites should benefit from the `AuditEventWriter` cleanup without changing every call site.

### Contract And Permission Changes
- **D-59:** Add error code `INSUFFICIENT_ACCESS_LEVEL` with HTTP 403 for upload access levels above the user's resolved effective max access level.
- **D-60:** Add error code `DUPLICATE_DOCUMENT` with HTTP 409 for same-content same-department active duplicate uploads.
- **D-61:** Add error code `UNSUPPORTED_FILE_TYPE` with HTTP 400 for MIME allowlist violations.
- **D-62:** `INVALID_FILE_FORMAT` already exists and remains available for downstream indexing/parsing failures.
- **D-63:** Do not add `documents.reindex` permission in Phase 3.
- **D-64:** Keep department as a free-form uppercase code validated by the existing regex `^[A-Z][A-Z0-9_]{0,63}$`. Do not add department table/CRUD in Phase 3.
- **D-65:** Update the document DELETE contract/implementation so delete-while-indexing is allowed; do not implement `DOCUMENT_INDEXING_IN_PROGRESS` for indexing-status conflicts in Phase 3.

### the agent's Discretion
- Choose exact Java package/class names while preserving existing adapter/service/domain/repository layering.
- Choose exact MinIO SDK wiring and bucket initializer shape, as long as bucket creation is idempotent and uses the locked bucket/key decisions.
- Choose exact implementation mechanics for stream hashing plus Tika sniffing, as long as uploads are bounded by the 50 MB limit and do not trust client `Content-Type`.
- Choose exact RabbitMQ retry/DLQ configuration consistent with the existing AsyncAPI and constants.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning State
- `.planning/PROJECT.md` - project value, service ownership, architecture constraints, and locked decisions.
- `.planning/REQUIREMENTS.md` - Phase 3 requirements DOC-01 through DOC-03, EVT-01 through EVT-02, and AUD-01.
- `.planning/ROADMAP.md` - Phase 3 goal and success criteria.
- `.planning/STATE.md` - current project state and accumulated completed-phase context.
- `.planning/phases/01-foundation-contracts/01-CONTEXT.md` - contract-first rules, root `contracts/` source of truth, generated code policy, Docker Compose contour.
- `.planning/phases/02-identity-users-access-control/02-CONTEXT.md` - locked access-filter semantics, permission model, role policies, audit table/writer baseline, and security/session behavior.

### Contracts
- `contracts/openapi/api-v1.yaml` - document REST endpoints, document schemas, permissions, and error responses that Phase 3 must refine/implement.
- `contracts/openapi/ai-service-v1.yaml` - access-filter and citation/chunk contracts relevant to Java/Python symmetry.
- `contracts/asyncapi/events-v1.yaml` - document lifecycle event envelope/payload contracts and Java/Python queue directions.
- `contracts/constants.yaml` - routing keys, queue names, exchange names, and error codes.

### Architecture And Patterns
- `docs/ARCHITECTURE.md` - Java/Python responsibilities, Java document/outbox/audit decomposition, and target architecture.
- `docs/PATTERNS.md` - contract-first, adapter/service layering, outbox, idempotent consumer, DLQ, HATEOAS, pagination, and error-contract patterns.
- `docs/CONTEXT.md` - high-level architecture context and Java/Python responsibility split.
- `backend/README.md` - backend module role and layout.
- `ai-service/README.md` - Python service boundary for downstream Phase 4 handoff.

### ADRs
- `docs/decisions/ADR-003-java-python-split.md` - Java owns auth/RBAC/document metadata while Python applies access filters and owns indexing/RAG.
- `docs/decisions/ADR-002-vector-database.md` - Qdrant payload filtering rationale that Phase 3 document metadata must feed.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/corp-rag-app` already contains Spring Boot Web/JDBC/Security/Validation/Flyway structure and Phase 2 controllers/services/repositories.
- `backend/corp-rag-app/src/main/java/com/corprag/service/audit/AuditEventWriter.java` is the existing audit writer to extend for MDC correlation IDs and Phase 3 document events.
- `backend/corp-rag-app/src/main/resources/db/migration/` contains Flyway migrations V1 through V10; Phase 3 migrations should continue at V11+.
- `backend/corp-rag-app/src/main/java/com/corprag/service/access/AccessFilterResolver.java` and `ResolvedAccessFilter` provide the canonical Java access filter to reuse for document visibility.
- `backend/corp-rag-app/src/main/java/com/corprag/security/Permission.java` already includes `documents.read`, `documents.upload`, and `documents.delete`.
- `contracts/asyncapi/events-v1.yaml` and `contracts/constants.yaml` already define document uploaded/deleted/indexed/failed routing keys, queues, exchanges, and generated constants.
- `infra/docker-compose.yml` already runs MinIO and RabbitMQ and wires them as Java backend dependencies.

### Established Patterns
- Contract-first: update root OpenAPI/AsyncAPI/constants before implementing service behavior.
- Generated Java/Python contract outputs are build artifacts and are not committed.
- Java is the browser-facing authority for auth/RBAC/document metadata and MinIO orchestration.
- Python owns ingestion/indexing and later applies the same visibility metadata in Qdrant/Neo4j retrieval paths.
- Controllers stay thin; service layer owns use cases; repositories own JDBC persistence.
- REST errors use RFC 7807 Problem Details via generated `ErrorCodes`.
- Audit events are structured JSONB rows, not log-only side effects.

### Integration Points
- Add document REST controller/service/repository/assembler under `backend/corp-rag-app`.
- Add MinIO client/storage adapter and startup bucket initializer under Java backend.
- Add Flyway migrations for `documents`, `outbox_events`, and `processed_events`.
- Add AMQP config, outbox publisher, and document indexing-result consumers under Java adapter/service packages.
- Extend `application.yml` and compose env wiring with Java-side MinIO/RabbitMQ/multipart settings.
- Extend contract verification inputs in `contracts/`.

</code_context>

<specifics>
## Specific Ideas

- Active duplicate constraint target:
  `CREATE UNIQUE INDEX idx_documents_sha_dept_active ON documents (content_sha256, department) WHERE deleted_at IS NULL;`
- Soft delete columns:
  `deleted_at TIMESTAMPTZ` and `deleted_by UUID REFERENCES users (id) ON DELETE SET NULL`.
- Outbox ready index target:
  `CREATE INDEX idx_outbox_unpublished_ready ON outbox_events (next_attempt_at) WHERE published_at IS NULL;`
- Outbox aggregate index target:
  `CREATE INDEX idx_outbox_aggregate ON outbox_events (aggregate_type, aggregate_id, created_at);`
- Processed-events cleanup index target:
  `CREATE INDEX idx_processed_events_time ON processed_events (processed_at);`
- Outbox publisher batch query should use `ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 50`.
- Raw URL issuance audit is enough for MVP; actual MinIO download tracking through event webhooks is deferred.
- Failed-document recovery in Phase 3 is delete plus re-upload, not reindex.

</specifics>

<deferred>
## Deferred Ideas

- Department dictionary table and CRUD endpoints are deferred, likely until frontend/admin workflows need dropdown-backed department management.
- Hard delete, GDPR purge, physical MinIO cleanup, and object retention policies are deferred to Phase 7 or Phase 8.
- Automated retry/backoff for failed indexing, poison message handling, and DLQ analytics are deferred to Phase 7+.
- Manual reindex endpoint and `documents.reindex` permission are deferred to Phase 7+.
- Actual download tracking through MinIO event webhooks is deferred to Phase 7+.
- Python-side delete tombstone mechanics are deferred to Phase 4 implementation details.

</deferred>

---

*Phase: 3-Documents, Events & Audit*
*Context gathered: 2026-05-13*
