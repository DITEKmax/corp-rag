---
phase: 01-foundation-contracts
verified: 2026-05-11T20:43:29Z
status: passed
score: 23/23 must-haves verified
overrides_applied: 0
---

# Phase 1: Foundation & Contracts Verification Report

**Phase Goal:** The repo has a runnable local platform and contract-first foundation for Java, Python, frontend, and message flows.
**Verified:** 2026-05-11T20:43:29Z
**Status:** passed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Developer can start the core infrastructure stack through Docker Compose. | VERIFIED | `docker compose --env-file .env.example -f infra/docker-compose.yml config --services` listed the expected services; `docker compose ... ps --format json` showed all nine Phase 1 services running and healthy. |
| 2 | Java, Python, frontend, and contract directories exist with consistent project structure. | VERIFIED | `backend/`, `ai-service/`, `frontend/`, `contracts/`, and `infra/` contain scaffolded source/build/runtime files; `rg --files` found the expected Java app, Python package, frontend shell, and contract files. |
| 3 | OpenAPI and AsyncAPI files describe the v1 REST and RabbitMQ contracts. | VERIFIED | `contracts/openapi/api-v1.yaml`, `contracts/openapi/ai-service-v1.yaml`, and `contracts/asyncapi/events-v1.yaml` define API paths, schemas, document lifecycle events, and envelope metadata. |
| 4 | Generated DTO/model code can be produced from the contracts. | VERIFIED | `python scripts/verify-contracts.py` with explicit Python and `MAVEN_CMD` passed: YAML lint, Java constants/OpenAPI generation, Java compile, Python model/constants generation, and Python smoke imports. |
| 5 | Developer can inspect one root contracts directory for every Java, Python, and RabbitMQ boundary. | VERIFIED | Only four source YAML files exist under root `contracts/`: `api-v1.yaml`, `ai-service-v1.yaml`, `events-v1.yaml`, and `constants.yaml`; no service-local YAML contract copies were found. |
| 6 | The frontend-facing Java REST API, Java-to-Python REST API, and document event topology are described before service behavior exists. | VERIFIED | Java app exposes only Actuator health; Python exposes `/health` and `/ready`; contracts already describe auth/users/documents/chat, `/v1/query`, citation lookup, and document events. |
| 7 | Routing keys, queues, exchanges, and contract error codes are declared once in `constants.yaml`. | VERIFIED | `contracts/constants.yaml` contains `routing_keys`, `queues`, `exchanges`, and `error_codes`; generators consume this file for Java and Python constants. |
| 8 | Developer can run one local command that lints contracts and regenerates Java and Python contract surfaces. | VERIFIED | `scripts/verify-contracts.py` orchestrates lint, generation, Java compile, Python generation, and smoke imports; PowerShell/POSIX/Makefile wrappers delegate to it. |
| 9 | Generated Java DTOs/constants and Python Pydantic models/constants are produced from root contracts without committing generated outputs. | VERIFIED | Generated Java outputs under `backend/**/target/` and Python outputs under `ai-service/src/corp_rag_ai/contracts/generated/` are ignored by `.gitignore`; source contracts are tracked. |
| 10 | The Java contract module compiles generated DTOs and constants before service behavior exists. | VERIFIED | `backend/corp-rag-contracts/pom.xml` uses OpenAPI Generator and generated source roots; the contract verifier completed Maven `generate-sources` and `compile`. |
| 11 | Java backend has a runnable Spring Boot application with Actuator health on port 8080. | VERIFIED | `application.yml` sets `server.port: 8080` and health exposure; Maven app tests passed and assert `/actuator/health` returns `UP`; Docker Compose reports `java-backend` healthy. |
| 12 | Java backend compiles against the generated contract module without handwritten contract DTOs. | VERIFIED | `corp-rag-app` depends on `corp-rag-contracts`; app tests import generated `ApiRoot`; no handwritten DTO package was found in app source. |
| 13 | Java database migration infrastructure exists with an empty baseline for the Java-owned Postgres database. | VERIFIED | `V1__baseline.sql` exists and contains only comments; `application.yml` enables Flyway against `corp_rag_java`; Makefile has `migrate-java`. |
| 14 | Python AI service has a runnable FastAPI application on port 8000. | VERIFIED | `uv run python -c "from corp_rag_ai.main import app..."` printed `Corp RAG AI Service` and showed `/health` and `/ready`; Docker Compose reports `python-ai` healthy. |
| 15 | Python generated contract modules can be created under the documented package path and imported by tests/checks. | VERIFIED | `scripts/generate_python_contracts.py` writes `api_v1.py`, `ai_service_v1.py`, and `events_v1.py` under `corp_rag_ai.contracts.generated`; verifier smoke-imported them. |
| 16 | Python database migration infrastructure exists with an empty Alembic baseline for the AI-owned Postgres database. | VERIFIED | `alembic.ini`, `migrations/env.py`, and `0001_empty_baseline.py` exist; `uv run alembic upgrade head --sql` produced only `alembic_version` plus baseline insertion. |
| 17 | Frontend has a static browser entrypoint that nginx can serve in the local stack. | VERIFIED | `frontend/index.html`, `nginx.conf`, and `Dockerfile` exist; Docker Compose reports `frontend` healthy. |
| 18 | The first browser screen clearly identifies the product as Corp RAG without adding app routing or API clients. | VERIFIED | `frontend/index.html` contains title and H1 `Corp RAG - coming soon`; no script/module/router/API client code appears in the frontend shell. |
| 19 | Frontend Docker image can be built independently for compose. | VERIFIED | `frontend/Dockerfile` copies `nginx.conf`, `index.html`, and styles; Compose builds `corp-rag-frontend:phase1` and the running frontend container is healthy. |
| 20 | Developer can start the Phase 1 local platform through Docker Compose. | VERIFIED | Compose config resolves, and all services from `infra/docker-compose.yml` are running healthy in the current local platform. |
| 21 | PostgreSQL creates scoped Java and Python databases/users for the two service owners. | VERIFIED | `infra/postgres/init.sql` creates roles and databases for `corp_rag_java` and `corp_rag_ai`; Java/Python configs and compose env vars match those names. |
| 22 | Root Makefile exposes contract verification and standalone Java/Python migration targets. | VERIFIED | `Makefile` includes `verify-contracts`, `compose-up`, `compose-ps`, `compose-down`, `migrate-java`, and `migrate-python`; `make` itself is unavailable on this Windows runner, so equivalent underlying commands were verified directly. |
| 23 | All required local environment variables are documented with placeholders and no real secrets. | VERIFIED | `.env.example` documents Postgres, Java, Python, MinIO, RabbitMQ, Qdrant, Neo4j, Langfuse, and service ports using local placeholder values. |

