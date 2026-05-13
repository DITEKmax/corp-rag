# Phase 3: Documents, Events & Audit - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 3-Documents, Events & Audit
**Areas discussed:** Document visibility rules, Upload lifecycle, Events/status/audit

---

## Document Visibility Rules

| Option | Description | Selected |
|--------|-------------|----------|
| AccessFilter-only visibility | Resolved role/policy filter is the only visibility source. Ownership does not bypass it. | yes |
| Owner-bypass visibility | Owner can see/delete their own documents even outside current role policy. | |
| Hybrid visibility | AccessFilter for list/search, owner-bypass for detail/raw/delete. | |

**User's choice:** AccessFilter-only visibility.

**Notes:** The user explicitly rejected owner bypass to preserve Java/Python symmetry, avoid a second visibility axis, and keep audit simpler. Invisible existing documents return `404 DOCUMENT_NOT_FOUND` rather than `403`. Upload may target any regex-valid department regardless of uploader filter, but upload access level may not exceed uploader effective max.

---

## Upload Lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| Department-scoped content dedupe | SHA-256 duplicate detection scoped to active documents in the same department. | yes |
| Global content dedupe | Same file content rejected across all departments. | |
| No dedupe | Every upload creates a new active document. | |

**User's choice:** Department-scoped content dedupe.

**Notes:** Same content and same department returns `409 DUPLICATE_DOCUMENT` with existing document id. Same content in different departments is allowed. Same content after soft delete is allowed.

| Option | Description | Selected |
|--------|-------------|----------|
| Immediate soft delete | Set `deleted_at`/`deleted_by`, publish `document.deleted`, hide everywhere, keep MinIO object. | yes |
| Physical delete now | Delete metadata and MinIO object in Phase 3. | |
| Block delete during indexing | Return conflict while indexing may be in progress. | |

**User's choice:** Immediate soft delete; do not block delete while indexing.

**Notes:** Delete is allowed in any active status. Soft-deleted documents return 404 for list/detail/raw. Java must not resurrect deleted documents if terminal indexing events arrive after delete. Physical MinIO cleanup is deferred.

| Option | Description | Selected |
|--------|-------------|----------|
| Single bucket and deterministic key | `corp-rag-documents`, key `{yyyy}/{MM}/{documentId}.{ext}` using MIME-derived extension. | yes |
| Original filename key | Include user filename in object key. | |
| Per-department buckets | Separate bucket/storage namespace by department. | |

**User's choice:** Single bucket and deterministic key.

**Notes:** Original filename is only metadata for UI/audit. Java will idempotently ensure the bucket exists on startup.

| Option | Description | Selected |
|--------|-------------|----------|
| Tika sniff plus allowlist | Trust sniffed MIME, treat client `Content-Type` as hint, enforce 50 MB limit. | yes |
| Trust client Content-Type | Use multipart header as MIME source. | |
| Allow all files | Accept arbitrary source files and let Python fail unsupported formats. | |

**User's choice:** Tika sniff plus allowlist.

**Notes:** Allowed types are PDF, DOCX, HTML, Markdown, and plain text. Sniffed/client mismatch is audited but not blocked if sniffed MIME is allowed.

---

## Events, Status, And Audit

| Option | Description | Selected |
|--------|-------------|----------|
| Terminal-only Phase 3 statuses | Java keeps `UPLOADED` until `INDEXED` or `INDEXING_FAILED`; `INDEXING` remains reserved. | yes |
| Java sets INDEXING optimistically | Switch to `INDEXING` after outbox publication or a started signal. | |
| Add indexing-started event | Introduce a new lifecycle event before terminal events. | |

**User's choice:** Terminal-only Phase 3 statuses.

**Notes:** No Phase 3 transition back from `INDEXING_FAILED`. Failed-document recovery is delete and re-upload.

| Option | Description | Selected |
|--------|-------------|----------|
| Defer reindex endpoint | No `POST /documents/{id}/reindex` and no `documents.reindex` in Phase 3. | yes |
| Add manual reindex now | Add endpoint, permission, seed changes, and status transition back to UPLOADED. | |
| Add automatic retry now | Retry retryable failures with backoff. | |

**User's choice:** Defer reindex endpoint and automatic retry.

**Notes:** `retryable` from Python is recorded in audit/details only. Reindex and automatic retry are Phase 7+ scope.

| Option | Description | Selected |
|--------|-------------|----------|
| Outbox plus idempotent consumers | Use `outbox_events`, scheduled publisher, and `processed_events`. | yes |
| Direct RabbitMQ publish | Publish from request transaction without outbox. | |
| Fire-and-forget only | Do not persist delivery state. | |

**User's choice:** Outbox plus idempotent consumers.

**Notes:** Outbox uses at-least-once delivery, exponential backoff, unlimited attempts, 7-day published cleanup. Consumers use transactional `processed_events` and ACK only after commit.

| Option | Description | Selected |
|--------|-------------|----------|
| Full correlation cleanup | Spring MDC filter, audit writer MDC, outbox/event/header propagation, consumer MDC. | yes |
| Only Phase 3 correlation | Leave Phase 2 audit behavior unchanged. | |
| Skip correlation cleanup | Continue random audit correlation ids. | |

**User's choice:** Full correlation cleanup.

**Notes:** This is a deliberate Phase 3 cross-cutting cleanup so Phase 2 audit rows and Phase 3 document/event rows share request correlation when available.

## the agent's Discretion

- Choose exact package/class names and mapper implementation details.
- Choose stream hashing/Tika mechanics that satisfy the file-size and MIME decisions.
- Choose exact RabbitMQ retry/DLQ configuration consistent with the contracts.
- Choose exact Java startup bucket initializer implementation.

## Deferred Ideas

- Department dictionary table/CRUD.
- Physical MinIO cleanup, hard delete, purge, and retention policies.
- Manual reindex endpoint and `documents.reindex`.
- Automatic indexing retry/backoff and DLQ analytics.
- Actual download tracking via MinIO event webhooks.
- Python-side tombstone implementation for delete-before-upload race handling.
