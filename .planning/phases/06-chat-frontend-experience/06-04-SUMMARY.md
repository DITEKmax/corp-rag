---
phase: "06-chat-frontend-experience"
plan: "04"
subsystem: "java-chat-conversation-rest"
tags: ["java", "spring", "chat", "rest", "conversation-lifecycle"]

requires:
  - phase: "06-chat-frontend-experience"
    provides: "Plan 01 generated chat DTOs"
  - phase: "06-chat-frontend-experience"
    provides: "Plan 02 chat repositories and soft-delete behavior"
provides:
  - "Java chat conversation lifecycle REST endpoints"
  - "message-history REST endpoint with assistant outcome rendering"
  - "contract DTO mapper for conversations/messages/citations/retrievalMeta"
affects: ["06-05", "06-07"]

tech-stack:
  added: []
  patterns: ["owner-scoped service methods", "generated DTO mapping at service boundary", "chat.query permission on chat lifecycle endpoints"]

key-files:
  created:
    - "backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/ChatController.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatConversationService.java"
    - "backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatMessageMapper.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/ChatControllerTest.java"
    - "backend/corp-rag-app/src/test/java/com/corprag/service/chat/ChatConversationServiceTest.java"
  modified: []

key-decisions:
  - "Implemented conversation lifecycle only; `/chat/query` remains Plan 05 and getCitationDetails remains deferred."
  - "All implemented chat endpoints require the existing `chat.query` permission."
  - "Delete delegates to repository soft-delete: active or already-deleted owner rows return 204, missing/foreign rows return `CONVERSATION_NOT_FOUND`."
  - "Message history maps non-ANSWERED assistant rows with status and nullable content/citations/retrievalMeta, preserving failed/refused turns."

patterns-established:
  - "Conversation create uses the contracted request object; blank/missing title becomes the placeholder that Plan 05 may replace once from the first user message."
  - "Conversation DTO links expose self/messages/delete; message DTO links expose the parent conversation."
  - "Paged conversation/message responses use the existing page/size semantics and repository SQL ordering."

requirements-completed: ["CHAT-01"]

duration: "10 min"
completed: "2026-05-26"
---

# Phase 6 Plan 04: Chat Conversation REST Summary

**Java now exposes the chat conversation lifecycle and message-history endpoints needed by the frontend shell, without adding query orchestration or source proxy behavior.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-05-26T23:49:26+03:00
- **Completed:** 2026-05-26T23:59:51+03:00
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added `ChatController` under `/api/v1/chat` for `GET/POST /conversations`, `GET/DELETE /conversations/{conversationId}`, and `GET /conversations/{conversationId}/messages`.
- Added `ChatConversationService` for owner-scoped create/list/get/delete/listMessages, placeholder-title handling, page/size validation, and `CONVERSATION_NOT_FOUND` mapping.
- Added `ChatMessageMapper` for generated contract DTOs, including nullable message content, nullable citations, nullable retrievalMeta, assistant status, citation snapshots, and retrieval diagnostics.
- Added controller tests for missing permission, owner-scoped service calls, create `Location`, delete behavior, missing/foreign 404 mapping, visible failed assistant outcomes, and deferred citation details returning 404.
- Added service tests for placeholder creation, pagination delegation, not-found behavior, delete not-found behavior, and failed assistant rows remaining visible without fake answer text.

## Endpoint List

- `GET /api/v1/chat/conversations` - lists current user's non-deleted conversations with `updatedAt DESC` ordering supplied by repository SQL.
- `POST /api/v1/chat/conversations` - creates a current-user conversation; blank/missing title uses the approved placeholder.
- `GET /api/v1/chat/conversations/{conversationId}` - returns owner-visible active conversation or 404.
- `DELETE /api/v1/chat/conversations/{conversationId}` - soft-deletes owner conversation and returns 204; repeated owner delete is idempotent through the repository.
- `GET /api/v1/chat/conversations/{conversationId}/messages` - returns visible persisted messages, including failed/refused assistant outcomes.

## Task Commits

1. **Tasks 1-3: Service, mapper, controller, and tests** - `fae0577` (`feat(06-04): add chat conversation REST`)

## Files Created/Modified

- `backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/ChatController.java` - Java chat lifecycle controller.
- `backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatConversationService.java` - Owner-scoped lifecycle service.
- `backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatMessageMapper.java` - Contract DTO mapping.
- `backend/corp-rag-app/src/test/java/com/corprag/adapter/rest/ChatControllerTest.java` - MVC/security coverage.
- `backend/corp-rag-app/src/test/java/com/corprag/service/chat/ChatConversationServiceTest.java` - Service and mapper behavior coverage.

## Decisions Made

- Kept `/chat/messages/{messageId}/citations` unimplemented; the controller has no citation-detail mapping.
- Kept `/chat/query` unimplemented in this wave; Plan 05 will add orchestration to the existing `ChatController`.
- Accepted a provided create-conversation title per the existing contract shape, while using the placeholder for blank/missing titles so Plan 05 can perform the one allowed first-message title derivation.

## Deviations from Plan

None.

## Issues Encountered

- Full Spring context initially failed because `ChatConversationService` has a package-private test constructor as well as the production constructor. Adding `@Autowired` to the production constructor fixed bean selection.

## Verification

- `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test -Dtest=*ChatController*,*ChatConversationService* -Dsurefire.failIfNoSpecifiedTests=false` exited 0.
- `C:\dev\apache-maven-3.9.15\bin\mvn.cmd --% -q -pl corp-rag-app -am test -DskipTests=false` exited 0.
- `rg -n "/query|chat/query|getCitationDetails|/citations|PythonQueryClient|v1/query" backend/corp-rag-app/src/main/java/com/corprag/adapter/rest/ChatController.java backend/corp-rag-app/src/main/java/com/corprag/service/chat/ChatConversationService.java` returned no matches.

## User Setup Required

None.

## Next Phase Readiness

Ready for Plan 06-05. Query orchestration can add `POST /chat/query` to `ChatController` and reuse the owner-scoped service/repositories, mapper, limiter, audit helper, and Python client already in place.

---
*Phase: 06-chat-frontend-experience*
*Completed: 2026-05-26*
