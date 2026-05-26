---
phase: 6
slug: chat-frontend-experience
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-26
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Maven/JUnit for Java; contract verifier for generated DTOs; vanilla JS static checks; browser UAT |
| **Config file** | `backend/pom.xml`, `backend/corp-rag-app/pom.xml`, `scripts/verify-contracts.py`, `frontend/**` |
| **Quick run command** | `cd backend; mvn -q -pl corp-rag-app -am test` |
| **Full suite command** | `$env:MAVEN_CMD='C:\dev\apache-maven-3.9.15\bin\mvn.cmd'; uv run --project ai-service --group dev python scripts/verify-contracts.py` plus backend tests and browser UAT |
| **Estimated runtime** | ~180-600 seconds depending on Docker/live UAT |

## Sampling Rate

- **After every task commit:** Run the smallest relevant contract/backend/frontend check listed on the plan task.
- **After every plan wave:** Run contract verification if contracts changed, plus `cd backend; mvn -q -pl corp-rag-app -am test` after backend waves.
- **Before `$gsd-verify-work`:** Contract verifier, backend tests, frontend static checks, and browser UAT must be green or explicitly deferred with reason.
- **Max feedback latency:** Keep focused task checks under 120 seconds; full stack checks are allowed at wave boundaries.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | CHAT-01, CHAT-02, UI-02 | T-06-01-01 | Contract exposes nullable outcomes without weakening guard semantics. | contract | `uv run --project ai-service --group dev python scripts/verify-contracts.py` | planned | pending |
| 06-02-01 | 02 | 2 | CHAT-01 | T-06-02-01 | Chat rows are owner-scoped and soft-deleted without hard-delete trace loss. | repository/integration | `cd backend; mvn -q -pl corp-rag-app -am test` | planned | pending |
| 06-03-01 | 03 | 2 | CHAT-02 | T-06-03-01 | 429 is pre-persistence and audited; refresh/audit conventions are reused. | unit/slice | `cd backend; mvn -q -pl corp-rag-app -am test` | planned | pending |
| 06-04-01 | 04 | 3 | CHAT-01 | T-06-04-01 | Conversation APIs return only owner, non-deleted rows. | MVC/slice | `cd backend; mvn -q -pl corp-rag-app -am test` | planned | pending |
| 06-05-01 | 05 | 4 | CHAT-02 | T-06-05-01 | Java calls Python only after auth/access/rate checks and persists paired outcomes. | unit/slice | `cd backend; mvn -q -pl corp-rag-app -am test` | planned | pending |
| 06-06-01 | 06 | 4 | UI-01 | T-06-06-01 | Session-first router blocks protected content until `/me` resolves. | static/browser | `node --check frontend/js/app.js` plus direct-fetch grep | planned | pending |
| 06-07-01 | 07 | 5 | UI-02 | T-06-07-01 | Chat UI never calls Python and never renders invalid BL-02 answer text. | static/browser | `node --check` over `frontend/js/**/*.js` plus browser UAT | planned | pending |
| 06-08-01 | 08 | 5 | UI-03 | T-06-08-01 | Admin routes and actions are permission-gated by the shared route table/client. | static/browser | frontend static checks plus browser UAT | planned | pending |
| 06-09-01 | 09 | 6 | CHAT-01, CHAT-02, UI-01, UI-02, UI-03 | T-06-09-01 | End-to-end browser workflows preserve auth, access, audit, and citation safety. | full/UAT | contract verifier, backend tests, browser UAT | planned | pending |

## Wave 0 Requirements

Existing infrastructure covers the phase:

- `scripts/verify-contracts.py` covers contract lint/codegen/compile.
- Backend Maven/JUnit infrastructure already exists.
- Frontend has no test runner; Phase 6 plans add static checks and browser UAT rather than installing a framework.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Browser login/change-password routing | UI-01 | Requires httpOnly cookies and route transitions in a browser. | Use local frontend and Java; verify `/me` bootstrap, login, forced password change, refresh, and logout. |
| Chat answer/source modal with live Python | CHAT-02, UI-02 | Requires indexed corpus and running Python query pipeline. | Ask an answerable question; verify Java owns the call, history persists, citations render, and source modal shows document text. |
| Admin compact console | UI-03 | Requires seeded users/roles/documents/policies and permission variations. | Log in as full and partial admins; verify permitted nav, access denied on forbidden deep links, and destructive confirmations. |

## Validation Sign-Off

- [x] All tasks have automated verify or a documented manual UAT layer.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency target documented.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** planned 2026-05-26