**Score:** 23/23 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `contracts/openapi/api-v1.yaml` | Frontend-facing Java REST API contract | VERIFIED | Defines auth, users, roles, access policies, documents, chat, root, ProblemDetail, pagination, citations, and guard schemas. |
| `contracts/openapi/ai-service-v1.yaml` | Internal Java-to-Python REST API contract | VERIFIED | Defines `/v1/query`, citation chunk lookup, health/readiness, QueryRequest, QueryResponse, AccessFilter, Citation, GuardVerdict, RetrievalMeta, and ProblemDetail. |
| `contracts/asyncapi/events-v1.yaml` | RabbitMQ document event contract | VERIFIED | Defines upload/delete/indexed/failed events, queues, DLQs, operations, and envelope metadata. |
| `contracts/constants.yaml` | Shared constants source | VERIFIED | Defines routing keys, queues, exchanges, and RFC 7807 error codes. |
| `backend/corp-rag-contracts/pom.xml` | Java contract generation module | VERIFIED | Uses `openapi-generator-maven-plugin`, root contract input specs, and generated source roots. |
| `scripts/verify-contracts.py` | Contract verification orchestrator | VERIFIED | Runs lint, constants generation, Java generation/compile, Python generation, and Python import smoke checks. |
| `scripts/generate_constants.py` | Shared constants generator | VERIFIED | Parses `contracts/constants.yaml` and writes Java/Python constants. |
| `scripts/generate_python_contracts.py` | Python model generator | VERIFIED | Writes Pydantic-compatible modules from OpenAPI/AsyncAPI schemas. |
| `Makefile` | Root developer command surface | VERIFIED | Contains contract, compose, and migration targets. |
| `backend/corp-rag-app/pom.xml` | Spring Boot app module | VERIFIED | Includes web, actuator, validation, JDBC, Flyway, PostgreSQL, H2 test, and contract module dependency. |
| `backend/corp-rag-app/src/main/java/com/corprag/CorpRagApplication.java` | Java application entrypoint | VERIFIED | Standard Spring Boot `main` entrypoint. |
| `backend/corp-rag-app/src/main/resources/application.yml` | Java runtime config | VERIFIED | Configures port 8080, datasource env vars, Flyway, and Actuator health. |
| `backend/corp-rag-app/src/main/resources/db/migration/V1__baseline.sql` | Java Flyway baseline | VERIFIED | Empty baseline with no domain tables. |
| `backend/corp-rag-app/Dockerfile` | Java backend image | VERIFIED | Builds from repository root so Maven can access contracts and backend modules. |
| `ai-service/pyproject.toml` | uv-managed Python project | VERIFIED | Declares FastAPI, Pydantic, pydantic-settings, SQLAlchemy async, asyncpg, Alembic, Uvicorn, pytest, and pytest-asyncio. |
| `ai-service/src/corp_rag_ai/main.py` | FastAPI app | VERIFIED | Exports `app` with `/health` and `/ready`. |
| `ai-service/src/corp_rag_ai/config.py` | Typed Python settings | VERIFIED | Maps AI DB, RabbitMQ, Qdrant, Neo4j, MinIO, and Langfuse environment variables. |
| `ai-service/alembic.ini` and `ai-service/migrations/` | Python migration infrastructure | VERIFIED | Async Alembic env reads settings; baseline revision is empty. |
| `ai-service/Dockerfile` | Python AI image | VERIFIED | Runs `uvicorn corp_rag_ai.main:app` on port 8000. |
| `frontend/index.html` | Static browser entrypoint | VERIFIED | Contains `Corp RAG - coming soon` and no scripts. |
| `frontend/src/styles/base.css` | Plain CSS foundation | VERIFIED | Uses CSS custom properties and BEM-style classes. |
| `frontend/nginx.conf` and `frontend/Dockerfile` | Static frontend packaging | VERIFIED | nginx serves index/styles and exposes `/health`. |
| `infra/docker-compose.yml` | Local platform compose file | VERIFIED | Defines postgres, minio, rabbitmq, qdrant, neo4j, langfuse, java-backend, python-ai, and frontend with healthchecks. |
| `infra/postgres/init.sql` | Postgres bootstrap | VERIFIED | Creates scoped Java, Python, and Langfuse local databases/users. |
| `.env.example` and `infra/.env.example` | Local env examples | VERIFIED | Root env contains required placeholders; infra env points developers back to root env usage. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `contracts/constants.yaml` | `contracts/asyncapi/events-v1.yaml` | Matching routing key, queue, exchange, and DLQ names | WIRED | Routing keys and queue names in AsyncAPI match constants values. |
| `contracts/openapi/api-v1.yaml` | `contracts/openapi/ai-service-v1.yaml` | Compatible schemas | WIRED | Shared concepts are present: QueryRequest/QueryResponse boundary, Citation, GuardVerdict, AccessFilter, ProblemDetail/error codes. |
| `contracts/openapi/*.yaml` | Java generated OpenAPI sources | OpenAPI Generator in `corp-rag-contracts` | WIRED | `pom.xml` points input specs at root contracts and writes `target/generated-sources/openapi`; verifier generated/compiled output. |
| `contracts/constants.yaml` | Java/Python generated constants | `scripts/generate_constants.py` | WIRED | Generated Java `EventRoutingKeys`, `QueueNames`, `ExchangeNames`, `ErrorCodes`; generated Python `routing_keys.py`, `queue_names.py`, `exchange_names.py`, `error_codes.py`. |
| `scripts/verify-contracts.py` | Makefile and shell wrappers | Thin wrapper commands | WIRED | Makefile, `.ps1`, and `.sh` call the central Python verifier. |
| `backend/corp-rag-app/pom.xml` | `backend/corp-rag-contracts` | Maven module dependency | WIRED | App POM depends on `corp-rag-contracts`; app test imports generated `ApiRoot`. |
| `backend/corp-rag-app/src/main/resources/application.yml` | `infra/postgres/init.sql` | Matching Java database credentials | WIRED | Java config defaults/env vars use `corp_rag_java`; Postgres init creates that DB/user. |
| `backend/corp-rag-app/Dockerfile` | `infra/docker-compose.yml` | Compose build context | WIRED | Compose `java-backend` builds with repository-root context and `backend/corp-rag-app/Dockerfile`. |
| `scripts/generate_python_contracts.py` | `ai-service/src/corp_rag_ai/contracts/generated/` | Generation target | WIRED | Script writes generated modules under documented package; output is ignored. |
| `ai-service/src/corp_rag_ai/config.py` | `infra/docker-compose.yml` | Environment variable names | WIRED | Compose supplies `AI_DB_URL`, `RABBITMQ_URL`, `QDRANT_URL`, `NEO4J_*`, `MINIO_*`, and `LANGFUSE_*` used by settings. |
| `ai-service/alembic.ini` | `Makefile migrate-python` | Alembic command target | WIRED | `migrate-python` runs `uv run alembic upgrade head`; Alembic env reads `AI_DB_URL`. |
| `frontend/Dockerfile` | `frontend/nginx.conf` and `frontend/index.html` | Docker image copies nginx/static files | WIRED | Dockerfile copies nginx config, index, and styles. |
| `frontend/Dockerfile` | `infra/docker-compose.yml` | Compose build context | WIRED | Compose `frontend` builds from `../frontend` and healthchecks `/health`. |
| `infra/postgres/init.sql` | Java/Python runtime config | Matching scoped credentials | WIRED | DB/user names align with Java `application.yml`, Python `config.py`, and `.env.example`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `scripts/verify-contracts.py` | Generated Java/Python contract surfaces | Root YAML contracts and constants | Yes | FLOWING - verifier executed codegen and smoke imports. |
| `backend/corp-rag-app` | Actuator health status | Spring Boot Actuator | Yes | FLOWING - Maven test asserted `/actuator/health` returns `UP`; compose reports healthy. |
| `ai-service/src/corp_rag_ai/main.py` | FastAPI route responses | In-process route handlers | Yes | FLOWING - import check listed `/health` and `/ready`; compose reports healthy. |
| `frontend/index.html` | Static product copy | Tracked HTML/CSS copied into nginx image | Yes | FLOWING - frontend image copies static files and compose healthcheck passes. |
| `infra/docker-compose.yml` | Service health state | Docker Compose and container healthchecks | Yes | FLOWING - live `ps` shows every Phase 1 service `running healthy`. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Compose defines the nine Phase 1 services | `docker compose --env-file .env.example -f infra/docker-compose.yml config --services` | Listed `rabbitmq`, `postgres`, `langfuse`, `neo4j`, `qdrant`, `minio`, `java-backend`, `frontend`, `python-ai`. | PASS |
| Current local platform is healthy | `docker compose --env-file .env.example -f infra/docker-compose.yml ps --format json` | All nine services were `running healthy`. | PASS |
| Contract verifier produces Java/Python outputs | `PATH=C:\tmp\botvenv-m04\Scripts;%PATH%; MAVEN_CMD=C:\dev\apache-maven-3.9.15\bin\mvn.cmd; python scripts/verify-contracts.py` | Passed lint, Java generation/compile, Python generation, and smoke imports. | PASS |
| Java app tests and generated contract dependency | `C:\dev\apache-maven-3.9.15\bin\mvn.cmd -q -f backend\pom.xml -pl corp-rag-app -am test` | Passed; test context loaded and `/actuator/health` returned `UP`. | PASS |
| Python FastAPI app imports and registers health routes | `uv run python -c "from corp_rag_ai.main import app; ..."` | Printed `Corp RAG AI Service` and `['/health', '/ready']`. | PASS |
| Python Alembic baseline renders | `uv run alembic upgrade head --sql` | Rendered only `alembic_version` and baseline revision insertion. | PASS |

