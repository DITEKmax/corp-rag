---
phase: "04-python-ingestion-indexing"
plan: "02"
subsystem: "ingestion-control-plane"
tags: ["python", "postgres", "rabbitmq", "aio-pika", "amqp", "idempotency", "failure-reporting"]

requires:
  - phase: "04-01"
    provides: "python-ai repo-root Docker codegen and generated contract preflight"
provides:
  - "AI-owned Postgres ingestion state tables for processed events, document index state, and parent chunks"
  - "Async repository primitives for terminal idempotency, state transitions, and parent chunk replacement"
  - "RabbitMQ connection, passive queue consumer, manual ACK/NACK, and result publisher foundation"
  - "Central StageFailure formatter and document.indexing.failed payload builder"
affects: ["04-03", "04-04", "04-05", "04-06", "04-07", "phase-5-retrieval"]

tech-stack:
  added: ["aio-pika>=9.6.2,<10.0.0"]
  patterns: ["terminal-after-outcome idempotency", "passive Java-owned RabbitMQ topology", "central safe failure formatting"]

key-files:
  created:
    - "ai-service/migrations/versions/0002_ingestion_state.py"
    - "ai-service/src/corp_rag_ai/domain/ingestion_state.py"
    - "ai-service/src/corp_rag_ai/domain/exceptions.py"
    - "ai-service/src/corp_rag_ai/repositories/ingestion_state.py"
    - "ai-service/src/corp_rag_ai/adapters/amqp/consumer.py"
    - "ai-service/src/corp_rag_ai/adapters/amqp/publisher.py"
    - "ai-service/tests/test_ingestion_state_repositories.py"
    - "ai-service/tests/test_amqp_consumer.py"
    - "ai-service/tests/test_amqp_publisher.py"
    - "ai-service/tests/test_stage_failure.py"
  modified:
    - "ai-service/pyproject.toml"
    - "ai-service/uv.lock"
    - "ai-service/src/corp_rag_ai/config.py"
    - "ai-service/src/corp_rag_ai/main.py"

key-decisions:
  - "AI AMQP consumers are config-gated and default-disabled until full ingestion orchestration is wired, preventing placeholder handlers from ACKing real queued documents."
  - "AMQP topology names are loaded from generated contract constants at runtime, with dependency injection in tests to keep clean source checkouts testable."
  - "StageFailure exposes only safe template variables such as exception class names, MIME type, parser name, and bounded dependency summaries."

patterns-established:
  - "Repositories own SQLAlchemy Core statements while transaction boundaries remain with the caller."
  - "ManualAckConsumer ACKs only after the handler returns and NACKs with requeue for pre-terminal infrastructure failures."
  - "Failed event payload construction is centralized before AMQP publishing."

requirements-completed: ["ING-01", "ING-07"]

duration: "12 min"
completed: 2026-05-17
---

# Phase 04 Plan 02: AI Ingestion State, AMQP Foundation, and Failure Reporting Summary

**AI-owned ingestion state, passive RabbitMQ adapters, and centralized safe indexing-failure payloads**

## Performance

- **Duration:** 12 min
- **Started:** 2026-05-17T18:05:19+03:00
- **Completed:** 2026-05-17T18:17:31+03:00
- **Tasks:** 3
- **Files modified:** 23

## Accomplishments

- Added Alembic migration `0002_ingestion_state` for `processed_events`, `document_index_state`, and `document_chunks_parent`.
- Implemented async repository primitives for duplicate checks, terminal inserts, state upserts, failed/deleted transitions, and parent chunk replacement.
- Added `aio-pika` and RabbitMQ adapters for robust connection setup, passive queue declarations, manual ACK/NACK consumption, idempotent duplicate short-circuiting, and result publishing.
- Added centralized `StageFailure` formatting and failed-event payload construction with safe message templates and `retryCount=0` default.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add AI ingestion state migrations and repositories** - `406a464` (feat)
2. **Task 2: Add AMQP consumer/publisher foundation with manual ACK** - `8f2516a` (feat)
3. **Task 3: Implement StageFailure and failed-event message formatting** - `99dec93` (feat)

## Files Created/Modified

- `ai-service/migrations/versions/0002_ingestion_state.py` - AI Postgres ingestion state schema.
- `ai-service/src/corp_rag_ai/repositories/ingestion_state.py` - Processed-event, document-state, and parent-chunk repositories.
- `ai-service/src/corp_rag_ai/adapters/amqp/consumer.py` - Passive queue consumption and manual ACK/NACK dispatch.
- `ai-service/src/corp_rag_ai/adapters/amqp/publisher.py` - `document.indexed` and `document.indexing.failed` AMQP publishing.
- `ai-service/src/corp_rag_ai/domain/exceptions.py` - Safe stage-aware failure formatting.
- `ai-service/tests/` - Repository, AMQP, and failure-formatting coverage.

## Decisions Made

- AMQP consumers stay disabled by default through `AI_AMQP_CONSUMERS_ENABLED=false`; later orchestration will enable real upload/delete handlers.
- Generated topology constants are loaded lazily so app import and tests do not require generated files unless AMQP runtime is constructed normally.
- Failure events use centralized message templates; exception instances render as class names only.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

- `uv` cache access needed approved execution outside the sandbox for dependency update and contract verification; after approval, `aio-pika` install and contract verification passed.

## Verification

- `uv run alembic upgrade head` - passed.
- `uv run pytest tests` - 20 passed.
- `uv run python ../scripts/verify-contracts.py` with Maven command configured - passed; contract YAML unchanged.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `04-03-PLAN.md`: parser work can rely on durable AI state, idempotent AMQP intake primitives, and safe failed-event payload construction.

---
*Phase: 04-python-ingestion-indexing*
*Completed: 2026-05-17*
