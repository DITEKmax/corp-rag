# Phase 3: Documents, Events & Audit - Research

**Researched:** 2026-05-13
**Status:** Complete
**Mode:** Inline planner research (subagent installation unavailable)

## Research Question

How should Phase 3 implement Java-owned document metadata, MinIO storage, document lifecycle events, indexing-result consumers, and audit/correlation behavior while preserving Phase 1 contract-first rules and Phase 2 access-filter semantics?

## Sources Reviewed

- `.planning/phases/03-documents-events-audit/03-CONTEXT.md`
- `.planning/REQUIREMENTS.md`
- `.planning/ROADMAP.md`
- `.planning/PROJECT.md`
- `.planning/STATE.md`
- `.planning/phases/02-identity-users-access-control/02-07-SUMMARY.md`
- `contracts/openapi/api-v1.yaml`
- `contracts/openapi/ai-service-v1.yaml`
- `contracts/asyncapi/events-v1.yaml`
- `contracts/constants.yaml`
- `docs/ARCHITECTURE.md`
- `docs/PATTERNS.md`
- `docs/decisions/ADR-002-vector-database.md`
- `docs/decisions/ADR-003-java-python-split.md`
- `backend/corp-rag-app/pom.xml`
- `backend/corp-rag-app/src/main/resources/application.yml`
- `backend/corp-rag-app/src/main/resources/db/migration/`
- `backend/corp-rag-app/src/main/java/com/corprag/service/access/AccessFilterResolver.java`
- `backend/corp-rag-app/src/main/java/com/corprag/service/audit/AuditEventWriter.java`
- `backend/corp-rag-app/src/main/java/com/corprag/repository/AuditEventRepository.java`
- `backend/corp-rag-app/src/main/java/com/corprag/security/Permission.java`
- `infra/docker-compose.yml`
- `.env.example`

## Current State

Phase 1 established root contracts and generated Java/Python contract surfaces. Phase 2 completed Java auth, roles, permissions, access policies, access-filter resolution, and an extendable `audit_events` table/writer.

Phase 3 begins with these useful assets:

- `AccessFilterResolver` returns `ResolvedAccessFilter` with PUBLIC always included, downward access-level hierarchy expansion, empty department wildcard semantics, and doc type coverage.
- `Permission` already contains `documents.read`, `documents.upload`, and `documents.delete`.
- `AuditEventWriter` and `AuditEventRepository` already persist structured JSONB audit rows.
- `audit_events` already has a nullable `correlation_id` column.
- `contracts/asyncapi/events-v1.yaml` already defines document uploaded/deleted/indexed/failed event envelopes and payloads.
- `contracts/constants.yaml` already defines document routing keys, exchanges, queues, DLQs, and existing error constants.
- Docker Compose already provides PostgreSQL, MinIO, and RabbitMQ and makes Java depend on MinIO/RabbitMQ health.

Gaps to close:

- No Java document schema, repository, controller, service, or assembler exists yet.
- No MinIO Java dependency/configuration/storage adapter exists yet.
- No Apache Tika dependency or MIME sniffing path exists yet.
- No Spring AMQP dependency/config/topology/outbox publisher/consumer exists yet.
- `AuditEventWriter` currently generates a new correlation ID instead of reading MDC.
- OpenAPI document delete still advertises a 409 indexing-in-progress response that conflicts with Phase 3 D-23/D-65.
- `contracts/constants.yaml` lacks `INSUFFICIENT_ACCESS_LEVEL`, `DUPLICATE_DOCUMENT`, and `UNSUPPORTED_FILE_TYPE`.

## Implementation Strategy

### Contract-First Pass

Phase 3 should start by aligning contracts before Java implementation:

- Add new error constants:
  - `INSUFFICIENT_ACCESS_LEVEL` -> 403
  - `DUPLICATE_DOCUMENT` -> 409
  - `UNSUPPORTED_FILE_TYPE` -> 400
- Remove the `409` delete-while-indexing response from `DELETE /documents/{documentId}`. Keep any existing constant unused rather than force a breaking constants deletion unless contract verification requires removal.
- Update document upload response/error documentation for sniffed MIME, duplicate detection, unsupported type, and access-level rejection.
- Clarify that `INDEXING` remains reserved and Java does not set it in Phase 3.
- If needed for Java/Python symmetry, extend event payloads with `contentSha256`, but do not expose MinIO object keys through public REST responses except via raw URL issuance.

