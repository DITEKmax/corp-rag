# Phase 6: Chat & Frontend Experience - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 6 delivers the browser-facing MVP experience and the missing Java chat layer behind it. Users can log in, satisfy forced password-change flows, use a vanilla frontend chat UI, create and continue persisted conversations, receive cited answers through Java-to-Python query orchestration, open quote-based citation sources, and use compact admin screens for documents, users, roles, and access policies.

The browser continues to talk only to Java. Python remains internal and is called only by Java.

</domain>

<decisions>
## Implementation Decisions

### Scope, Storage, And Service Boundary
- **D-223:** Phase 6 builds the Java chat layer from scratch. There is currently no `ChatController`, no `service/chat` package, and no conversations/messages schema.
- **D-224:** Browser requests go only to Java `:8080` / `/api/v1`. The frontend must never call Python directly.
- **D-225:** Chat storage is PostgreSQL only, in Java-owned `corp_rag_java` through Flyway migrations. Do not introduce MongoDB, Redis, a shared cache, or any non-relational chat datastore in Phase 6.
- **D-226:** JSONB columns on Java chat message rows provide the required document-shaped flexibility for `citations` and `retrieval_meta`. Do not add a separate citation datastore or table in Phase 6.
- **D-227:** Existing RAG infrastructure stores, including Qdrant, Neo4j, and MinIO, remain Python/RAG-pipeline infrastructure. Phase 6 chat persistence does not expand or repurpose them.

### Conversation Lifecycle
- **D-228:** `conversationId` is required on both frontend `POST /chat/query` and Python `QueryRequest`. There is no implicit-create-on-first-message inside `/chat/query`.
- **D-229:** The frontend uses lazy create: on the first user message, call `POST /chat/conversations`, then call `POST /chat/query` with the returned `conversationId`.
- **D-230:** Java derives the conversation title from the first user message. No rename endpoint is added in Phase 6 and titles remain immutable after derivation.
- **D-231:** If standalone `POST /chat/conversations` is used without a title before any message exists, use a safe default placeholder such as `Новый диалог`, then replace it once with the first user-message-derived title. Planning must verify this against the final contract shape.
- **D-232:** `DELETE /chat/conversations/{conversationId}` is implemented and returns `204`.
- **D-233:** Conversation delete is a soft delete: set `deleted_at` on `chat_conversations` and explicitly set `deleted_at` on child `chat_messages`, or enforce equivalent parent filtering. Do not hard-delete chat rows because audit and correlation trails reference them.
- **D-234:** Deleted conversations disappear from `listConversations`; `getConversation` and `listMessages` return `404`; repeated DELETE is idempotent and returns `204`.
- **D-235:** Phase 6 has no restore/recovery UI and no hidden-vs-deleted distinction.
- **D-236:** `listConversations` returns non-deleted conversations sorted by `updated_at DESC` in SQL, using existing `PageQuery` / `SizeQuery` pagination.
- **D-237:** `updated_at` is bumped on any persisted chat activity, including `REFUSED_GUARD`, `NO_EVIDENCE`, `DEGRADED`, `TIMEOUT`, and `AI_UNAVAILABLE`. A rate-limit `429` does not bump `updated_at` because it is not persisted.
- **D-238:** Conversation list rows expose title, updatedAt, and messageCount only. Do not add a last-outcome/status badge in Phase 6.

### Message Persistence And Status
- **D-239:** Every processed query persists exactly one user row and one paired assistant-outcome row in one transaction after the final outcome is known.
- **D-240:** Assistant status values are `ANSWERED`, `REFUSED_GUARD`, `NO_EVIDENCE`, `DEGRADED`, `TIMEOUT`, and `AI_UNAVAILABLE`.
- **D-241:** Rate-limit `429` is rejected before input guard, Python calls, and DB writes. It creates no chat rows.
- **D-242:** Semantic outcomes such as `REFUSED_GUARD`, `NO_EVIDENCE`, and `DEGRADED` are persisted as assistant rows. Infra failures such as `TIMEOUT` and `AI_UNAVAILABLE` are also persisted as assistant rows so the history remains paired and visible.
- **D-243:** Refused and failed turns remain visible in `listMessages`. They are intentional safety/debug evidence, not noise to hide.
- **D-244:** Python `conversationHistory` includes only clean answered turns and excludes every non-`ANSWERED` assistant row.
- **D-245:** Java loads the last N=10 eligible answered turns for Python history.
- **D-246:** A manual UI retry resubmits the same text with the same `conversationId` through `POST /chat/query`, producing a fresh user+assistant pair with a new `correlationId`. Original failed/degraded pairs are preserved unchanged.
- **D-247:** Retry buttons appear only for `DEGRADED`, `TIMEOUT`, and `AI_UNAVAILABLE`. Do not show retry for `REFUSED_GUARD` or `NO_EVIDENCE`.
- **D-248:** BL-02 auto-retry for missing citations is internal to one `/chat/query` request on the Java side. It may make one extra Python call before persistence; the outside world sees one final persisted pair.

