---
status: partial
phase: 06-chat-frontend-experience
source: [06-VERIFICATION.md]
started: 2026-05-27
updated: 2026-05-27
---

# Phase 6 Human UAT

## Current Test

Awaiting browser UAT with running local stack, seeded users, fresh indexed corpus, and reranker pre-warm.

## Tests

### 1. Session Flow

expected: `/me` bootstrap, login, forced password change, refresh, logout, access denied, and service-unavailable behavior work in browser.
result: pending

### 2. Chat Flow

expected: lazy create, query, outcomes, retry, history reload, soft delete, and 429 behavior work through Java.
result: pending

### 3. Source Modal

expected: cited source opens from returned quote/snippet only and displays document text, never graph markers.
result: pending

### 4. Admin Console

expected: full and partial admins can exercise permitted document, user, role, and access-policy workflows.
result: pending

### 5. Audit/Correlation

expected: live DB/audit evidence confirms shared query correlation ids and 429 audit-without-chat-row behavior.
result: pending

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0
