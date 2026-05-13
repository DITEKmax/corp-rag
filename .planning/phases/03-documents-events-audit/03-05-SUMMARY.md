---
phase: 03-documents-events-audit
plan: 05
subsystem: events
tags: [rabbitmq, spring-amqp, outbox, audit, documents]

requires:
  - phase: 03-documents-events-audit
    provides: document upload/delete outbox rows
provides:
  - RabbitMQ document lifecycle topology from generated contract constants
  - Scheduled outbox publisher with persistent AMQP headers
  - Unlimited publish retries with exponential backoff capped at five minutes
  - Published outbox cleanup after seven-day retention
affects: [phase-03, phase-04, ai-service-indexing, document-events]

tech-stack:
  added: [spring-boot-starter-amqp, spring-rabbit-test]
  patterns:
    - contract-generated RabbitMQ topology
    - scheduled transactional outbox publication
    - bean-definition topology verification

key-files:
  created:
    - backend/corp-rag-app/src/main/java/com/corprag/config/AmqpConfig.java
    - backend/corp-rag-app/src/main/java/com/corprag/config/OutboxPublisherProperties.java
    - backend/corp-rag-app/src/main/java/com/corprag/adapter/amqp/AmqpHeaderNames.java
    - backend/corp-rag-app/src/main/java/com/corprag/service/outbox/EventEnvelopeFactory.java
    - backend/corp-rag-app/src/main/java/com/corprag/service/outbox/OutboxPublisher.java
    - backend/corp-rag-app/src/test/java/com/corprag/adapter/amqp/AmqpConfigTest.java
    - backend/corp-rag-app/src/test/java/com/corprag/service/outbox/OutboxPublisherTest.java
  modified:
    - backend/corp-rag-app/pom.xml
    - backend/corp-rag-app/src/main/resources/application.yml
    - backend/corp-rag-app/src/main/java/com/corprag/service/outbox/OutboxService.java
    - backend/corp-rag-app/src/test/java/com/corprag/service/outbox/OutboxServiceTest.java
    - infra/docker-compose.yml
    - .env.example

key-decisions:
  - "RabbitMQ health is opt-in outside compose so backend tests remain broker-independent; compose enables it."
  - "Outbox publishing is config-gated and enabled by compose, preventing unit tests from background-polling missing tables."
  - "Topology verification uses Spring bean-definition tests because Docker/Testcontainers is unavailable locally."

patterns-established:
  - "OutboxPublisher polls ready rows in bounded batches and records each row outcome independently."
  - "AMQP messages copy stored outbox headers and enforce persistent delivery mode at publish time."

requirements-completed: ["EVT-01", "AUD-01"]

duration: 15 min
completed: 2026-05-13
---

# Phase 03 Plan 05: Document Outbox Publisher Summary

**RabbitMQ document lifecycle publication through a scheduled transactional outbox publisher**

## Performance

- **Duration:** 15 min
- **Started:** 2026-05-13T20:22:00Z
- **Completed:** 2026-05-13T20:36:30Z
- **Tasks:** 3
- **Files modified:** 13

## Accomplishments

- Added Spring AMQP wiring for the document topic exchange, DLX, primary queues, DLQs, and generated-constant bindings.
- Added `EventEnvelopeFactory` and `OutboxPublisher` so upload/delete rows are sent with persistent delivery and correlation/event headers.
- Added retry backoff, published-row cleanup after seven days, and unit coverage for publisher success/failure/header/cleanup behavior.
- Kept RabbitMQ Testcontainers out of this plan because local Docker is unavailable; topology is verified through Spring bean definitions.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Spring AMQP dependency, configuration, and topology** - `4b2571c` (feat)
2. **Task 2: Implement scheduled outbox publisher with backoff** - `8c33aff` (feat)
3. **Task 3: Add outbox cleanup and publisher/topology verification** - `5eafa2f` (test)

**Plan metadata:** this summary commit

## Files Created/Modified

- `backend/corp-rag-app/src/main/java/com/corprag/config/AmqpConfig.java` - Declares document exchanges, queues, DLQs, and bindings from generated constants.
- `backend/corp-rag-app/src/main/java/com/corprag/config/OutboxPublisherProperties.java` - Binds publisher batch, retry, schedule, and retention settings.
- `backend/corp-rag-app/src/main/java/com/corprag/adapter/amqp/AmqpHeaderNames.java` - Centralizes AMQP header names.
- `backend/corp-rag-app/src/main/java/com/corprag/service/outbox/EventEnvelopeFactory.java` - Builds document event envelopes and headers.
- `backend/corp-rag-app/src/main/java/com/corprag/service/outbox/OutboxPublisher.java` - Polls, publishes, marks success/failure, and cleans old published rows.
- `backend/corp-rag-app/src/test/java/com/corprag/service/outbox/OutboxPublisherTest.java` - Covers success, headers, backoff, batch size, and cleanup.
- `backend/corp-rag-app/src/test/java/com/corprag/adapter/amqp/AmqpConfigTest.java` - Verifies exchange, queue, DLQ, and binding declarations.
- `backend/corp-rag-app/pom.xml` - Adds Spring AMQP runtime and Rabbit test support.
- `backend/corp-rag-app/src/main/resources/application.yml` - Adds RabbitMQ and outbox publisher configuration.
- `infra/docker-compose.yml` and `.env.example` - Add Java RabbitMQ and outbox publisher env wiring.

## Decisions Made

- Rabbit health is disabled by default and enabled by compose so ordinary backend tests do not require a live broker.
- The publisher is compose-enabled but disabled by default in non-compose runs to prevent scheduled background polling in test contexts.
- RabbitMQ topology is verified with bean-definition tests in this environment; container-level routing remains a future enhancement when Docker is available.

## Deviations from Plan

None - plan executed within the allowed fallback path for topology verification.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope creep; the RabbitMQ container test branch was not practical because Docker is unavailable.

## Issues Encountered

- Initial backend tests failed because Actuator Rabbit health attempted `localhost:5672`; fixed by making Rabbit health opt-in and enabling it in compose.
- Spring could not infer queue bean parameters without `-parameters`; fixed with explicit `@Qualifier` annotations in `AmqpConfig`.
- RabbitMQ Testcontainers was not practical because local Docker is unavailable; bean-definition topology coverage was added instead.

## Verification

- `python scripts/verify-contracts.py` via `ai-service/.venv/Scripts/python.exe` with `MAVEN_CMD=C:\dev\apache-maven-3.9.15\bin\mvn.cmd` passed.
- `C:\dev\apache-maven-3.9.15\bin\mvn.cmd -q -pl corp-rag-app -am test` passed.

## User Setup Required

None - RabbitMQ and publisher settings are covered by `.env.example` and compose defaults.

## Next Phase Readiness

Plan 03-06 can consume Python indexing result events against the generated backend queues and should reuse the same AMQP header constants, idempotency table, and correlation propagation behavior.

## Self-Check: PASSED

- All plan tasks completed.
- Required summary created.
- Requirements copied from PLAN frontmatter.
- Automated verification passed.

---
*Phase: 03-documents-events-audit*
*Completed: 2026-05-13*
