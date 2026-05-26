---
phase: 6
slug: chat-frontend-experience
status: complete
created: 2026-05-26
---

# Phase 6 — Existing Pattern Map

## Backend REST

| New Work | Closest Existing Pattern | Notes |
|----------|--------------------------|-------|
| `ChatController` conversation endpoints | `UserController`, `RoleController`, `DocumentController` | Use generated DTOs, `JwtAuthorization.requirePermission`, and project ProblemDetails style. |
| `/chat/query` error responses | `ProblemDetailsWriter`, `ProblemDetailsExceptionHandler` | Reuse `errorCode`, `correlationId`, `details`, RFC7807 content type. |
| Chat owner scoping | `DocumentQueryService` + `AccessFilterResolver` usage | Pass authenticated user id through service/repository; do not rely on frontend filtering. |

## Backend Persistence

| New Work | Closest Existing Pattern | Notes |
|----------|--------------------------|-------|
| Chat Flyway migration | `backend/corp-rag-app/src/main/resources/db/migration/V*.sql` | Next migration is `V14__...`; existing tables include `users`, `documents`, `audit_events`, `outbox_events`. |
| Chat repositories | `DocumentRepository`, `AuditEventRepository`, `UserRepository` | Follow JDBC/domain mapping style; use JSONB mapping for citations/retrieval metadata. |
| Query audit | `AuditEventWriter` | Existing audit table is the target; no query-audit table. |

## Security And Session

| New Work | Closest Existing Pattern | Notes |
|----------|--------------------------|-------|
| API client CSRF assumptions | `OriginRefererValidationFilter`, `SecurityConfig` | Spring CSRF is disabled; unsafe cookie-auth requests use Origin/Referer validation. Browser sets `Origin`; frontend must not. |
| Refresh-on-401 | `RefreshTokenService` | Refresh token family rotation requires single-flight refresh on the frontend. |
| Must-change-password routing | `MustChangePasswordFilter`, `AuthController` | Frontend must honor `/me.mustChangePassword` and reactive filter rejection. |

## Frontend

| New Work | Closest Existing Pattern | Notes |
|----------|--------------------------|-------|
| App shell/router/client | `frontend/index.html`, `frontend/styles/base.css` | There is no framework. Add vanilla JS modules and BEM styles while reusing base tokens. |
| Admin UI | Existing Java admin controllers | Frontend-only compact screens; no silent backend additions. |
| Source modal | `Citation.quote` contract | Modal is data-only from returned citation snapshot; no Python or Java chunk proxy. |

## Verification

| New Work | Closest Existing Pattern | Notes |
|----------|--------------------------|-------|
| Contract-first gate | `scripts/verify-contracts.py` | Run before Java DTO-dependent code. |
| Backend tests | Existing Maven/JUnit tests under `backend/corp-rag-app/src/test` | Add focused service/controller/repository tests for chat. |
| Frontend checks | No existing test runner | Use `node --check`, static no-direct-fetch/no-Python grep, and browser UAT. |
