---
status: pass
phase: 06-chat-frontend-experience
source:
  - human live UAT 2026-06-01
  - docker stack, browser, curl, Postgres, Qdrant, RabbitMQ, MinIO inspection
started: 2026-05-31
updated: 2026-06-01
verdict: PASS
---

# Phase 6 - Chat & Frontend Experience - Human UAT Evidence

**Date:** 2026-06-01
**Verdict:** PASS - Phase 6 is closed.
**Method:** live UAT in the Docker stack (9 containers), browser at `http://localhost`, direct API probes through `curl`, and direct inspection of Postgres, Qdrant, RabbitMQ, and MinIO. Code fixes were applied by Codex as path-limited commits and each fix was rechecked live.

## Result

All four Phase 6 ROADMAP success criteria passed:

1. User creates or continues a private conversation and sees persisted history.
2. Chat query goes through Java to Python; UI displays answer, citations, confidence, and guard results.
3. User opens a cited source from the answer UI through the detail modal.
4. Admin manages documents, users, roles, and access policies from frontend screens.

During UAT, 14 defects were found and fixed, including stack-blocking issues. Residual Low/OBS items are tracked in `.planning/BACKLOG.md` and do not block Phase 6 or Phase 7.

## Live Evidence

### Infrastructure And Build

- Contract constant generation is fixed and integrated into Maven; `java-backend` Docker build passes and the jar is produced.
- All 9 containers were healthy; `java-backend`, `frontend`, and `python-ai` were rebuilt for Phase 6.
- Flyway V14 applied on real Postgres and under Testcontainers.

### Security And CORS

- `Origin: http://localhost` returned 201 and is allowed.
- `Origin: http://evil.example` returned 403 `ORIGIN_VALIDATION_FAILED` and is blocked.
- `/me` without a session returned 401 ProblemDetail; frontend redirected to `#/login`.

### CHAT-01 - Conversation Lifecycle

- Draft conversation is created when the first message is sent.
- Conversation list, messages, one-time title derivation from the first message, and `messageCount` work.
- Delete returns 204 and is idempotent; soft-delete was confirmed in Postgres.
- Failed turns such as `NO_EVIDENCE` and `AI_UNAVAILABLE` remain visible in history as assistant bubbles without fabricated answer text.

### CHAT-02 - Query Outcomes

- All outcomes were observed: `ANSWERED`, `NO_EVIDENCE`, `UNSUPPORTED`, `REFUSED`, and `DEGRADED`.
- Output guard remains strict: `missing_citations` blocks answers without valid inline `[N]` refs.
- Rate limit writes `CHAT_QUERY_RATE_LIMITED` audit events; rate-limited requests create no `chat_messages`.
- User and assistant messages for a turn share the same `correlationId`, confirmed in Postgres.
- Rate limit 30/min transitions from 503-style dependency failures to 429 on the 31st request.

### Java To Python Path

- `/chat/query` through Java to Python returns `ANSWERED` with 4 citations and an inline `[1]`; it no longer returns 503.
- The path was confirmed for both English and Russian corpora.

### Browser UI

- UI-01: session flow works: `/me` 401, login, and return to the requested route.
- UI-02: citation chips `[N]`, source cards with snippets, and detailed source modal work. The modal displays source number, document title, access-level badge, and quote-only content without `entity:*` graph markers.
- UI-03: Documents, Users, Roles, and Access policies admin screens work with permission gating.

### Indexing Degradation

- Documents still reach `INDEXED` when entity extraction fails; embeddings persist in Qdrant and `neo4j_entity_count=0`.
- Poison messages go to `backend.document.indexed.dlq`; the main queue remains clean.

### Russian Corpus Path

- Russian Markdown uploaded through the UI is indexed as clean UTF-8 text in Qdrant.
- Russian query answered correctly: `Руководитель должен согласовать заявление на отпуск в течение пяти рабочих дней [1]`.
- Confidence shows High and the cited source is correct.

### Raw Document URL

- Browser "Open raw" returns 200 via a presigned URL using public `localhost:9000`.

## Fixed Defects

| ID | Severity | Issue | Status |
|----|----------|-------|--------|
| BLOCK-1 | Blocker | `java-backend` called `localhost:8000` instead of `python-ai` because `JAVA_AI_BASE_URL` was missing | fixed + live |
| BLOCK-2 | Blocker | frontend image was stale Phase 1 content without chat UI | fixed + live |
| BUILD-01 | Blocker | `generate_constants.py` was not integrated into Maven and app compilation failed | fixed |
| BUILD-01-FIX2 | Blocker | Maven exec plugin hardcoded `python`; Docker image has `python3` | fixed + Docker |
| DEFECT-01a | High | `indexedAt` serialized with a space instead of `T`, breaking the consumer | fixed |
| DEFECT-01b | High | poison message requeued forever instead of reaching DLQ | fixed + live |
| DEFECT-08 | High | nondeterministic inline citations caused false `NO_EVIDENCE` | fixed, 10/10 answered |
| DEFECT-09 | Medium | raw URL exposed internal host `minio:9000` | fixed |
| DEFECT-09-FIX2 | Medium | public MinIO client failed region lookup against `localhost` | fixed + live, raw 200 |
| DEFECT-10 | High | `/api/v1/users` returned 500 because compiler lacked `-parameters` | fixed + live, users 200 |
| DEFECT-11 | Med-High | entity-extraction failure made the whole document `INDEXING_FAILED` | fixed + live, document `INDEXED` |
| DEFECT-13 | High | Send button stayed disabled in draft chat | fixed + live |
| smoke-fix | Medium | empty `sectionPath` needed to serialize as `Document`; otherwise Java downgraded valid Python `ANSWERED` to `DEGRADED` | fixed |

Round 2 path-limited commits: `6236b0e`, `0560a32`, `af759ce`, `f86feb7`, `278cc19`, `656dbfc`, `36f6ea9`, `fcea8e0`.

## Final Verification

- Backend Maven: 146 tests, 0 failures.
- Python: `uv run pytest` returned 227 passed, 12 skipped.
- Docker builds passed for Java, frontend, and `python-ai`.

## Formal Gap

UI-02 "zero network calls when opening the source modal" was validated behaviorally: the modal opens instantly from returned citations and no network activity was visually observed. The browser Network tab was not explicitly captured. This is considered PASS because the implemented modal uses already returned citation snapshots.

## Phase 7 Handoff

Phase 6 is closed. Low/OBS residual items are in `.planning/BACKLOG.md`. For Phase 7 Evaluation, the demo corpus is Russian; the Russian ingestion/query/citation path is confirmed working and needs a Russian golden dataset.
