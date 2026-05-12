---
phase: "02-identity-users-access-control"
plan: "01"
subsystem: api
tags: [openapi, contracts, auth, rbac, access-filter]
requires:
  - phase: "01-foundation-contracts"
    provides: "contract verification, generated Java/Python contract surfaces"
provides:
  - "Phase 2 REST contract for auth refresh, password lifecycle, users, roles, and access policies"
  - "Phase 2 shared error-code constants"
  - "Java-to-Python AccessFilter compatibility semantics"
affects: ["02-identity-users-access-control", "java-backend", "python-ai"]
tech-stack:
  added: []
  patterns: ["contract-first API changes before implementation"]
key-files:
  created: []
  modified:
    - "contracts/openapi/api-v1.yaml"
    - "contracts/openapi/ai-service-v1.yaml"
    - "contracts/constants.yaml"
key-decisions:
  - "Kept Phase 2 admin APIs in the flat /users, /roles, and /access-policies namespace."
  - "Documented ETag/If-Match optimistic concurrency for full replacement role and access-policy updates."
  - "Kept AccessFilter field names and enum values aligned between Java API and Python AI service contracts."
patterns-established:
  - "Temporary passwords are returned only through create/reset response DTOs, not normal User DTOs."
  - "Permission wire values are contract-enforced lower dotted strings."
requirements-completed: ["AUTH-01", "AUTH-02", "AUTH-03", "AUTH-04"]
duration: "31 min"
completed: "2026-05-12"
---

# Phase 02 Plan 01: Contract-First Identity Surface Summary

**Phase 2 auth, RBAC, user, role, access-policy, and AccessFilter contracts with generated Java/Python verification**

## Performance

- **Duration:** 31 min
- **Started:** 2026-05-12T04:23:00Z
- **Completed:** 2026-05-12T04:54:08Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `POST /auth/refresh`, `POST /auth/password`, and `POST /users/{userId}/reset-password`.
- Updated cookie contract paths to `corp_rag_session` at `/api/v1` and `corp_rag_refresh` at `/api/v1/auth`.
- Removed password input from `CreateUserRequest` and added one-time temporary password response DTOs.
- Converted role and access-policy updates to full `PUT` replacement with `If-Match`, `ETag`, 428, and 412 semantics.
- Added Phase 2 error constants and preserved Python `QueryRequest.accessFilter` compatibility.

## Task Commits

1. **Task 1: Extend Java API contract for Phase 2 identity flows** - `4bd4285` (feat)
2. **Task 2: Add Phase 2 constants and AccessFilter compatibility checks** - `1b0ce50` (feat)

**Plan metadata:** this summary commit

## Files Created/Modified

- `contracts/openapi/api-v1.yaml` - Adds Phase 2 identity API paths, cookie semantics, one-time password DTOs, permission enum, and ETag replacement contracts.
- `contracts/openapi/ai-service-v1.yaml` - Clarifies AccessFilter wildcard department semantics while preserving required fields and enum values.
- `contracts/constants.yaml` - Adds Phase 2 auth, RBAC, origin-validation, audit, and access-policy error constants.

## Decisions Made

- None beyond the locked Phase 2 decisions; execution followed the plan.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `scripts/verify-contracts.py` needed to run outside the Codex sandbox because the Maven compiler failed with `Access is denied` when launched from the sandbox. The unrestricted run completed successfully.

## Verification

- `python scripts/verify-contracts.py` - passed with escalated permissions due the sandboxed Maven compiler access issue.
- Targeted acceptance checks confirmed `/auth/refresh`, `/auth/password`, `/users/{userId}/reset-password`, cookie paths, no `CreateUserRequest.password`, ETag/If-Match responses, all Phase 2 error constants, and AccessFilter field/enum compatibility.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 2 implementation plans can generate and compile Java/Python contract surfaces against the updated auth, user, role, access-policy, and AccessFilter schemas.

---
*Phase: 02-identity-users-access-control*
*Completed: 2026-05-12*
