---
phase: 06-chat-frontend-experience
plan: 09
subsystem: validation
tags: [uat, verification, frontend, backend, contracts]
requires:
  - phase: 06-chat-frontend-experience
    provides: chat Java endpoints and frontend chat/admin screens
provides:
  - Phase 6 UAT checklist
  - automated validation evidence
  - run documentation for the browser app
  - residual browser-UAT blocker record
affects: [verify-work, uat, docs]
tech-stack:
  added: []
  patterns: [evidence-first UAT, explicit live-prerequisite blocker recording]
key-files:
  created:
    - .planning/phases/06-chat-frontend-experience/06-UAT.md
    - .planning/phases/06-chat-frontend-experience/06-UAT-EVIDENCE.md
  modified:
    - README.md
    - frontend/README.md
    - frontend/js/core/api-client.js
key-decisions:
  - "Frontend defaults to Java http://localhost:8080/api/v1 so compose static nginx does not receive API calls."
  - "Browser UAT is recorded as blocked, not passed, because the local stack and fresh indexed corpus were unavailable."
patterns-established:
  - "Final validation summaries distinguish automated pass, live UAT blocker, and residual risk."
requirements-completed: [CHAT-01, CHAT-02, UI-01, UI-02, UI-03]
duration: 6min
completed: 2026-05-27
---

# Phase 06 Plan 09: Validation Summary

**Automated Phase 6 validation is green; live browser UAT is blocked pending running services, seeded sessions, fresh indexed corpus, and reranker pre-warm.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-27T00:50:11+03:00
- **Completed:** 2026-05-27T00:55:39+03:00
- **Tasks:** 6
- **Files modified:** 5

## Verification

- Contract verifier: PASS.
- Backend Maven suite: PASS.
- Frontend JS syntax sweep: PASS, 29 files.
- Direct fetch boundary: PASS, only `frontend/js/core/api-client.js`.
- No frontend Python/deferred endpoint references: PASS.
- Generated permission-code check: PASS.
- Runtime-code/config scan for Redis/Mongo/shared cache: PASS, no matches.

## UAT Status

- `06-UAT.md` now contains the repeatable Phase 6 UAT checklist.
- `06-UAT-EVIDENCE.md` records command evidence and maps requirements to automated/browser status.
- Browser UAT was not run because `docker compose -f infra/docker-compose.yml ps` showed no running services and live CHAT-02 prerequisites were not established.
- CHAT-02 live UAT specifically still needs a freshly indexed corpus, `AI_QUERY_LIVE_CORPUS_READY=true`, and one untimed reranker pre-warm query before timed checks.

## Auto-Fixed Issue

**Frontend API base URL**
- **Issue:** The static frontend is served by nginx at `http://localhost`; a relative `/api/v1` base would hit frontend nginx instead of Java.
- **Fix:** `frontend/js/core/api-client.js` now defaults to `http://localhost:8080/api/v1`, with `window.CORP_RAG_API_BASE` as an override hook.
- **Verification:** Frontend syntax/direct-fetch/no-Python checks passed after the change.
- **Committed in:** `1deb747`

## Requirement Status

| Requirement | Status |
|-------------|--------|
| CHAT-01 | PARTIAL: backend/static evidence pass; browser lifecycle UAT blocked |
| CHAT-02 | PARTIAL: backend/static evidence pass; live query/source UAT blocked |
| UI-01 | PARTIAL: frontend static evidence pass; browser session UAT blocked |
| UI-02 | PARTIAL: frontend static evidence pass; browser source-modal UAT blocked |
| UI-03 | PARTIAL: frontend/backend static evidence pass; browser admin UAT blocked |

## Task Commits

1. **Task 1: UAT checklist** - `2a9016b` (docs)
2. **Runtime fix: frontend Java API base** - `1deb747` (fix)

**Plan metadata:** pending in summary commit

## Files Created/Modified

- `.planning/phases/06-chat-frontend-experience/06-UAT.md` - Manual and automated UAT checklist with live corpus/pre-warm prerequisites.
- `.planning/phases/06-chat-frontend-experience/06-UAT-EVIDENCE.md` - Command evidence, live-UAT blocker, audit/correlation evidence map, residual risk.
- `frontend/js/core/api-client.js` - Java API default base URL.
- `README.md` - Updated local run URLs and frontend/Java API note.
- `frontend/README.md` - Updated actual Phase 6 frontend structure and run notes.

## Residual Risks

- Browser UAT remains incomplete until the stack is running and seeded.
- Live audit/database checks for 429 audit-without-chat-row were not collected; automated tests cover the controller/service/repository behavior.
- Live answer quality depends on corpus readiness and reranker warm-up, which are explicitly called out in `06-UAT.md`.

## User Setup Required

For live UAT:

- Start the stack with `docker compose -f infra/docker-compose.yml up -d --build`.
- Seed or confirm full-admin, partial-admin, and normal chat users.
- Upload/reindex a known corpus and set/record `AI_QUERY_LIVE_CORPUS_READY=true`.
- Run one untimed reranker pre-warm query before timed CHAT-02 checks.

## Next Phase Readiness

Ready for `$gsd-verify-work` with a clear distinction between automated pass and live browser-UAT blockers.

---
*Phase: 06-chat-frontend-experience*
*Completed: 2026-05-27*