Verification: `python scripts/verify-contracts.py`.

### Persistence And Correlation Foundation

Use Flyway migrations after V10:

- `documents` table:
  - `id UUID PRIMARY KEY`
  - `title VARCHAR(512) NOT NULL`
  - `description VARCHAR(1000)`
  - `original_filename VARCHAR(512) NOT NULL`
  - `mime_type VARCHAR(128) NOT NULL`
  - `size_bytes BIGINT NOT NULL`
  - `access_level VARCHAR(32) NOT NULL`
  - `department VARCHAR(64) NOT NULL`
  - `doc_type VARCHAR(32) NOT NULL`
  - `language VARCHAR(8) NOT NULL`
  - `status VARCHAR(32) NOT NULL`
  - `owner_user_id UUID REFERENCES users(id) ON DELETE SET NULL`
  - `storage_bucket VARCHAR(128) NOT NULL`
  - `storage_key VARCHAR(512) NOT NULL`
  - `content_sha256 CHAR(64) NOT NULL`
  - `uploaded_at TIMESTAMPTZ NOT NULL`
  - `indexed_at TIMESTAMPTZ`
  - `chunk_count INTEGER`
  - `failure_stage VARCHAR(64)`
  - `failure_error_code VARCHAR(128)`
  - `failure_reason TEXT`
  - `failure_retryable BOOLEAN`
  - `failure_retry_count INTEGER`
  - `qdrant_collection VARCHAR(128)`
  - `neo4j_entity_count INTEGER`
  - `indexing_duration_ms BIGINT`
  - `deleted_at TIMESTAMPTZ`
  - `deleted_by UUID REFERENCES users(id) ON DELETE SET NULL`
- Partial unique index:
  - `(content_sha256, department) WHERE deleted_at IS NULL`
- Visibility/filter indexes:
  - `(status) WHERE deleted_at IS NULL`
  - `(department, doc_type, access_level) WHERE deleted_at IS NULL`
  - `(uploaded_at DESC) WHERE deleted_at IS NULL`
- `outbox_events` table per D-38 with ready/unpublished indexes.
- `processed_events` table keyed by `event_id` with processed timestamp cleanup index.

Add Java domain records/enums and JDBC repositories using existing `JdbcClient` patterns. Keep controllers thin; repositories own SQL; services own lifecycle rules.

Add `CorrelationIdFilter` early in the chain, before JWT handling:

- Accept valid `X-Correlation-Id` UUID or generate UUID.
- Store in MDC key `correlationId`.
- Return the same ID on the response header.
- Clear MDC in `finally`.
- Update `ProblemDetailsWriter` and `AuditEventWriter` to use MDC correlation ID and fall back for background jobs.

### Document Storage And Upload

Add dependencies in `backend/corp-rag-app/pom.xml` where first used:

- `spring-boot-starter-amqp` for RabbitMQ plans.
- MinIO Java SDK for storage.
- Apache Tika Core for MIME sniffing.
- Testcontainers RabbitMQ and, if practical, MinIO-compatible container coverage for integration tests.

Configuration:

- Add Java MinIO properties:
  - endpoint
  - access key
  - secret key
  - secure flag
  - bucket `corp-rag-documents`
  - presigned URL TTL 5 minutes
- Add multipart max file/request size 50MB.
- Add Java RabbitMQ URL/host/user/password configuration through Spring Boot AMQP properties.
- Wire Java service env vars in `infra/docker-compose.yml` and `.env.example`.

Storage flow:

- Ensure `corp-rag-documents` bucket exists idempotently on startup.
- Sniff MIME with Tika from uploaded bytes/stream. Do not trust client `Content-Type`.
- Allowed MIME map:
  - `application/pdf` -> `pdf`
  - `application/vnd.openxmlformats-officedocument.wordprocessingml.document` -> `docx`
  - `text/html` -> `html`
  - `text/markdown` -> `md`
  - `text/plain` -> `txt`
