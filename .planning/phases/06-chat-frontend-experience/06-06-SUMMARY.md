---
phase: 06-chat-frontend-experience
plan: 06
subsystem: frontend
tags: [vanilla-js, hash-router, cookie-auth, refresh-rotation, rbac-nav]
requires:
  - phase: 06-chat-frontend-experience
    provides: contract-aligned auth, chat, and permission schemas
provides:
  - vanilla frontend app shell and session-first bootstrap
  - central API client with credentials-included requests and single-flight refresh
  - declarative route table shared by guards and navigation
  - login and forced-password-change pages
affects: [frontend, chat-ui, admin-ui, auth-flow]
tech-stack:
  added: []
  patterns: [vanilla ESM modules, memory-only session singleton, declarative guarded routes, BEM shell components]
key-files:
  created:
    - frontend/styles/app.css
    - frontend/js/app.js
    - frontend/js/core/api-client.js
    - frontend/js/core/session-state.js
    - frontend/js/core/router.js
    - frontend/js/core/routes.js
    - frontend/js/components/shell.js
    - frontend/js/components/ui.js
    - frontend/js/components/views.js
    - frontend/js/pages/login-page.js
    - frontend/js/pages/change-password-page.js
  modified:
    - frontend/index.html
key-decisions:
  - "API client uses relative /api/v1, credentials: include, and never sets Origin manually."
  - "PASSWORD_CHANGE_REQUIRED is detected from ProblemDetails before refresh-on-401 is attempted."
  - "The same route table drives guard decisions and visible navigation."
patterns-established:
  - "Feature modules must call apiClient.request or typed apiClient methods, never fetch directly."
  - "Protected route content is not rendered until bootstrap /me succeeds."
requirements-completed: [UI-01]
duration: 14min
completed: 2026-05-27
---

# Phase 06 Plan 06: Frontend Shell Summary

**Vanilla ESM app shell with session-first bootstrap, rotating-cookie-safe refresh, and permission-filtered navigation.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-05-27T00:12:31+03:00
- **Completed:** 2026-05-27T00:26:02+03:00
- **Tasks:** 4
- **Files modified:** 12

## Accomplishments

- Replaced the static frontend entrypoint with a real `#app` mount, loading skeleton, shared shell, and guarded hash router.
- Added a single API client that prefixes `/api/v1`, sends cookies with every request, parses ProblemDetails, and serializes refresh attempts through one shared promise.
- Implemented memory-only session state, login, forced password change, logout, access denied, not found, and service-unavailable retry screens.
- Built navigation from the same route table used by guards, so partial-admin visibility and direct-route denial stay consistent.

## Task Commits

1. **Tasks 1-4: Frontend shell, API client, router, auth pages** - `09d904c` (feat)

**Plan metadata:** pending in summary commit

## Files Created/Modified

- `frontend/index.html` - Mounts the module app and initial neutral loading skeleton.
- `frontend/styles/app.css` - BEM shell/auth/form/state styles using existing tokens from `base.css`.
- `frontend/js/app.js` - Session-first bootstrap through `/me`, service-unavailable fallback, and router startup.
- `frontend/js/core/api-client.js` - Central fetch wrapper with `credentials: include`, single-flight refresh, ProblemDetails mapping, and must-change routing.
- `frontend/js/core/session-state.js` - Memory-only user, permission, must-change, and return-route state.
- `frontend/js/core/router.js` - Hash router with auth, must-change, permission, denied, and not-found handling.
- `frontend/js/core/routes.js` - Declarative route table for login, change-password, chat, and admin placeholders.
- `frontend/js/components/shell.js` - Permission-filtered app shell and nav rendering.
- `frontend/js/components/ui.js` - Shared button, drawer, modal, error, empty, and escaping helpers.
- `frontend/js/components/views.js` - Loading, denied, not-found, service-unavailable, and placeholder views.
- `frontend/js/pages/login-page.js` - Login form routed through the API client and return-hash flow.
- `frontend/js/pages/change-password-page.js` - Forced password-change form routed through the API client.

## Decisions Made

- Followed the existing Java CSRF implementation: `OriginRefererValidationFilter` validates browser-sent Origin/Referer on unsafe cookie-authenticated API requests. The frontend does not and cannot set `Origin`.
- Confirmed `RefreshTokenService` rotates refresh tokens by family, so refresh is reactive and single-flight only; no timer-based refresh was added.
- Confirmed `MustChangePasswordFilter` returns ProblemDetails with `PASSWORD_CHANGE_REQUIRED` and HTTP 401. The API client parses that error code before generic 401 refresh handling, preventing a refresh loop.

## Deviations from Plan

### Auto-fixed Issues

**1. Direct-fetch verification pattern tightened**
- **Found during:** Task 2 verification
- **Issue:** The original plan's substring check would false-positive on method names like `fetchConversations`.
- **Fix:** Used the approved regex boundary gate `(?<![A-Za-z_])fetch\(` with ripgrep PCRE.
- **Files modified:** None
- **Verification:** The gate found only `frontend/js/core/api-client.js`.
- **Committed in:** `09d904c`

---

**Total deviations:** 1 auto-fixed verification issue
**Impact on plan:** Verification became stricter without changing runtime scope.

## Issues Encountered

- Browser smoke was not run in this plan. Automated checks passed, and live browser/session behavior remains covered by the later integrated UAT plan when the frontend is exercised against Java and seeded test data.

## Verification

- `node --check frontend/js/app.js`
- `node --check frontend/js/core/api-client.js`
- `node --check frontend/js/core/router.js`
- `node --check frontend/js/core/routes.js`
- `node --check frontend/js/pages/login-page.js`
- `node --check frontend/js/pages/change-password-page.js`
- `rg -n -P "(?<![A-Za-z_])fetch\(" frontend/js -g "*.js"` found only the central API client.
- `git diff --check` passed with only the existing LF-to-CRLF warning on `frontend/index.html`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Chat and admin UI plans can now use the shared API client, route table, shell, memory session state, and guarded navigation without duplicating auth or permission logic.

---
*Phase: 06-chat-frontend-experience*
*Completed: 2026-05-27*