### Chat Schema Shape
- **D-249:** Use a single `chat_messages` table, not split user/assistant message tables. Ordered history is read from one `(conversation_id, created_at)` stream.
- **D-250:** Do not add `pair_id` / thread fields in Phase 6. Pairing is represented by adjacent rows sharing `conversation_id` and `correlation_id` from the same request.
- **D-251:** Proposed `chat_conversations` fields: `id uuid primary key`, `user_id uuid not null`, `title varchar(200) not null`, `created_at timestamptz not null`, `updated_at timestamptz not null`, `deleted_at timestamptz null`.
- **D-252:** Proposed `chat_conversations` index: `(user_id, deleted_at, updated_at desc)`.
- **D-253:** Proposed `chat_messages` fields: `id uuid primary key`, `conversation_id uuid not null`, `role varchar(16) not null`, `status varchar(32) null`, `content text null`, `citations jsonb null`, `retrieval_meta jsonb null`, `confidence numeric(4,3) null`, `correlation_id uuid not null`, `created_at timestamptz not null`, `deleted_at timestamptz null`.
- **D-254:** `status` constraints must enforce: `(role='USER' and status is null)` or `(role='ASSISTANT' and status in ('ANSWERED','REFUSED_GUARD','NO_EVIDENCE','DEGRADED','TIMEOUT','AI_UNAVAILABLE'))`.
- **D-255:** `content` is nullable because non-`ANSWERED` assistant rows may intentionally have no answer text. Do not force placeholder answer text.
- **D-256:** `citations` is non-null only for `ASSISTANT` / `ANSWERED` rows with returned citations. It is null for user rows and non-answered assistant outcomes.
- **D-257:** `retrieval_meta` is nullable and stored for assistant rows whenever Python returned it, including `NO_EVIDENCE` and `DEGRADED`. It may be null for `TIMEOUT`, `AI_UNAVAILABLE`, and early `REFUSED_GUARD`.
- **D-258:** `correlation_id` is non-null and shared by the user row and assistant row written for one processed request. Manual retry gets a new `correlation_id`.
- **D-259:** Proposed `chat_messages` indexes: `(conversation_id, deleted_at, created_at asc)` and `(correlation_id)`.
- **D-260:** Planning must verify the exact FK target names and table naming convention against existing Phase 2/3 migrations before finalizing the Flyway script.

### Rate Limiting
- **D-261:** Implement `POST /chat/query` rate limiting in-memory per Java instance, per authenticated `userId`, at 30 requests/minute.
- **D-262:** Count rate-limit attempts before input guard, Python call, and any DB write.
- **D-263:** Limit only `POST /chat/query`. Other chat endpoints are not rate-limited in Phase 6 unless an existing framework already applies global limits.
- **D-264:** Use a thread-safe limiter. Token bucket is preferred, but sliding vs fixed window is a plan-level detail.
- **D-265:** Expire stale limiter entries lazily or periodically so inactive users do not accumulate counters forever.
- **D-266:** The in-memory limiter is an honest single-instance MVP limitation. Do not introduce Redis or Postgres-backed rate limiting in Phase 6.
- **D-267:** Rate-limit failures return RFC7807 `application/problem+json` with status `429`, the existing project ProblemDetails field names/style, a reason value such as `RATE_LIMIT_EXCEEDED`, a correlationId, and a `Retry-After` header.
- **D-268:** A rate-limit `429` emits a light audit event but does not create chat rows and does not update conversation activity.

