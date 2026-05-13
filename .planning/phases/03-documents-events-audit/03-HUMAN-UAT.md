---
status: partial
phase: 03-documents-events-audit
source: [03-VERIFICATION.md]
started: 2026-05-14T00:27:16+03:00
updated: 2026-05-14T00:27:16+03:00
---

## Current Test

[awaiting human testing]

## Tests

### 1. Docker-backed external integration
expected: A supported document upload stores the object in MinIO, persists metadata/status in PostgreSQL, emits document.uploaded and document.deleted through the outbox to RabbitMQ, consumes document.indexed and document.indexing.failed messages idempotently, and writes correlated audit rows.
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
