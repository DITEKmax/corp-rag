---
status: complete
result: passed
phase: 03-documents-events-audit
source: [03-VERIFICATION.md]
started: 2026-05-14T00:27:16+03:00
updated: 2026-05-17T16:08:14+03:00
---

## Current Test

[testing complete]

## Tests

### 1. Docker-backed external integration
expected: A supported document upload stores the object in MinIO, persists metadata/status in PostgreSQL, emits document.uploaded and document.deleted through the outbox to RabbitMQ, consumes document.indexed and document.indexing.failed messages idempotently, and writes correlated audit rows.
result: passed
notes:
  - Clean Docker stack was exercised with postgres, minio, rabbitmq, and java-backend from clean volumes and force-recreated containers.
  - Admin login passed using the Phase 2 bootstrap and password change flow.
  - Document upload returned REST 201 and confirmed multipart handling, MIME sniffing, SHA-256 hashing, MinIO PUT, DB insert, outbox insert, and audit insert in the intended transaction boundary.
  - Outbox publisher polled within the configured cadence, published to RabbitMQ with persistent delivery, added x-correlation-id, x-event-type, and x-event-version headers, and emitted a payload containing all 14 required AsyncAPI fields.
  - Document list and detail passed SQL visibility filtering, HATEOAS link behavior, and D-49 no-audit behavior for ordinary reads.
  - Raw URL issuance returned a 5-minute MinIO presigned URL, wrote DOCUMENT_RAW_URL_ISSUED audit, and content integrity was verified through curl from inside the java-backend container.
  - Same-department duplicate upload returned 409 DUPLICATE_DOCUMENT with details.existingDocumentId matching the original document; DB and MinIO each retained only one active copy.
  - Cross-department duplicate upload returned 201, confirming the D-18 partial unique scope by department.
  - Delete returned 204, soft-deleted via deleted_at/deleted_by, retained status and MinIO object per D-26, emitted document.deleted and DOCUMENT_DELETED audit, and subsequent read/raw returned 404 per D-04.
  - Manual document.indexed event moved an active document from UPLOADED to INDEXED, stored chunkCount, durationMs, qdrantCollection, and neo4jEntityCount, and wrote audit with AMQP header correlation restored through MDC.
  - Idempotency passed: redelivery of the same eventId did not increase processed_events count, did not duplicate audit, and still ACKed through ON CONFLICT DO NOTHING behavior.
  - D-30 late-event protection passed: a late indexed event for a soft-deleted document did not resurrect status or visibility, wrote audit details.statusUpdated=false, and marked the event processed.
  - Correlation propagation passed across HTTP request header, response header, audit_events.correlation_id, outbox_events.correlation_id, AMQP x-correlation-id, and AMQP payload metadata.correlationId.
  - RabbitMQ topology passed: all eight queues were running with DLX bindings for main queues and exchanges corp-rag.documents and corp-rag.documents.dlx present.

## Summary

total: 1
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

### A. Compose admin bootstrap env vars were missing

ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD, and ADMIN_BOOTSTRAP_ENABLED existed in `.env` but were not passed through `infra/docker-compose.yml` to `java-backend`. This was a pre-existing Phase 2 compose gap discovered by clean Phase 3 UAT. The additive compose fix is included in the Phase 3 closeout commit.

### B. MinIO presigned URL uses the internal Docker hostname

MinIO presigned URLs currently contain the internal Docker hostname `minio:9000`, which is not resolvable from the host machine. AWS Signature V4 does not allow post-hoc hostname rewrites because the hostname participates in the signature. Production deployment needs a configuration split: `JAVA_MINIO_ENDPOINT` for internal server-side MinIO API calls and `JAVA_MINIO_PUBLIC_ENDPOINT` for public-facing presigned URL signing. Phase 3 MVP accepts this limitation: UAT verified content integrity by curling the URL from inside the `java-backend` container. Implement in Phase 7+ production hardening together with MinIO orphan cleanup and publisher confirms.

### C. Password policy behavior needs developer-facing documentation

Phase 2 password policy correctly rejects passwords containing the username or email local part, but this behavior is not documented in developer-facing notes. Phase 7 cleanup can add the policy description to the `/api/v1/auth/password` OpenAPI description.
