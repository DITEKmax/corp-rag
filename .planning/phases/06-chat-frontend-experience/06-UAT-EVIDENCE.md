# Phase 6 UAT Evidence

Execution dates: 2026-05-27 automated baseline; 2026-05-31 live browser/API UAT update; 2026-06-01 final live UAT.

Final verdict: PASS. Phase 6 is closed by human live UAT in the Docker stack, browser, direct API probes, and storage/queue inspection.

## Final Automated And Build Evidence

| Check | Result |
|-------|--------|
| Backend Maven suite | PASS: 146 tests, 0 failures |
| Python tests | PASS: `uv run pytest`, 227 passed, 12 skipped |
| Java Docker build | PASS |
| Frontend Docker build | PASS |
| Python AI Docker build | PASS |
| Maven contract constant generation | PASS; integrated into `generate-sources` and Docker-compatible with `python3` |
| Flyway V14 | PASS on Testcontainers and live Postgres |
| Docker stack health | PASS: 9 containers healthy |

Earlier Phase 6 static checks also passed: contract verifier, frontend JS syntax sweep, direct fetch boundary, permission-code generation, no frontend direct Python calls, and no Redis/Mongo/shared-cache runtime additions.

## Success Criteria Evidence

| ROADMAP criterion | Evidence | Status |
|-------------------|----------|--------|
| User can create or continue a private conversation and see persisted history | Draft send creates conversation; list/messages/title derivation/messageCount work; idempotent delete and soft-delete confirmed; failed turns remain visible without fabricated content | PASS |
| Chat query calls Python through Java and displays answer, citations, confidence, and guard results | `/chat/query` through Java to Python returns `ANSWERED` with citations; all outcomes observed: `ANSWERED`, `NO_EVIDENCE`, `UNSUPPORTED`, `REFUSED`, `DEGRADED`; UI renders answer, citations, confidence, and guard outcomes | PASS |
| User can open a cited source from the answer UI | Citation chips/cards open the quote-only source detail modal with source number, title, access badge, and document text; no `entity:*` marker leakage | PASS |
| Admin can manage documents, users, roles, and access policies from frontend screens | Browser UAT covered Documents, Users, Roles, Access policies, and permission gating | PASS |

## Requirement Evidence Map

| Requirement | Final evidence | Status |
|-------------|----------------|--------|
| CHAT-01 | API lifecycle and browser chat lifecycle passed; persisted history and soft-delete verified in Postgres | PASS |
| CHAT-02 | Java-to-Python query passed for English and Russian corpus; audit/rate-limit/correlation semantics verified | PASS |
| UI-01 | `/me` 401 leads to login, authenticated return to requested route works | PASS |
| UI-02 | Chat UI, citation chips, source cards, and source modal passed | PASS |
| UI-03 | Admin screens for documents, users, roles, and access policies passed | PASS |

## Security And Audit Evidence

- `Origin: http://localhost` is allowed.
- `Origin: http://evil.example` is rejected with 403 `ORIGIN_VALIDATION_FAILED`.
- `/me` without a session returns 401 ProblemDetail and frontend redirects to `#/login`.
- Rate limit writes `CHAT_QUERY_RATE_LIMITED` audit events.
- Rate-limited requests create no `chat_messages`.
- User and assistant messages for the same turn share one `correlationId`.
- The audit timestamp column is `audit_events.occurred_at`.

## Query And Guard Evidence

- `ANSWERED`, `NO_EVIDENCE`, `UNSUPPORTED`, `REFUSED`, and `DEGRADED` outcomes were observed.
- Output guard remains strict and blocks missing inline citations.
- The 30/minute limiter returns 429 on the 31st request.
- The final smoke fix ensures empty `sectionPath` serializes as `Document` so Java no longer downgrades valid Python `ANSWERED` results to `DEGRADED`.

## Russian Path Evidence

- Russian UTF-8 Markdown uploaded through the UI indexed successfully.
- Qdrant stores readable Russian text.
- Russian query returned: `Руководитель должен согласовать заявление на отпуск в течение пяти рабочих дней [1]`.
- Confidence was High and the citation source was correct.

## Indexing And Raw Source Evidence

- Documents still reach `INDEXED` when entity extraction fails; Qdrant embeddings are saved and `neo4j_entity_count=0`.
- Poison message reaches `backend.document.indexed.dlq`; main queue stays clean.
- Browser raw source opens through a presigned public `localhost:9000` URL and returns 200.

## Fixed Defects During UAT

| ID | Severity | Issue | Status |
|----|----------|-------|--------|
| BLOCK-1 | Blocker | Java called `localhost:8000` instead of `python-ai` | fixed + live |
| BLOCK-2 | Blocker | frontend image was stale Phase 1 content | fixed + live |
| BUILD-01 | Blocker | constants generation was not in Maven | fixed |
| BUILD-01-FIX2 | Blocker | Docker Maven generation needed `python3` | fixed + Docker |
| DEFECT-01a | High | `indexedAt` timestamp format broke consumer | fixed |
| DEFECT-01b | High | poison message requeued forever | fixed + live |
| DEFECT-08 | High | inline citation nondeterminism caused false `NO_EVIDENCE` | fixed |
| DEFECT-09 | Medium | raw URL used internal `minio:9000` host | fixed |
| DEFECT-09-FIX2 | Medium | public MinIO client failed region lookup | fixed + live |
| DEFECT-10 | High | `/api/v1/users` 500 without Java `-parameters` | fixed + live |
| DEFECT-11 | Med-High | entity extraction failure failed whole document | fixed + live |
| DEFECT-13 | High | draft chat Send button stayed disabled | fixed + live |
| smoke-fix | Medium | empty `sectionPath` downgraded valid answers | fixed |

Round 2 path-limited commits: `6236b0e`, `0560a32`, `af759ce`, `f86feb7`, `278cc19`, `656dbfc`, `36f6ea9`, `fcea8e0`.

## Residual Items

Residual Low/OBS items are tracked in `.planning/BACKLOG.md`:

- BL-UAT-01: raw viewing of Russian text needs explicit UTF-8 charset.
- BL-UAT-02: verify whether user messages render visibly in the chat thread.
- BL-UAT-03: monitor occasional first-turn `Response unavailable`.
- BL-UAT-04: improve document title extraction from YAML/content.
- OBS: HATEOAS null metadata, Qdrant version mismatch, favicon, AMQP channel warning, reranker memory headroom, and `ai-service` Dockerfile production-like cleanup.

## Phase 7 Handoff

Phase 7 can start. The demo corpus path is Russian, so Phase 7 golden data should be Russian-first. Russian upload, indexing, answer synthesis, inline citations, and source display are confirmed working.