- Compute SHA-256 while reading the upload.
- Generate object key `{yyyy}/{MM}/{documentId}.{ext}`.
- Insert document row with `UPLOADED`.
- Insert `document.uploaded` outbox row in the same transaction.
- Upload object to MinIO with the sniffed MIME.

Important ordering risk: MinIO object storage is not transactional with PostgreSQL. For MVP, prefer uploading to MinIO before committing the DB/outbox row, then persist metadata/outbox in one DB transaction. If DB commit fails after MinIO put, a bounded housekeeping task can remove orphaned recent objects later; the inverse failure (DB row exists but object missing) is worse because Python would receive an event it cannot process.

Duplicate flow:

- Same content SHA in same department with `deleted_at IS NULL` returns `409 DUPLICATE_DOCUMENT` and `details.existingDocumentId`.
- Same content in different department is allowed.
- Same content after soft delete is allowed.

Access-level flow:

- Upload requires `documents.upload`.
- Upload access level must be less than or equal to caller's effective max resolved level.
- Upload department/docType are validated by contract/domain rules but not constrained by the caller's current filter.

### Document Query, Raw URL, And Delete

List/detail/raw/delete must all use `AccessFilterResolver` as the only visibility source:

- Active rows only: `deleted_at IS NULL`.
- `doc_type IN (:filter.docTypes)`.
- Department predicate:
  - filter departments empty means wildcard.
  - otherwise `department IN (:filter.departments)`.
- Access predicate:
  - document `access_level` must be within resolved allowed levels.
  - `PUBLIC` remains visible according to Phase 2 semantics through resolver output.

Implement visibility in SQL before pagination and counts. Invisible existing documents return `404 DOCUMENT_NOT_FOUND` for detail/raw/delete.

Raw URL:

- `GET /documents/{id}/raw` checks visibility first.
- Generate 5-minute MinIO presigned GET URL.
- Write `DOCUMENT_RAW_URL_ISSUED` audit row.
- Java never proxies file bytes.

Delete:

- Requires `documents.delete`.
- Applies the same visibility filter.
- Soft-deletes immediately with `deleted_at` and `deleted_by`.
- Inserts `document.deleted` outbox row in the same transaction.
- Never rejects because status is `UPLOADED` or `INDEXING`.
- Does not physically delete MinIO object in Phase 3.

### Outbox Publisher

Implement scheduled polling:

- Query unpublished ready rows with `ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 50`.
- Publish to `corp-rag.documents` using the stored `routing_key`.
- Mark `published_at` on success.
- On failure, increment `publish_attempts`, store `last_error`, and set `next_attempt_at` using exponential backoff capped at 5 minutes.
- Keep unlimited attempts.
- Clean up published rows older than 7 days.

Topology:

- Declare `corp-rag.documents` topic exchange.
- Declare `corp-rag.documents.dlx` topic DLX.
- Declare primary and DLQ queues from generated constants.
- Bind queues to routing keys from generated constants.

### Java Consumers For Python Indexing Results

Implement consumers for:

- `document.indexed`
- `document.indexing.failed`

Processing pattern:

- Set MDC correlation ID from `x-correlation-id` or event metadata.
- Start transaction.
- Insert `processed_events(event_id, event_type, correlation_id, processed_at)` with conflict handling.
- If already present, ACK and return.
- If document is soft-deleted, record event as processed and audit/debug as appropriate, but do not update document status.
- If active:
  - `document.indexed`: `UPLOADED -> INDEXED`, set chunk count, indexed timestamp, Qdrant collection, Neo4j entity count, duration.
  - `document.indexing.failed`: `UPLOADED -> INDEXING_FAILED`, set failure stage/code/message/retryable/retry count.
- Write `DOCUMENT_INDEXED` or `DOCUMENT_INDEXING_FAILED` audit event.
- Commit before ACK.

Business exceptions should roll back so `processed_events` is not recorded. Let the listener NACK/requeue according to RabbitMQ/Spring AMQP configuration.

### Tests

Use the existing split:

- Unit tests for pure logic:
  - visibility predicate builder/access-level max rules
  - MIME mapping/object-key generation
  - SHA-256 duplicate behavior where possible
  - event envelope/header builder
  - idempotent consumer support
  - correlation ID filter/AuditEventWriter MDC fallback