### Query Orchestration And Audit
- **D-269:** Java is the browser-facing authority for auth, access-filter resolution, rate limiting, chat persistence, and query audit.
- **D-270:** Java calls Python synchronously with resolved access filter, `conversationId`, the user message, and up to 10 eligible answered history turns.
- **D-271:** Planning must define concrete Java audit rows for `/chat/query` outcomes, tied to `correlationId`, including successful answer, guard refusal, no evidence, degraded, timeout/unavailable, and 429.
- **D-272:** Query audit rows are separate from chat history rows. Chat history is user-visible; audit is traceability evidence.

### Citation And Source Viewer
- **D-273:** Phase 6 source viewing is an MVP quote/snippet modal rendered entirely from returned `Citation` fields: `documentTitle`, `sectionPath`, `quote`, `snippet`, `pageNumber`, and `accessLevel`.
- **D-274:** `Citation.quote` is required and already contains real document text after Phase 5.1 DEF-A. The modal shows `quote`; citation chips use shorter `snippet` previews.
- **D-275:** Do not wire Python chunk detail service, do not add a Java chunk proxy, and do not implement `/chat/messages/{messageId}/citations` in Phase 6.
- **D-276:** Fix the `api-v1.yaml` source-viewer description bug: it references Python `GET /chunks/{chunkId}`, but the real Python path is `GET /v1/documents/{documentId}/chunks/{chunkId}`. Mark `getCitationDetails` deferred/not implemented for Phase 6.
- **D-277:** Source viewer must display document text only. It must never show `entity:X` or graph marker strings.
- **D-278:** For every inline `[N]`, Phase 6 can resolve citation chips directly through `citations[N-1]`.
- **D-279:** BL-02 `missing_citations` after internal auto-retry surfaces as `DEGRADED`: a compact retry-focused bubble with no answer text and no citation chips.
- **D-280:** Do not weaken the output guard to show BL-02 text. The fix is Python synthesis prompt hardening only.
- **D-281:** Persist citation snapshots as JSONB exactly as returned in `ChatQueryResponse`. This preserves history after document delete or reindex.
- **D-282:** Citation snapshot accessLevel is point-in-time display data, not future access authority. Any future full-content viewer must re-check access live in Java.
- **D-283:** Add nullable `retrievalMeta` to the OpenAPI `Message` schema, reusing the existing `RetrievalMeta` schema. Regenerate Java DTOs and run contract verification.
- **D-284:** Frontend displays confidence as a qualitative label, not a raw number, because confidence remains unstable.
- **D-285:** Retrieval diagnostics are hidden behind a collapsed diagnostics block and use the same `retrievalMeta` shape for fresh responses and history.

### Admin Experience
- **D-286:** Admin UI is compact operational coverage across all four required resources: documents, users, roles, and access policies.
- **D-287:** Admin screens are frontend-only over already implemented Java endpoints from Phases 2/3. Do not add new admin backend silently; if a screen needs a missing endpoint, flag it in the plan.
- **D-288:** Permission-gated admin navigation and screens are mandatory. Use permissions, not an `isAdmin` boolean.
- **D-289:** Admin routes are separate guarded hash routes: `#/admin/documents`, `#/admin/users`, `#/admin/roles`, and `#/admin/access-policies`.
- **D-290:** Use one shared admin layout with side nav and content slot. User-role assignment lives inside `#/admin/users`; do not create `#/admin/user-roles`.
- **D-291:** Direct navigation to a forbidden admin route shows access denied, not an empty screen.
- **D-292:** Documents admin includes list, upload, delete, indexing/failure status, and raw open link using existing Phase 3 endpoints.
- **D-293:** Raw document links are presigned URLs fetched on click through Java. Do not cache or guess presigned URLs in the frontend.
- **D-294:** Frontend does not duplicate document access logic. Java decides visibility and returns success, 403, or 404.
- **D-295:** Duplicate document upload responses with `details.existingDocumentId` should show a clear "already uploaded" message.
- **D-296:** Users and roles use tables plus focused drawers/forms, not full detail routes.
- **D-297:** Users UI supports list, create, disable, reset password, and role assignment/removal. Role assignment uses `UserRoleController`, not a merged user update.
- **D-298:** Roles UI supports list, create, and edit permission sets. Permission codes must come from backend/contract data, not free text or a hardcoded frontend-only list.
- **D-299:** Destructive or sensitive actions, including document delete, user disable, and password reset, require confirmation.
- **D-300:** Planning must verify server-side self-lockout protection for disabling self or removing one's own last role/permission. If absent, flag it as a backend gap; frontend warnings are not the guarantee.

