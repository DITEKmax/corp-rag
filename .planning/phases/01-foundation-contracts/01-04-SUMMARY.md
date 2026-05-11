---
phase: 01-foundation-contracts
plan: 04
subsystem: ai-service
tags: [python, fastapi, uv, pydantic, sqlalchemy, asyncpg, alembic, docker]

requires:
  - phase: 01-foundation-contracts
    provides: Python contract generation target from Plan 01-02.
provides:
  - Runnable FastAPI AI service application on port 8000.
  - Typed environment-backed settings for AI service dependencies.
  - Reserved Python generated-contract package namespace.
  - Alembic async migration infrastructure for the AI-owned Postgres database.
  - Empty AI database baseline revision.
  - Docker image definition for the Python AI service.
affects: [docker-compose, phase-04-python-ingestion, phase-05-retrieval, phase-07-observability]

tech-stack:
  added:
    - Python 3.12 uv project
    - FastAPI
    - Uvicorn
    - Pydantic v2
    - pydantic-settings
    - SQLAlchemy 2 async
    - asyncpg
    - Alembic
    - pytest
    - pytest-asyncio
  patterns:
    - Minimal FastAPI service skeleton
    - Environment-backed service configuration
    - Async SQLAlchemy Alembic migrations
    - Empty migration baseline

key-files:
  created:
    - ai-service/pyproject.toml
    - ai-service/Dockerfile
    - ai-service/.dockerignore
    - ai-service/alembic.ini
    - ai-service/migrations/env.py
    - ai-service/migrations/versions/0001_empty_baseline.py
    - ai-service/src/corp_rag_ai/__init__.py
    - ai-service/src/corp_rag_ai/config.py
    - ai-service/src/corp_rag_ai/main.py
    - ai-service/src/corp_rag_ai/contracts/__init__.py
  modified: []

key-decisions:
  - "The Python AI service stays Phase 1 minimal: FastAPI health/readiness only, no retrieval, embeddings, graph, guard, AMQP consumer, or business routers."
  - "Python runtime configuration uses AI_DB_URL plus service dependency env vars that Plan 01-06 can wire into compose."
  - "Alembic uses SQLAlchemy async configuration with an explicit empty baseline for corp_rag_ai."

patterns-established:
  - "Generated Python contracts live under corp_rag_ai.contracts.generated and remain ignored build artifacts."
  - "Readiness is deliberately light in Phase 1 and does not probe external services."
  - "The AI database migration history starts with a reviewable empty baseline before domain tables are introduced."

requirements-completed: [FND-01, FND-03]

duration: 9 min
completed: 2026-05-11
---

# Phase 01 Plan 04: Python FastAPI AI Service Foundation Summary

**FastAPI AI-service skeleton with uv dependency management, typed environment settings, Docker packaging, and an empty async Alembic baseline**

## Performance

- **Duration:** 9 min
- **Started:** 2026-05-11T19:23:49Z
- **Completed:** 2026-05-11T19:32:21Z
- **Tasks:** 2 completed
- **Files modified:** 10 tracked files

## Accomplishments

- Added `ai-service/pyproject.toml` as a uv-managed Python 3.12 project with FastAPI, Uvicorn, Pydantic v2, pydantic-settings, SQLAlchemy async, asyncpg, Alembic, pytest, and pytest-asyncio.
- Added a minimal FastAPI `app` exporting `/health` and `/ready` only, matching the Phase 1 no-business-behavior boundary.
- Added typed settings for the AI database, RabbitMQ, Qdrant, Neo4j, MinIO, and Langfuse environment variables without committing real secrets.
- Added Alembic async migration infrastructure and an explicit `0001_empty_baseline` revision with no domain tables.
- Added Docker packaging for running `uvicorn corp_rag_ai.main:app` on port 8000.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add uv FastAPI service skeleton** - `efaad08` (`feat(01-04): add FastAPI AI service skeleton`)
2. **Task 2: Add Alembic baseline for AI database** - `104321d` (`feat(01-04): add Alembic AI database baseline`)

**Plan metadata:** recorded in the `docs(01-04): complete Python AI service foundation plan` completion commit.

## Files Created/Modified

