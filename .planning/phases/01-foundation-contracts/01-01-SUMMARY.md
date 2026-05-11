---
phase: 01-foundation-contracts
plan: 01
subsystem: contracts
tags: [openapi, asyncapi, rabbitmq, rfc7807, contract-first]

requires: []
provides:
  - Frontend-facing Java REST OpenAPI v1 contract.
  - Internal Java-to-Python AI service OpenAPI v1 contract.
  - RabbitMQ AsyncAPI v1 document lifecycle event contract.
  - Shared routing key, queue, exchange, and error-code constants.
affects: [backend, ai-service, frontend, phase-01-contract-generation]

tech-stack:
  added: []
  patterns:
    - Contract-First
    - Schema as API
    - Event Envelope
    - Routing Keys as Constants
    - RFC 7807 Problem Details

key-files:
  created:
    - contracts/openapi/api-v1.yaml
    - contracts/openapi/ai-service-v1.yaml
    - contracts/asyncapi/events-v1.yaml
    - contracts/constants.yaml
  modified: []

key-decisions:
  - "Root contracts/ remains the only shared source location for REST, event, and generated constant contracts."
  - "REST error surfaces use RFC 7807 ProblemDetail with standard Phase 1 status families."
  - "RabbitMQ events use EventEnvelope metadata and constants.yaml-owned routing names."

patterns-established:
  - "OpenAPI contracts define DTOs, auth expectations, examples, and ProblemDetail responses before service code."
  - "AsyncAPI messages wrap typed payloads in EventEnvelope metadata for tracing and idempotency."
  - "constants.yaml is the generation source for Java and Python routing, queue, exchange, and error constants."

requirements-completed: [FND-02]

duration: 2 min
completed: 2026-05-11
---

# Phase 01 Plan 01: Define Root Contracts Summary

**Shared OpenAPI, AsyncAPI, and constants contracts for the Java API, Python AI API, and RabbitMQ document events**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-11T18:19:03Z
- **Completed:** 2026-05-11T18:21:18Z
- **Tasks:** 2 completed
- **Files modified:** 4 contract source files were verified

## Accomplishments

- Verified `contracts/openapi/api-v1.yaml` covers the frontend-facing Java REST surface for auth, users, roles, access policies, documents, chat, root discovery, HATEOAS links, access filters, pagination, and ProblemDetail errors.
- Verified `contracts/openapi/ai-service-v1.yaml` covers the internal Java-to-Python query, citation chunk lookup, health, and readiness endpoints with compatible query, citation, guard, retrieval, and error schemas.
- Verified `contracts/asyncapi/events-v1.yaml` covers `document.uploaded`, `document.deleted`, `document.indexed`, and `document.indexing.failed` with EventEnvelope metadata.
- Verified `contracts/constants.yaml` defines routing keys, queues, exchanges, DLQ names, and REST/event error codes for later Java and Python generation.

## Task Commits

The contract artifacts were already present in git history before this executor started:

1. **Task 1: Create REST contract sources** - `d1ba7de` (`feat(contracts): add v1 contract baseline (OpenAPI + AsyncAPI + constants)`)
2. **Task 2: Create event contract and shared constants** - `d1ba7de` (`feat(contracts): add v1 contract baseline (OpenAPI + AsyncAPI + constants)`)

**Plan metadata:** recorded in the `docs(01-01): complete define root contracts plan` completion commit.

## Files Created/Modified

- `contracts/openapi/api-v1.yaml` - Frontend-facing Java REST API contract.
- `contracts/openapi/ai-service-v1.yaml` - Internal Python AI service REST contract.
- `contracts/asyncapi/events-v1.yaml` - RabbitMQ document lifecycle event contract.
- `contracts/constants.yaml` - Shared routing, queue, exchange, and error-code constants.

## Verification

- `python -c "...REST contract sources present..."` - **environment note**: neither `python` nor `py` is installed on PATH in this runner.
- PowerShell equivalent of Task 1 token assertions - **PASS**: `REST contract sources present`.
- PowerShell equivalent of Task 2 token assertions - **PASS**: `event contract and constants present`.
- Root-only contract source scan - **PASS**: only the four expected YAML files exist under root `contracts/`.
- Stub scan over the four contract files - **PASS**: no `TODO`, `FIXME`, placeholder, or empty hardcoded UI-flow stubs found.

## Decisions Made

- None beyond the Phase 1 decisions. Execution followed D-01, D-02, D-03, D-04, D-05, D-06, D-08, D-09, D-10, and D-13.

## Deviations from Plan

None - the planned contract artifacts matched the required scope. The only execution difference was environmental: the exact Python verification command could not run because Python is not installed on PATH, so the same assertions were run with PowerShell.

## Issues Encountered

- Python launcher unavailable: `python -c ...` and `py --version` both reported no installed launcher. Contract verification continued because the plan checks are file/token assertions and were reproduced with PowerShell.

## Known Stubs

None.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 01-02 to add contract generation and verification tooling against these root source files.

## Self-Check: PASSED

- Found all four contract source files.
- Found production contract commit `d1ba7de`.
- Verification assertions passed with PowerShell equivalents.
- No duplicate service-local contract source files were found.

---
*Phase: 01-foundation-contracts*
*Completed: 2026-05-11*
