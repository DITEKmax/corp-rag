---
phase: "06-chat-frontend-experience"
plan: "01"
subsystem: "api"
tags: ["openapi", "contracts", "chat", "problem-details", "csrf"]

requires:
  - phase: "02-identity-users-access-control"
    provides: "cookie auth, refresh rotation, must-change-password, permissions"
  - phase: "03-documents-events-audit"
    provides: "ProblemDetails, audit writer, document/source conventions"
  - phase: "05-retrieval-guards-query-api"
    provides: "Python query and citation contract"
provides:
  - "Phase 6 chat/message OpenAPI outcome contract"
  - "nullable Message.retrievalMeta history diagnostics"
  - "deferred quote-only source viewer contract boundary"
  - "POST /chat/query 429 ProblemDetail and Retry-After shape"
affects: ["06-02", "06-03", "06-04", "06-05", "06-06", "06-07"]

tech-stack:
  added: []
  patterns: ["contract-first OpenAPI gate before Java/frontend implementation"]

key-files:
  created:
    - ".planning/phases/06-chat-frontend-experience/06-01-SUMMARY.md"
  modified:
    - "contracts/openapi/api-v1.yaml"
    - "contracts/openapi/ai-service-v1.yaml"

key-decisions:
  - "Java CSRF protection is Origin/Referer validation through OriginRefererValidationFilter; Spring CSRF is disabled and no double-submit token path was found."
  - "Message and ChatQueryResponse now expose AssistantMessageStatus and nullable content/citations/retrievalMeta so status-only outcomes do not need placeholder answer text."
  - "getCitationDetails is explicitly deferred for Phase 6; source viewing uses returned citation quote/snippet snapshots only."
  - "POST /chat/query rate limiting uses the existing ProblemDetail errorCode/correlationId/details style plus Retry-After."

patterns-established:
  - "Generated DTOs are verified before backend implementation depends on new contract fields."
  - "Deferred full-content source viewer text must name the real Python path and the Java live access-check requirement."

requirements-completed: ["CHAT-01", "CHAT-02", "UI-01", "UI-02", "UI-03"]

duration: "35 min"
completed: "2026-05-26"
---

# Phase 6 Plan 01: Contract Preflight Summary

**Chat outcomes, source-viewer scope, and rate-limit errors are explicit in OpenAPI and verified before Java implementation.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-05-26T22:50:00+03:00
- **Completed:** 2026-05-26T23:24:46+03:00
- **Tasks:** 4
- **Files modified:** 2

## Accomplishments

- Verified the concrete backend anchors before contract edits: `OriginRefererValidationFilter`, `SecurityConfig`, `AppSecurityProperties`, `RefreshTokenService`, `ProblemDetailsWriter`, `ProblemDetailsExceptionHandler`, and `AuditEventWriter`.
- Added `AssistantMessageStatus` with `ANSWERED`, `REFUSED_GUARD`, `NO_EVIDENCE`, `DEGRADED`, `TIMEOUT`, and `AI_UNAVAILABLE`.
- Updated `Message` for nullable `content`, nullable citation snapshots, nullable `retrievalMeta`, and assistant status history rendering.
- Updated `ChatQueryResponse` to carry outcome status and support `ANSWERED`, `NO_EVIDENCE`, and `DEGRADED` 200 responses without unsafe placeholder text.
- Marked `getCitationDetails` deferred for Phase 6 and corrected the stale Python chunk path to `GET /v1/documents/{documentId}/chunks/{chunkId}`.
- Documented `POST /chat/query` 429 as RFC7807 `ProblemDetail` with `RATE_LIMIT_EXCEEDED`, `correlationId`, `details`, and `Retry-After`.

## Task Commits

1. **Task 1: Verify first-wave backend anchors** - read-only verification, no commit.
2. **Tasks 2-4: Align schemas, defer source details, verify contracts** - `837ced1` (`feat(06-01): align chat contracts`)

## Files Created/Modified

- `contracts/openapi/api-v1.yaml` - Chat message/query status contract, nullable history diagnostics, deferred citation detail wording, and 429 response details.
- `contracts/openapi/ai-service-v1.yaml` - Fixed stale Citation text to reference the real chunk detail path.

## Decisions Made

- No frontend CSRF token echo path is required: Java uses Origin/Referer validation and `SecurityConfig` disables Spring CSRF.
- The response/status contract is the source of truth for UI bubble variants; Java/frontend must not infer DEGRADED or failure states from empty strings.
- The Phase 6 source viewer remains quote-only; the deferred full-content path must later add Java ownership and live access checks before calling Python.

## Deviations from Plan

None - plan scope was executed as written.

## Issues Encountered

- Initial verifier run failed because the new deferred summary contained an unquoted colon in YAML. Quoting the summary fixed parsing; the full verifier then passed.

## Verification

- `rg -n "OriginRefererValidationFilter|csrf\\(|RefreshTokenService|ProblemDetailsWriter|AuditEventWriter|RATE_LIMIT_EXCEEDED" backend contracts`
- `rg -n "AssistantMessageStatus|ANSWERED|REFUSED_GUARD|NO_EVIDENCE|DEGRADED|TIMEOUT|AI_UNAVAILABLE|retrievalMeta|Retry-After|RATE_LIMIT_EXCEEDED|/v1/documents/\\{documentId\\}/chunks/\\{chunkId\\}" contracts/openapi/api-v1.yaml contracts/openapi/ai-service-v1.yaml contracts/constants.yaml`
- `rg -n "GET /chunks\\{chunkId\\}" contracts/openapi/api-v1.yaml contracts/openapi/ai-service-v1.yaml` returned no matches.
- `$env:MAVEN_CMD='C:\\dev\\apache-maven-3.9.15\\bin\\mvn.cmd'; uv run --project ai-service --group dev python scripts/verify-contracts.py` passed.

## User Setup Required

None - no external service configuration is required. The local verifier used the repository-approved Windows Maven path through `MAVEN_CMD`.

## Next Phase Readiness

Ready for Plan 06-02 Java chat schema and repositories. Downstream plans can rely on generated DTOs for assistant status, nullable message content, history diagnostics, and 429 error shape.

---
*Phase: 06-chat-frontend-experience*
*Completed: 2026-05-26*