### Probe Execution

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| None discovered | `find scripts -path '*/tests/probe-*.sh'` equivalent by file listing | No conventional or phase-declared probes exist in `scripts/`. | SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| FND-01 | 01-03, 01-04, 01-05, 01-06 | Local Docker Compose environment can run core infrastructure for PostgreSQL, MinIO, RabbitMQ, Qdrant, Neo4j, and observability dependencies. | SATISFIED | Compose defines and currently runs postgres, minio, rabbitmq, qdrant, neo4j, langfuse, java-backend, python-ai, and frontend; all are healthy. |
| FND-02 | 01-01 | Shared OpenAPI and AsyncAPI contracts define Java frontend API, Java-to-Python API, and RabbitMQ events before implementation. | SATISFIED | Root contract files define Java REST API, AI service API, document events, and constants; services remain minimal skeletons. |
| FND-03 | 01-02, 01-03, 01-04 | Generated Java DTOs/constants and Python Pydantic models/constants are produced from the shared contracts. | SATISFIED | Contract verifier generated Java OpenAPI/constants, compiled Java contract module, generated Python model/constants modules, and smoke-imported Python outputs. |

No orphaned Phase 1 requirements were found: `.planning/REQUIREMENTS.md` maps only FND-01, FND-02, and FND-03 to Phase 1, and all three appear in plan frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `.env.example` | 59-60 | `placeholder` in Langfuse keys | INFO | Intentional env placeholder values; Phase 1 requires no real secrets. |
| `infra/docker-compose.yml` | 166-167 | `placeholder` in Langfuse env defaults | INFO | Intentional local placeholder values used by compose. |
| `frontend/index.html` | 6, 13 | `Corp RAG - coming soon` | INFO | Intentional Phase 1 static shell text required by plan D-26. |
| `scripts/generate_constants.py` | 63, 66, 187, 190 | Empty dict/list returns | INFO | Parser control-flow defaults, not user-visible stub data. |

No unreferenced `TBD`, `FIXME`, or `XXX` markers were found in phase-modified code.

### Human Verification Required

None. The Phase 1 goal is infrastructure/contracts/scaffold behavior and was verified through code inspection plus runnable local commands.

### Gaps Summary

No blocking gaps found. The phase goal is achieved in the codebase.

Verification notes:
- Bare `make` is not installed on this Windows runner, so Makefile targets were verified by inspecting thin target bodies and running the underlying commands directly.
- The sandboxed contract verifier failed at Maven compile with `Access is denied` / compiler resource errors. Re-running the same verifier outside the sandbox passed.
- `STRUCTURE.md` does not exist, so codebase drift against that document is not applicable.

---

_Verified: 2026-05-11T20:43:29Z_
_Verifier: the agent (gsd-verifier)_