### Frontend App Shell, Session, And Routing
- **D-301:** Frontend remains vanilla HTML/CSS/JavaScript with BEM, no framework, no Tailwind, no utility CSS framework.
- **D-302:** Build a custom hash router, API client, session-state module, and BEM components. Reuse existing design tokens in `frontend/styles/base.css`.
- **D-303:** Use session-first bootstrap. On page load, call `GET /api/v1/me` once before rendering protected route content.
- **D-304:** Bootstrap routing: 401/no session -> `#/login`; `mustChangePassword=true` -> `#/change-password` and block the rest of the app; valid session -> store user+permissions in memory and resolve current hash route through the guard.
- **D-305:** If bootstrap `/me` fails with 5xx, show a service-unavailable screen with retry. Do not eject a potentially logged-in user to login.
- **D-306:** Store user and permissions in memory only. On reload, fetch `/me` again.
- **D-307:** Honor forced password change both proactively from `/me.mustChangePassword` and reactively if any request is rejected by `MustChangePasswordFilter`.
- **D-308:** `#/login` and `#/change-password` are the only routes reachable without a normal passed guard.
- **D-309:** API client refreshes once on protected-call 401, then retries the original request once.
- **D-310:** Refresh must be single-flight because backend refresh tokens rotate by family. Exactly one refresh request may be in flight; concurrent 401s await the same shared refresh promise.
- **D-311:** If refresh fails, or the retried request returns 401 again, clear in-memory session and route to login with return route.
- **D-312:** Exclude login, change-password, bootstrap `/me`, and `/auth/refresh` from the refresh-on-401 interceptor.
- **D-313:** Do not use timer-based refresh. The access token is httpOnly and frontend cannot read its expiry safely.
- **D-314:** All Java API calls go through one API client. Direct `fetch` calls in feature modules are forbidden.
- **D-315:** The API client owns `credentials: "include"`, `/api/v1` base URL, JSON body headers, refresh, and unified error mapping.
- **D-316:** Do not manually set the `Origin` header in fetch. Browsers forbid that header and set it themselves.
- **D-317:** Planning must verify whether Java protection is Origin/Referer-only or uses a double-submit CSRF token. If a token exists, plan the frontend read/echo path explicitly.
- **D-318:** Use one declarative route table as the source of truth for router guards and navigation. Each route has `path`, `render`, `access`, and `nav` metadata.
- **D-319:** Route `access` values are `public`, `authed`, or a concrete permission code. `#/change-password` has a distinct `allowDuringMustChange` flag.
- **D-320:** Navigation is built from the route table and filtered by in-memory permissions. Unknown hashes render a not-found entry from the same router system.

### Verification Flags For Planning
- **D-321:** Verify exact Java CSRF/CORS mechanism and accepted frontend origins before implementing the API client assumptions.
- **D-322:** Verify FK target names, Java schema/table naming conventions, and whether `chat_` prefix matches existing Flyway style.
- **D-323:** Verify server-side self-lockout enforcement. If absent, plan a backend gap fix or explicitly surface the gap.
- **D-324:** Verify existing ProblemDetails field names and error/reason conventions before adding `RATE_LIMIT_EXCEEDED`.
- **D-325:** Verify whether existing admin endpoints expose permission-code metadata suitable for role editing. If not, flag the missing source of truth.

### Do-Not-Break Gates
- **D-326:** Keep the Python output guard strict. Do not weaken citation validation to make UI probes pass.
- **D-327:** BL-02 single-citation `missing_citations` must surface as a graceful degraded/retry state, not as an empty bubble.
- **D-328:** Source viewer must show document text and never `entity:X` markers.
- **D-329:** Frontend must not call Python directly, including for source viewing.
- **D-330:** Do not introduce Redis, a shared cache, MongoDB, or any new Phase 6 infrastructure.

