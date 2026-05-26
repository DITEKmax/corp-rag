---
phase: 06-chat-frontend-experience
plan: 08
subsystem: frontend-admin
tags: [vanilla-js, admin-ui, rbac, documents, users, roles, access-policies]
requires:
  - phase: 06-chat-frontend-experience
    provides: frontend shell, route guards, and central API client
  - phase: 02-identity-access
    provides: users, roles, user-role assignment, and access policies
  - phase: 03-document-lifecycle
    provides: document list/upload/delete/raw endpoints
provides:
  - compact admin screens for documents, users, roles, and access policies
  - contract-derived frontend permission-code module
  - admin API wrapper over existing Java endpoints
  - permission-filtered admin action visibility
affects: [frontend, admin-uat, phase-09]
tech-stack:
  added: []
  patterns: [contract-derived generated frontend constants, admin route layout, table-plus-drawer screens]
key-files:
  created:
    - frontend/js/api/admin-api.js
    - frontend/js/components/admin/admin-ui.js
    - frontend/js/components/admin/document-table.js
    - frontend/js/components/admin/user-drawer.js
    - frontend/js/components/admin/role-drawer.js
    - frontend/js/components/admin/access-policy-drawer.js
    - frontend/js/generated/permission-codes.js
    - frontend/js/pages/admin/admin-layout.js
    - frontend/js/pages/admin/documents-page.js
    - frontend/js/pages/admin/users-page.js
    - frontend/js/pages/admin/roles-page.js
    - frontend/js/pages/admin/access-policies-page.js
    - frontend/styles/admin.css
    - scripts/generate_frontend_permission_codes.py
  modified:
    - frontend/js/core/routes.js
key-decisions:
  - "Admin screens use existing Java endpoints only; no admin backend was added."
  - "Role permission checkboxes are generated from the OpenAPI PermissionCode enum."
  - "User-role assignment remains inside #/admin/users; no #/admin/user-roles route exists."
patterns-established:
  - "Read routes gate pages; mutation buttons are additionally filtered by specific permissions."
  - "Role and access-policy updates derive If-Match from contract version fields."
requirements-completed: [UI-03]
duration: 13min
completed: 2026-05-27
---

# Phase 06 Plan 08: Admin Frontend Summary

**Compact operational admin console covering documents, users, roles, and access policies over existing Java APIs.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-05-27T00:35:55+03:00
- **Completed:** 2026-05-27T00:49:18+03:00
- **Tasks:** 6
- **Files modified:** 15

## Accomplishments

- Added guarded admin pages for `#/admin/documents`, `#/admin/users`, `#/admin/roles`, and `#/admin/access-policies`.
- Built a shared admin layout with local admin navigation filtered from the same route table and current permissions.
- Added a central `adminApi` wrapper over Java endpoints; no direct feature `fetch` calls and no Python URLs.
- Implemented document list/upload/delete/status/raw-open operations with raw URL fetched per click and duplicate-upload detail handling.
- Implemented users table plus drawer for create, disable, reset-password, and replace-role-set operations.
- Implemented roles table plus drawer for create and permission-set editing from generated permission constants.
- Implemented access-policy list/create/edit/delete with role attachment on create and role read-only on edit.

## Endpoint Verification

- `UserController`: list/create/get/update/delete/reset-password are present.
- `UserRoleController`: `POST /api/v1/users/{userId}/roles` replaces the user's role set; no separate user-role route was added to the frontend.
- `RoleController`: list/create/get/update/delete are present; UI implements compact depth: list/create/edit permission sets.
- `AccessPolicyController`: list/create/get/update/delete are present; create attaches to role, update edits policy scope.
- `DocumentController`: list/upload/delete/raw are present; indexing status comes from the document DTO.

## Self-Lockout Evidence

- `UserController` rejects self active-flag changes with `SELF_MODIFICATION_FORBIDDEN`.
- `UserService.deleteUser` rejects self-delete and last `users.update` admin deletion with `SELF_MODIFICATION_FORBIDDEN` / `LAST_ADMIN_PROTECTED`.
- `RoleService.replaceUserRoles` rejects self role replacement and last `users.update` authority removal.
- `RoleService.updateRole` rejects removing the final role-granted `users.update` authority.
- `AccessPolicyService` raises `LAST_ADMIN_VISIBILITY_LOST` for policy mutations that would remove required full visibility.

## Permission Source

- `scripts/generate_frontend_permission_codes.py` reads the `PermissionCode` enum from `contracts/openapi/api-v1.yaml`.
- `frontend/js/generated/permission-codes.js` is generated and verified with `uv run python scripts/generate_frontend_permission_codes.py --check`.
- Role editing uses checkbox values from that generated module, not free text.

## Known Scope Notes

- Existing access-policy update does not move a policy to a different role; role attachment is supported on create. The UI does not invent a move endpoint.
- Browser smoke was not run in this plan. Live admin evidence remains part of Plan 09 integrated UAT.

## Task Commits

1. **Tasks 1-6: Admin API, routes, layout, documents, users, roles, access policies** - `4da2404` (feat)

**Plan metadata:** pending in summary commit

## Verification

- Full frontend syntax sweep: `node --check` passed for all 29 frontend JS files.
- `uv run python scripts/generate_frontend_permission_codes.py --check` passed.
- `rg -n -P "(?<![A-Za-z_])fetch\(" frontend/js -g "*.js"` found only `frontend/js/core/api-client.js`.
- Static grep found no Python `/v1/query`, `:8000`, chunk endpoint, deferred citation endpoint, or `#/admin/user-roles` route.
- Endpoint/self-lockout evidence grep found the expected controllers and backend protection codes.
- `git diff --check` passed with only the existing LF-to-CRLF warning on `frontend/js/core/routes.js`.

## User Setup Required

None for static checks. Live admin operation verification needs authenticated full and partial admin sessions in Plan 09.

## Next Phase Readiness

Plan 09 can run integrated UAT across session bootstrap, chat, source modal, admin routes, permission-gated partial admins, and live corpus prerequisites.

---
*Phase: 06-chat-frontend-experience*
*Completed: 2026-05-27*