- `@WebMvcTest` or controller-slice tests for document REST permission/error mapping.
- PostgreSQL integration tests using existing `PostgresIntegrationTestSupport` for:
  - documents/outbox/processed_events migrations
  - list pagination with SQL visibility
  - duplicate partial unique index
  - soft-delete invisibility and delete outbox atomicity
- RabbitMQ integration tests if Docker is available for topology and publisher behavior.
- Full backend verification target: `cd backend; mvn -q -pl corp-rag-app -am verify`.

## Recommended Plan Split

| Plan | Wave | Scope | Requirements |
|------|------|-------|--------------|
| 03-01 | 1 | Phase 3 contract alignment and generated contract verification | DOC-01, DOC-02, DOC-03, EVT-01, EVT-02, AUD-01 |
| 03-02 | 2 | Persistence schema, domain/repository foundation, and correlation/audit cleanup | DOC-01, DOC-02, DOC-03, EVT-01, EVT-02, AUD-01 |
| 03-03 | 3 | MinIO/Tika upload pipeline and `document.uploaded` outbox creation | DOC-01, EVT-01, AUD-01 |
| 03-04 | 4 | Document list/detail/raw/delete REST APIs with SQL visibility and delete outbox | DOC-02, EVT-01, AUD-01 |
| 03-05 | 5 | RabbitMQ topology and scheduled outbox publisher | EVT-01, AUD-01 |
| 03-06 | 6 | Idempotent indexing-result consumers, status transitions, and full Phase 3 verification | DOC-03, EVT-02, AUD-01 |

This keeps the critical path mostly sequential because later plans depend on contract/schema/service foundations. The main independent work inside a wave is task-level, not plan-level.

## Risks And Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Java/Python visibility drift | Data leak or missing results later | Build document SQL predicates directly from `ResolvedAccessFilter` and test department wildcard, doc type, and access-level cases. |
| DB/MinIO non-atomic upload | Orphan object or broken event | Prefer MinIO put before DB/outbox commit; add bounded orphan cleanup as MVP housekeeping; never commit DB/outbox for a missing object. |
| Duplicate detection races | Same content duplicated in a department | Enforce database partial unique index and map violation to `DUPLICATE_DOCUMENT`. |
| Outbox duplicates | Python receives event more than once | Accept at-least-once delivery; include event ID and require Python idempotency in Phase 4. |
| Consumer duplicate delivery | Status/audit double update | Use `processed_events` insert-first transaction and ACK duplicates. |
| Delete/indexed race | Soft-deleted document gets resurrected | Consumers must record event as processed but skip active row updates when `deleted_at IS NOT NULL`. |
| Correlation gaps | Audit/event traces cannot be connected | Install filter before JWT; carry MDC into audit, outbox headers, publisher, and consumers. |
| Contract/code mismatch | Generated DTO compile failures | Run `python scripts/verify-contracts.py` after contract edits and Maven verify after each Java slice. |

## Acceptance Coverage

| Requirement | Research Coverage |
|-------------|-------------------|
| DOC-01 | Upload plan covers permission, access-level cap, MIME sniffing, SHA-256, MinIO storage, metadata row, duplicate rejection, and upload audit. |
| DOC-02 | Query/delete plan covers list/detail/raw/delete visibility, 404 for invisible docs, SQL pagination/counts, presigned URLs, and soft delete. |
| DOC-03 | Schema and consumer plans cover status, failure details, chunk count, indexed timestamp, collection/entity/duration metadata. |
| EVT-01 | Outbox schema/service plus publisher plan covers transactional event rows, backoff, cleanup, topology, and RabbitMQ publication. |
| EVT-02 | Consumer plan covers idempotency, transactional processed-events insert, ACK duplicate behavior, and deleted-document race handling. |
| AUD-01 | Correlation/audit cleanup plus document/action/consumer audit events extend the existing audit system. |

## Research Conclusion

Phase 3 should be planned as six sequential executable slices. The most important design constraint is symmetry: the same Phase 2 `ResolvedAccessFilter` must drive Java document SQL visibility now and Python Qdrant/Neo4j payload filtering later. The second critical constraint is event durability: upload/delete state changes and outbox rows must commit atomically, while consumers must be idempotent and must not resurrect soft-deleted documents.

## RESEARCH COMPLETE
