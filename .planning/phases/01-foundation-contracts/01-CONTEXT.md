# Phase 1: Foundation & Contracts - Context

**Gathered:** 2026-05-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 delivers the runnable project shape and contract-first foundation for the Corporate RAG System. It must prove that Java, Python, frontend, Docker Compose, shared contracts, generated code, and empty database migration baselines all work together. It does not implement product behavior.

</domain>

<decisions>
## Implementation Decisions

### Contract Scope
- **D-01:** Phase 1 defines the full v1 contract baseline upfront. Implementation happens phase by phase, but the contract surface is not invented ad hoc later.
- **D-02:** Full v1 covers all three mandatory surfaces: frontend-facing Java OpenAPI, Java-to-Python OpenAPI, and RabbitMQ AsyncAPI events.
- **D-03:** Admin/user/role endpoints are in scope for the v1 contract because enterprise access control is core project value, not optional admin polish.
- **D-04:** Each endpoint/event needs implementation-ready schemas: request/response DTOs, RFC 7807 error shapes, auth expectations, at least one realistic example, and v1 versioning.
- **D-05:** Phase 1 does not need exhaustive edge-case examples, every possible error-code variant, or polished prose. Standard errors are enough: 400, 401, 403, 404, 409, 500.
- **D-06:** Later contract refinements must be additive and non-breaking. Breaking contract changes require a new ADR.
- **D-07:** Contract completion is proven by lint, codegen, compile/import smoke tests, and generated-model sanity tests.

### Contract Source Location
- **D-08:** Top-level `contracts/` is the only shared source location. It is language-neutral and not owned by Java or Python.
- **D-09:** Required source files are:
  - `contracts/openapi/api-v1.yaml`
  - `contracts/openapi/ai-service-v1.yaml`
  - `contracts/asyncapi/events-v1.yaml`
  - `contracts/constants.yaml`
- **D-10:** Java and Python consume root contracts directly. Do not create checked-in service-local YAML copies, build-time sync copies, or packaged contract artifacts for this monorepo.
- **D-11:** `backend/corp-rag-contracts` is a generated Java contract surface module. It contains generated DTOs and generated constants only.
- **D-12:** Python generated contract code lives under `ai-service/src/corp_rag_ai/contracts/generated/` as normal importable `src`-layout package code.
- **D-13:** `contracts/constants.yaml` is the single source for routing keys, queue names, exchange names, and error codes. Java and Python constants are generated from it.
- **D-14:** No handwritten constants, handwritten DTOs, business logic, mappers, validators, or feature helpers belong in generated contract modules.

### Generated Code Policy
- **D-15:** Generated outputs are not committed. Commit only `contracts/` sources and generator scripts/config.
- **D-16:** Java generated outputs use Maven conventions under `backend/corp-rag-contracts/target/generated-sources/openapi/`; `backend/**/target/` stays ignored.
- **D-17:** Python generated outputs live under `ai-service/src/corp_rag_ai/contracts/generated/` and are explicitly ignored.
- **D-18:** Phase 1 exposes contract verification through `scripts/verify-contracts.py`. Thin wrappers call the same logic: root `Makefile`, `scripts/verify-contracts.ps1`, and `scripts/verify-contracts.sh`.
- **D-19:** `verify-contracts` must lint OpenAPI/AsyncAPI, generate Java DTOs/constants, compile Java generated code, generate Python models/constants, and smoke-import key Python generated modules.
- **D-20:** Phase 1 provides local verification logic. CI wiring can be added later, but the same command should be CI-ready.
- **D-21:** Pre-commit is optional. Provide a documented template/config and `make pre-commit-install`, but do not enforce hooks.

### Foundation Scaffold
- **D-22:** Phase 1 builds minimal runnable skeletons, not feature-ready scaffolding. It proves shape, not behavior.
- **D-23:** Java scope: Spring Boot 3.3 app in `backend/corp-rag-app`, Actuator enabled, port 8080, `GET /actuator/health` returns 200 with status UP. No security config, JWT, business endpoints, or domain DB tables.
- **D-24:** Java Maven structure includes parent POM, `corp-rag-contracts`, and `corp-rag-app`; generated DTOs from `contracts/openapi/api-v1.yaml` compile.
- **D-25:** Python scope: FastAPI app on port 8000, `GET /health` returns healthy, `GET /ready` returns ready, `pyproject.toml` managed by `uv`, generated contract modules import. No retrieval, embeddings, AI logic, or business routers.
- **D-26:** Frontend scope: nginx serves static `index.html` saying `Corp RAG - coming soon`. No JS modules, routing, or API client.
- **D-27:** Docker Compose scope: 9 services are defined and healthy: postgres, minio, rabbitmq, qdrant, neo4j, langfuse, java-backend, python-ai, frontend.
- **D-28:** Compose uses healthchecks for all services and `depends_on: condition: service_healthy` for app dependencies. Done means `docker compose up -d` completes and `docker compose ps` shows all 9 services healthy within about 2 minutes.
- **D-29:** One Postgres container creates two logical databases with separate scoped users: `corp_rag_java` and `corp_rag_ai`.
- **D-30:** Java uses Flyway with an empty baseline migration against `corp_rag_java`.
- **D-31:** Python uses SQLAlchemy 2.0 async, `asyncpg`, and Alembic with an empty baseline migration against `corp_rag_ai`.
- **D-32:** Standalone migration targets are required: `make migrate-java` and `make migrate-python`.
- **D-33:** Langfuse is container-only in Phase 1. It runs healthy and is reachable; Java/Python SDKs and trace instrumentation are deferred.
- **D-34:** `.env.example` documents all required variables and contains placeholders for Langfuse keys and service credentials. No real secrets are committed.