- `ai-service/pyproject.toml` - uv-managed Python project and dependency manifest.
- `ai-service/Dockerfile` - Python AI service container image definition.
- `ai-service/.dockerignore` - Docker build context exclusions.
- `ai-service/src/corp_rag_ai/__init__.py` - Package metadata.
- `ai-service/src/corp_rag_ai/config.py` - Typed environment-backed settings.
- `ai-service/src/corp_rag_ai/main.py` - FastAPI app with `/health` and `/ready`.
- `ai-service/src/corp_rag_ai/contracts/__init__.py` - Tracked parent package marker for ignored generated contract modules.
- `ai-service/alembic.ini` - Alembic command configuration.
- `ai-service/migrations/env.py` - Async SQLAlchemy Alembic environment using `AI_DB_URL`.
- `ai-service/migrations/versions/0001_empty_baseline.py` - Empty AI database baseline revision.

## Verification

- `cd ai-service; uv run python -c "from corp_rag_ai.main import app; print(app.title)"` - **PASS**: printed `Corp RAG AI Service`.
- `cd ai-service; uv run alembic upgrade head --sql` - **PASS**: rendered offline SQL for only `alembic_version` and `0001_empty_baseline`.
- `git check-ignore -v ai-service/src/corp_rag_ai/contracts/generated/api_v1.py` - **PASS**: generated Python contract output is ignored by `.gitignore`.
- `cd ai-service; .\.venv\Scripts\python.exe -c "import corp_rag_ai.contracts.generated.api_v1, corp_rag_ai.contracts.generated.ai_service_v1, corp_rag_ai.contracts.generated.events_v1; print('generated imports ok')"` - **PASS**: generated contract imports work with the new package layout.
- Scope scan for retrieval, embeddings, graph repositories, AMQP consumers, business routers, mutating endpoints, and domain `CREATE TABLE` statements - **PASS**: no out-of-scope Phase 1 behavior found.
- Stub scan over created/modified tracked files - **PASS**: no TODO/FIXME/placeholder UI stubs or hardcoded empty UI data paths found.

## Decisions Made

- Used `AI_DB_URL` as the Python-owned Postgres URL for both settings and Alembic so Plan 01-06 has one compose variable to wire.
- Kept `/ready` dependency-light in this phase, matching the accepted threat disposition that deep readiness belongs to later service phases.
- Added a tracked `corp_rag_ai.contracts` package marker while keeping `corp_rag_ai.contracts.generated` ignored and generated by Plan 01-02 tooling.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added generated contract parent package marker**
- **Found during:** Task 1 (Add uv FastAPI service skeleton)
- **Issue:** The plan required generated Python modules to live under `corp_rag_ai.contracts.generated`, but the ignored generated directory cannot provide a tracked parent package marker.
- **Fix:** Added `ai-service/src/corp_rag_ai/contracts/__init__.py` as a small supporting file outside the ignored generated output directory.
- **Files modified:** `ai-service/src/corp_rag_ai/contracts/__init__.py`
- **Verification:** Generated API, AI-service, and event modules imported successfully from `corp_rag_ai.contracts.generated`.
- **Committed in:** `efaad08`

---

**Total deviations:** 1 auto-fixed missing critical support file.
**Impact on plan:** The addition keeps generated outputs untracked while making the documented import path stable. No feature scope was added.

## Issues Encountered

- Sandboxed `uv run` could not open the local uv cache under `C:\Users\maksd\AppData\Local\uv\cache`. The same verification commands passed after approved local tool/cache access.

## Known Stubs

None - the empty Alembic baseline is intentional Phase 1 migration content, not an unimplemented service behavior.

## Threat Flags

None - the new settings, health/readiness routes, Docker runtime, and Alembic baseline are the planned surfaces covered by T-04-01 through T-04-03.

## Authentication Gates

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 01-06 to wire `python-ai` into Docker Compose with matching `AI_DB_URL`, service dependency variables, healthchecks, and `make migrate-python`.

## Self-Check: PASSED

- Found all 10 tracked files created for this plan.
- Found task commits `efaad08` and `104321d` in git history.
- Final FastAPI import, Alembic SQL rendering, generated-contract ignore/import, scope, and stub checks passed.
- `.planning/config.json` remained unstaged and was not modified by this plan.

---
*Phase: 01-foundation-contracts*
*Completed: 2026-05-11*
