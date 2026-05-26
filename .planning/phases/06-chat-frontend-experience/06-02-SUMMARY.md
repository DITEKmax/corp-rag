---
phase: "06-chat-frontend-experience"
plan: "02"
subsystem: "database"
tags: ["postgres", "flyway", "jdbc", "chat", "jsonb"]

requires:
  - phase: "06-chat-frontend-experience"
    provides: "Plan 01 contract status/retrievalMeta shape"
  - phase: "02-identity-users-access-control"
    provides: "users table and user ownership FK target"
provides:
  - "V14 chat_conversations and chat_messages schema"
  - "chat domain records and assistant status enum"
  - "owner-scoped JDBC repositories for conversations/messages"
  - "answered-pair history query for Python conversationHistory"
affects: ["06-03", "06-04", "06-05"]

tech-stack:
  added: []
  patterns: ["PostgreSQL JSONB snapshots via ObjectMapper and CAST(:json AS jsonb)", "owner-scoped repository methods"]

key-files:
  created:
    - "backend/corp-rag-app/src/main/resources/db/migration/V14__add_chat_conversations_messages.sql"
    - "backend/corp-rag-app/src/main/java/com/corprag/domain/chat/"
    - "backend/corp-rag-app/src/main/java/com/corprag/repository/ChatConversationRepository.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/repository/ChatMessageRepository.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/repository/ChatRepositoryPersistenceIT.java"
  modified: []

key-decisions:
  - "Highest existing Flyway migration was V13, so chat storage was added as V14__add_chat_conversations_messages.sql."
  - "Conversation owner FK targets users (id), matching existing migrations."
  - "chat_ prefix is consistent with existing snake_case Java-owned tables and keeps chat storage distinct."
  - "Python history selection returns complete ANSWERED user+assistant pairs by correlation_id, limited by pair count, never dangling filtered messages."

patterns-established:
  - "Conversation delete is repository-level soft delete on parent plus explicit child deleted_at update."
  - "Manual retry and processed query pairs share correlation_id across adjacent user/assistant rows."
  - "Message JSONB fields deserialize into typed snapshot records before service/controller mapping."

requirements-completed: ["CHAT-01", "CHAT-02"]

duration: "10 min"
completed: "2026-05-26"
---

# Phase 6 Plan 02: Java Chat Persistence Summary

**PostgreSQL chat tables and owner-scoped JDBC repositories now store paired conversation history, citation snapshots, and retrieval diagnostics.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-05-26T23:25:00+03:00
- **Completed:** 2026-05-26T23:35:40+03:00
- **Tasks:** 4
- **Files modified:** 11

## Accomplishments

- Verified existing schema conventions: `V13` was the prior highest migration, FK style uses `REFERENCES users (id)`, JSONB uses `CAST(:json AS jsonb)`, and active-row filtering uses `deleted_at IS NULL`.
- Added `chat_conversations` and `chat_messages` with locked fields, role/status/content constraints, JSONB snapshots, `correlation_id`, and required indexes.
- Added chat domain records for conversations, summaries, messages, citation snapshots, retrieval metadata, roles, and assistant statuses.
- Added `ChatConversationRepository` for create, owner-scoped get/list/count, one-time placeholder title derivation, and idempotent soft-delete with child message soft-delete.
- Added `ChatMessageRepository` for transactional user+assistant pair append, owner-scoped message listing/counting, JSONB mapping, and last-N complete ANSWERED pair history.
- Added `ChatRepositoryPersistenceIT` covering migration/FK checks, title derivation, ordering, JSON round-trip, nullable non-ANSWERED content, soft delete, correlation sharing, and answered-pair history.

## Task Commits

1. **Tasks 1-4: Schema, repositories, and invariant tests** - `38d593f` (`feat(06-02): add chat persistence foundation`)

## Files Created/Modified

- `backend/corp-rag-app/src/main/resources/db/migration/V14__add_chat_conversations_messages.sql` - Java-owned chat schema.
- `backend/corp-rag-app/src/main/java/com/corprag/domain/chat/` - Chat persistence domain records/enums.
- `backend/corp-rag-app/src/main/java/com/corprag/repository/ChatConversationRepository.java` - Conversation persistence and soft-delete behavior.
- `backend/corp-rag-app/src/main/java/com/corprag/repository/ChatMessageRepository.java` - Message pair persistence and answered-pair history selection.
- `backend/corp-rag-app/src/test/java/com/corprag/repository/ChatRepositoryPersistenceIT.java` - PostgreSQL repository invariant tests.

## Decisions Made

- Kept role values uppercase in storage (`USER`, `ASSISTANT`) to match Java enum/storage style; later REST assemblers can map to the existing lower-case API role enum.
- Enforced nullable outcome content in the database while requiring content for user rows and answered assistant rows.
- Kept citation snapshots display-only by schema: allowed only on `ASSISTANT` + `ANSWERED` rows.

## Deviations from Plan

None - plan scope was executed as written.

## Issues Encountered

- Targeted Maven test filtering needed PowerShell `--%` because dotted `-D` properties were otherwise misparsed.
- `ChatRepositoryPersistenceIT` compiled and matched the plan filter, but all five PostgreSQL Testcontainers cases skipped in this shell because Testcontainers could not find a valid Docker environment.

## Verification

- `rg -n "CREATE TABLE chat_conversations|CREATE TABLE chat_messages|chat_messages_.*status|retrieval_meta JSONB|correlation_id|updated_at DESC" backend/corp-rag-app/src/main/resources/db/migration/V14__add_chat_conversations_messages.sql`
- `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test -Dtest=*Chat*Repository* -Dsurefire.failIfNoSpecifiedTests=false` exited 0; chat IT skipped due Docker/Testcontainers unavailable.
- `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test -DskipTests=false` exited 0.

## User Setup Required

None - no external setup. To execute PostgreSQL-backed chat ITs locally, Docker/Testcontainers must be available to Maven.

## Next Phase Readiness

Ready for Plan 06-03. The query audit/rate limiter/Python client plan can use `ChatConversationRepository` and `ChatMessageRepository` without changing schema assumptions.

---
*Phase: 06-chat-frontend-experience*
*Completed: 2026-05-26*