### the agent's Discretion
- Choose exact Java package/class names for chat controllers, services, repositories, DTO assemblers, and tests if they follow existing adapter/service/domain/repository patterns.
- Choose exact frontend module names and component boundaries within the locked vanilla JS, BEM, route-table, session-state, and API-client design.
- Choose exact qualitative confidence labels and UI copy for refusal/degraded/timeout states, provided the labels do not blame the user or conflate BL-02 with guard refusal.
- Choose exact in-memory rate limiter algorithm details if the limit remains per user, thread-safe, 30/minute, pre-persistence, and documented as single-instance.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning State
- `.planning/PROJECT.md` - project value, service ownership, constraints, and frontend vanilla/no-framework requirement.
- `.planning/REQUIREMENTS.md` - Phase 6 requirements `CHAT-01`, `CHAT-02`, `UI-01`, `UI-02`, and `UI-03`.
- `.planning/ROADMAP.md` - Phase 6 goal, success criteria, dependency on Phase 5.1, and Phase 7/8 boundaries.
- `.planning/STATE.md` - current project state, Phase 5.1 handoff, and Phase 6 readiness.
- `.planning/phases/02-identity-users-access-control/02-CONTEXT.md` - auth/session, permission model, access-filter, refresh-token, and must-change-password decisions.
- `.planning/phases/03-documents-events-audit/03-CONTEXT.md` - document/admin API behavior, audit discipline, correlation, and document raw URL behavior.
- `.planning/phases/05-retrieval-guards-query-api/05-CONTEXT.md` - Java/Python query boundary, citation contract, retrieval metadata, guard behavior, and Phase 6 handoff.
- `.planning/phases/05.1-phase-5-uat-fix-wave/05.1-CONTEXT.md` - BL-02/DEF-A citation fixes, reranker degradation, graph quote safety, and Phase 6 source-viewer constraints.

### Contracts
- `contracts/openapi/api-v1.yaml` - frontend-facing Java API; update chat/message schema, `Message.retrievalMeta`, deferred citation-details text, and any rate-limit ProblemDetails contract changes here first.
- `contracts/openapi/ai-service-v1.yaml` - internal Python query contract, including required `conversationId`, `QueryRequest`, `QueryResponse`, citations, guard verdict, and retrieval metadata.
- `contracts/constants.yaml` - shared constants and existing error/reason code conventions.

### Architecture And ADRs
- `docs/ARCHITECTURE.md` - Java/Python/frontend responsibilities, vanilla frontend architecture, implemented Phase 5 query flow, and Phase 6 boundary.
- `docs/PATTERNS.md` - contract-first, adapter/service layering, DTO separation, transport-thin logic, and testability patterns.
- `docs/decisions/ADR-003-java-python-split.md` - Java as browser-facing authority and Python as internal AI service.
- `docs/decisions/ADR-006-degraded-mode-policy.md` - explicit degraded behavior and fail-loud expectations.
- `docs/decisions/ADR-007-citation-contract-and-refusal-rules.md` - citation/refusal contract and output-guard safety expectations.
- `docs/decisions/ADR-008-guard-architecture.md` - guard architecture and guard/refusal semantics.

### Existing Frontend
- `frontend/index.html` - current static shell to replace with the real app entry.
- `frontend/styles/base.css` - existing design tokens and simple BEM-compatible styling baseline to reuse.
- `frontend/README.md` - target vanilla frontend folder structure and no-framework/no-Tailwind constraints.
- `frontend/nginx.conf` - static serving/proxy context to verify with Java origin/CORS behavior.

