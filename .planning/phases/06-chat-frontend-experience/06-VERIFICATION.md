---
phase: 06-chat-frontend-experience
status: human_needed
created: 2026-05-27
requirements: [CHAT-01, CHAT-02, UI-01, UI-02, UI-03]
---

# Phase 6 Verification

## Verdict

`human_needed`

Automated validation is green. Live UAT on 2026-05-31 partially exercised the backend/API path, and Round 2 live UAT on 2026-06-01 found additional rebuild-sensitive fixes. Browser UI UAT still needs rerun after rebuilding every changed service image.

## Automated Checks

- Contract verifier: passed.
- Backend Maven suite: passed.
- Frontend syntax sweep: passed for 29 JavaScript files.
- Direct `fetch` gate: passed; only `frontend/js/core/api-client.js` uses `fetch`.
- Frontend Python/deferred-endpoint gate: passed; no Python direct calls or deferred citation-detail endpoints.
- Permission-code generator check: passed.
- No Redis/Mongo/shared-cache runtime-code/config scan: passed.

## Requirement Status

| Requirement | Status | Evidence |
|-------------|--------|----------|
| CHAT-01 | pass | Backend persistence/conversation tests passed; API lifecycle passed in live UAT on 2026-05-31. |
| CHAT-02 | partial | Backend query/orchestration/rate-limit tests passed; live outcomes were observed, but Java ANSWERED was blocked before the `JAVA_AI_BASE_URL` fix. |
| UI-01 | blocked | Frontend session shell/static checks passed; browser session UAT was blocked by stale frontend image content. |
| UI-02 | blocked | Source modal/static checks passed; browser source-modal UAT was blocked by stale frontend image content. |
| UI-03 | blocked | Admin screens/static/backend endpoint checks passed; browser full/partial admin UAT was blocked by stale frontend image content. |

## Human Verification Items

1. Run browser session UAT for `/me`, login, forced password change, refresh, logout, access denied, and service-unavailable behavior.
2. Rebuild/restart `java-backend` and `frontend`; rebuild/restart `python-ai` whenever `ai-service` changed. Do not rely on static `phase1` tags as freshness signals; check image `CREATED` time.
3. Run chat UAT with a verified query-visible corpus and one untimed reranker pre-warm query before timed CHAT-02 checks. Reindex only if the retained Phase 5 corpus is missing.
4. Verify answer, no-evidence, refused, degraded, timeout/unavailable, retry-as-new-pair, history reload, soft-delete, and 429 behavior in browser/DB.
5. Verify source modal opens from returned citation quote/snippet and never displays `entity:*` graph markers.
6. Run admin UAT as full and partial admin for documents, users, roles, and access policies.
7. Collect live audit/database evidence for shared `correlation_id` and 429 audit-without-chat-row behavior, using `audit_events.occurred_at` and `documents.uploaded_at` where applicable.

## References

- Checklist: `.planning/phases/06-chat-frontend-experience/06-UAT.md`
- Evidence: `.planning/phases/06-chat-frontend-experience/06-UAT-EVIDENCE.md`