### Explicitly Out of Scope
- Spring Security configuration, JWT handling, auth behavior, and protected endpoints.
- Java or Python business endpoints beyond health/readiness.
- Frontend app router, pages, API client, or session guard.
- Runtime AMQP exchange/queue declaration by application code.
- MinIO bucket creation.
- Qdrant collections.
- Neo4j constraints.
- Domain tables beyond migration-history infrastructure.
- Langfuse SDK instrumentation or correlation-ID tracing.

### the agent's Discretion
- Choose exact generator implementation details that satisfy the decisions above, especially the specific constants generator implementation. Avoid overbuilding; a small Python or JVM-side generator is enough if it is reliable and cross-platform.
- Choose exact healthcheck command variants per image if the planned command is unsupported, while preserving equivalent semantics.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning
- `.planning/PROJECT.md` - project value, constraints, and locked architecture decisions.
- `.planning/REQUIREMENTS.md` - phase requirements FND-01, FND-02, FND-03 and updated generated DTO/constants expectation.
- `.planning/ROADMAP.md` - Phase 1 goal, success criteria, dependencies, and scope boundary.
- `.planning/STATE.md` - current project status and accumulated context.

### Project Docs
- `docs/ARCHITECTURE.md` - target architecture, updated root `contracts/` layout, service structures, and phase task references.
- `docs/PATTERNS.md` - required patterns: Contract-First, Separate Contract Module, Compile-Time Safety, Schema as API, Routing Keys as Constants, One Source of Truth.
- `docs/CONTEXT.md` - project elevator context and architectural rationale.
- `CLAUDE.md` - repo rules that were updated to point contract source to root `contracts/`.

### Service Layout Docs
- `backend/README.md` - Java target structure and generated DTO/constants module role.
- `ai-service/README.md` - Python target structure and generated contract package placement.
- `ROADMAP.md` - root roadmap/epic breakdown updated to use root `contracts/` and generated constants.

### ADRs
- `docs/decisions/ADR-001-embedding-model.md` - locked bge-m3 embedding decision.
- `docs/decisions/ADR-002-vector-database.md` - locked Qdrant vector DB decision.
- `docs/decisions/ADR-003-java-python-split.md` - locked Java/Python split and REST/RabbitMQ integration decision.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/`, `ai-service/`, `frontend/`, `infra/` - existing placeholder service directories to turn into minimal runnable skeletons.
- `docs/ARCHITECTURE.md`, `docs/PATTERNS.md`, `docs/CONTEXT.md` - source documents that already define most target architecture and patterns.
- `docs/decisions/` - existing ADR directory and accepted ADRs.

### Established Patterns
- Contract-first implementation is mandatory: OpenAPI/AsyncAPI/`constants.yaml` before service behavior.
- Frontend talks only to Java; Python is internal.
- Java and Python are separate services with database-per-service logical ownership.
- Generated contract surfaces are compiled/imported artifacts, not committed source.
- Docker Compose is the local MVP operating contour.

### Integration Points
- Root `contracts/` feeds Java Maven codegen and Python codegen directly.
- `backend/corp-rag-contracts` feeds `backend/corp-rag-app` at compile time.
- `ai-service/src/corp_rag_ai/contracts/generated/` feeds FastAPI/Python service code at import time.
- `infra/docker-compose.yml` coordinates all 9 services and health dependencies.
- Postgres init creates both logical DBs; app-level migration tools mark each service baseline.

</code_context>

<specifics>
## Specific Ideas

- `contracts/constants.yaml` should include sections for `routing_keys`, `queues`, `exchanges`, and `error_codes`.
- Python generated contract package target:
  - `api_v1.py`
  - `ai_service_v1.py`
  - `events_v1.py`
  - `routing_keys.py`
  - `queue_names.py`
  - `exchange_names.py`
  - `error_codes.py`
- Phase 1 verification command family:
  - `make verify-contracts`
  - `scripts/verify-contracts.ps1`
  - `scripts/verify-contracts.sh`
  - `python scripts/verify-contracts.py`
- Optional pre-commit config should be documented but not enforced.
- Static frontend placeholder text: `Corp RAG - coming soon`.

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Foundation & Contracts*
*Context gathered: 2026-05-11*