### Existing Java Integration Points
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/AuthController.java` - login, refresh, logout, `/me`, links, and must-change-password response shape.
- `backend/corp-rag-app/src/main/java/com/corprag/security/MustChangePasswordFilter.java` - reactive forced-password-change enforcement the frontend must honor.
- `backend/corp-rag-app/src/main/java/com/corprag/service/auth/RefreshTokenService.java` - refresh rotation/family semantics that require frontend single-flight refresh.
- `backend/corp-rag-app/src/main/java/com/corprag/security/OriginRefererValidationFilter.java` - verify actual CSRF/Origin behavior before frontend implementation.
- `backend/corp-rag-app/src/main/java/com/corprag/security/Permission.java` - existing permission codes for route guards and role editing.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/DocumentController.java` - document list/upload/detail/raw/delete API used by admin documents.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/UserController.java` - user list/create/update/disable/reset API used by admin users.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/UserRoleController.java` - role assignment/removal used inside the user drawer.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/RoleController.java` - role list/create/update/delete API used by admin roles.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/AccessPolicyController.java` - access-policy CRUD used by admin access policies.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/ProblemDetailsExceptionHandler.java` - existing ProblemDetails shape and error mapping to reuse for 429 and chat errors.
- `backend/corp-rag-app/src/main/java/com/corprag/service/audit/AuditEventWriter.java` - audit write path for query outcome and 429 audit events.
- `backend/corp-rag-app/src/main/resources/db/migration/` - verify existing table names, FK targets, timestamp conventions, and Flyway naming before adding chat migrations.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/styles/base.css` provides existing CSS custom properties and BEM-compatible launch-shell styles; replace/extend it instead of introducing a new design system.
- Java REST controllers already exist for auth, documents, users, roles, user-role assignment, and access policies. Admin UI should consume these endpoints rather than adding backend admin features.
- `RefreshTokenService` already implements refresh-token rotation with reuse detection; the frontend API client must prevent concurrent refresh requests.
- `OriginRefererValidationFilter` and `MustChangePasswordFilter` already enforce browser-facing safety flows that the frontend must respect.
- `AuditEventWriter` is the likely integration point for query audit and rate-limit audit rows.

### Established Patterns
- Contract-first changes go through `contracts/openapi/api-v1.yaml` and generated DTOs before implementation.
- Java transport classes should stay thin; orchestration and persistence belong in services/repositories.
- PostgreSQL/Flyway owns Java service state. New chat schema belongs in Java migrations, not Python storage.
- Frontend remains static/vanilla and nginx-served, with hash routing and ES modules rather than a framework build.
- Existing Java security is permission-code based. Route guards and nav visibility should use permissions, not roles.

### Integration Points
- Add Java chat contracts, schema, repositories, services, rate limiter, audit integration, Python client/orchestrator, and REST controller under existing Java backend patterns.
- Extend frontend from the static shell into modules for API client, session state, router, chat page, source modal, admin layout/pages, and shared BEM components.
- Extend OpenAPI `Message` with nullable `retrievalMeta`, fix/defer `getCitationDetails`, and align chat persistence fields with response DTOs.
- Verify `frontend/nginx.conf` / Java CORS-Origin behavior in local compose and direct `:8080` development.

</code_context>

<specifics>
## Specific Ideas

- MVP source modal uses returned `quote` as the full visible body and `snippet` only for the citation chip preview.
- BL-02 degraded UI copy should avoid blaming the user or saying "unsafe"; frame it as failure to format with proper source references and offer retry.
- Chat retry produces a duplicate user text in history by design; this is honest evidence of repeated attempts.
- Admin uses separate guarded routes with one shared layout, not tabs and not a dashboard.
- Drawers are preferred over modals for user-role assignment and role permission editing because those forms are too complex for small dialogs.
- The route registry is the single source of truth for routing, guards, and navigation.

</specifics>

<deferred>
## Deferred Ideas

- Full-content source viewer backed by Python `GET /v1/documents/{documentId}/chunks/{chunkId}`, Java proxy, and Java-side message-ownership/live-access checks.
- Implement `/chat/messages/{messageId}/citations` only when full-content source viewer is in scope.
- Distributed rate limiter via Redis or shared store when/if the Java app becomes multi-instance. This later work must decide fail-open vs fail-closed behavior when Redis is unavailable.
- RAG answer caching via Redis is deferred to Phase 7+ and must include resolved access scope in the cache key, not just message text. It also needs corpus-version invalidation on upload/delete/reindex and must account for synthesis nondeterminism and guard behavior such as BL-02.
- User-facing restore/recovery UI for soft-deleted conversations.
- Separate hidden-vs-deleted conversation behavior.
- Last-outcome/status indicator in conversation list rows.
- Admin dashboard with summaries/aggregate queries.
- Deep-linking directly to a specific admin drawer.
- Richer admin UX polish beyond compact operational forms.

</deferred>

---

*Phase: 6-Chat & Frontend Experience*
*Context gathered: 2026-05-26*
