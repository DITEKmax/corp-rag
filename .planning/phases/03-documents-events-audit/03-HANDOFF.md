# Phase 03 to Phase 04 Handoff

**Created:** 2026-05-17T16:08:14+03:00
**From:** Phase 03 - Documents, Events & Audit
**To:** Phase 04 - Python Ingestion & Indexing
**Status:** Phase 03 passed Docker-backed HUMAN UAT. Do not start Phase 4 until the user explicitly requests discussion or planning.

## Phase 3 Outcome

Phase 3 delivered the Java document lifecycle backbone:

- Document upload/list/detail/raw/delete REST endpoints with SQL visibility enforcement.
- MinIO object storage orchestration with MIME sniffing, SHA-256 hashing, duplicate detection, and 5-minute presigned raw URLs.
- PostgreSQL document metadata, outbox_events, processed_events, and audit rows.
- RabbitMQ topology for document lifecycle queues and DLQs.
- Scheduled outbox publisher for document.uploaded and document.deleted events.
- Java consumers for document.indexed and document.indexing.failed events with insert-first idempotency.
- Correlation propagation across HTTP, audit, outbox, AMQP headers, and event payload metadata.

Human UAT passed all 13 checks on a clean Docker stack with postgres, minio, rabbitmq, and java-backend.

## Artifacts Phase 4 Depends On

- `contracts/asyncapi/events-v1.yaml` - Source of truth for document.uploaded, document.deleted, document.indexed, and document.indexing.failed envelopes and payloads.
- `contracts/constants.yaml` - Source for exchange, routing key, queue, DLQ, and error-code constants.
- `scripts/generate_constants.py` and `scripts/generate_python_contracts.py` - Generate Java/Python contract surfaces; generated outputs remain ignored build artifacts.
- `backend/corp-rag-app/src/main/java/com/corprag/config/AmqpConfig.java` - Declares corp-rag.documents, corp-rag.documents.dlx, eight queues, DLQs, and bindings from generated constants.
- `backend/corp-rag-app/src/main/java/com/corprag/service/outbox/EventEnvelopeFactory.java` - Defines Java envelope/header behavior Phase 4 must preserve when publishing result events back.
- `backend/corp-rag-app/src/main/java/com/corprag/service/events/IdempotentEventProcessor.java` - Java insert-first idempotency pattern for backend result queues.
- `backend/corp-rag-app/src/main/resources/db/migration/V13__create_processed_events_table.sql` - Java processed_events ledger. Phase 4 should implement/use a Python-side equivalent for upload/delete consumption, while Java's table already protects backend result consumers.
- `infra/docker-compose.yml` - Local env wiring for postgres, minio, rabbitmq, java-backend, and Phase 2 admin bootstrap variables.
- `.env.example` - Expected local defaults for Java RabbitMQ, MinIO, outbox publisher, and indexing consumer toggles.

## RabbitMQ State After UAT

The Docker stack was left running after Phase 3 UAT. Queue state captured on 2026-05-17:

| Queue | Messages | Ready | Unacked | State |
|-------|----------|-------|---------|-------|
| ai.document.uploaded | 2 | 2 | 0 | running |
| ai.document.deleted | 1 | 1 | 0 | running |
| ai.document.uploaded.dlq | 0 | 0 | 0 | running |
| ai.document.deleted.dlq | 0 | 0 | 0 | running |
| backend.document.indexed | 0 | 0 | 0 | running |
| backend.document.indexed.dlq | 0 | 0 | 0 | running |
| backend.document.failed | 0 | 0 | 0 | running |
| backend.document.failed.dlq | 0 | 0 | 0 | running |

Phase 4's Python consumer will receive accumulated UAT messages on first startup if the same Docker volumes are kept. If Phase 4 needs a deterministic blank slate, clear these queues explicitly or recreate RabbitMQ volumes.

## Phase 4 Preflight Risks

- `ai-service/src/corp_rag_ai/contracts/generated/` is ignored by Git. The current `python-ai` compose build context is `../ai-service`, so a clean AI-service Docker build does not include root `contracts/` or root `scripts/`. Phase 4 should fix Python contract generation in the AI-service Docker build or adjust the build context before relying on generated contract imports in a clean container.
- Phase 4 should avoid querying Java for upload metadata that is already present in the document.uploaded payload. The event includes document ID, title, content SHA-256, access metadata, language, MIME, size, original filename, MinIO bucket/key, uploadedAt, and envelope metadata.
- Java expects result events on backend.document.indexed and backend.document.failed queues with valid eventId, eventType, eventVersion, occurredAt, correlationId, and sourceService metadata.
- Java accepts a valid AMQP `x-correlation-id` header first, then envelope metadata, then generates a fallback UUID. Python should preserve the incoming correlation ID when publishing result events.

## Deferred Concerns For Phase 7+

- MinIO orphan cleanup after MinIO put succeeds but the later metadata/outbox/audit DB transaction fails.
- Hard delete, GDPR-style purge, MinIO object retention, and physical object cleanup.
- Spring AMQP publisher confirms before marking outbox rows published.
- Outbox batch transaction split so each event publish can commit independently with `REQUIRES_NEW` semantics.
- Tika/upload streaming optimization to avoid full file buffering under concurrent production uploads.
- MinIO public endpoint split: `JAVA_MINIO_ENDPOINT` for internal server-side calls and `JAVA_MINIO_PUBLIC_ENDPOINT` for public-facing presigned URL signing.
- Automated retry/backoff for failed indexing, poison-message handling, DLQ analytics, and manual reindex endpoint/permission.
- Actual raw download tracking through MinIO event webhooks.
- Phase 2 password policy developer docs: document that passwords containing username or email local part are rejected.

## Stop Point

Project is ready for Phase 4 discussion, but Phase 4 has not been started. Wait for explicit user instruction before running `$gsd-discuss-phase 4`.
