---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 5 context gathered
last_updated: "2026-05-19T20:01:49.921Z"
last_activity: 2026-05-19 -- Phase 05 planning complete
progress:
  total_phases: 8
  completed_phases: 4
  total_plans: 36
  completed_plans: 28
  percent: 78
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-12)

**Core value:** Employees can ask natural-language questions over permitted corporate documents and receive grounded, cited answers without leaking data across access boundaries.
**Current focus:** Phase 05 -- retrieval-guards-query-api

## Current Position

Phase: 05 -- READY_TO_EXECUTE
Plan: 8 plans
Status: Ready to execute
Last activity: 2026-05-19 -- Phase 05 planning complete

Progress: [complete through Phase 04; Phase 05 plans ready to execute]

## Performance Metrics

**Velocity:**

- Total plans completed: 28
- Average duration: N/A
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 6 | - | - |
| 02 | 7 | - | - |
| 03 | 6 | - | - |
| 04 | 9/9 | ~2h 21m + manual UAT | ~20m for automated waves |

**Recent completed plans:** Phase 04 P01-P09 complete. Phase 04 UAT passed on 2026-05-19 with evidence in `.planning/phases/04-python-ingestion-indexing/04-UAT-EVIDENCE.md`.

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent locked decisions affecting current work:

- ADR-001: Use bge-m3 for dense+sparse embeddings.
- ADR-002: Use Qdrant for vector storage and payload-filtered retrieval.
- ADR-003: Split Java Spring backend and Python AI service.
- [Phase 01]: Root contracts/ remains the only shared source location for REST, event, and generated constant contracts. — Plan 01-01 verified api-v1.yaml, ai-service-v1.yaml, events-v1.yaml, and constants.yaml as the shared contract baseline.
- [Phase 01]: Plan 01-05 keeps the Phase 1 frontend static and nginx-served with no JavaScript modules, routing, API client, or auth/session guard. — Matches D-22 and D-26; real UI behavior is deferred to Phase 6.
- [Phase 01]: Contract verification is centralized in scripts/verify-contracts.py with Makefile, PowerShell, and POSIX wrappers delegating to the same command. — Plan 01-02 requires one local verification command family for lint, generation, Java compile, and Python smoke imports.
- [Phase 01]: Python contract modules import Pydantic when available but remain smoke-importable before ai-service dependency management exists. — Plan 01-04 owns Python dependency setup; Plan 01-02 still needs a local generated-module import smoke check.
- [Phase 01]: Generated Java and Python contract outputs remain build artifacts and are not committed. — Matches D-15 through D-17 and keeps root contracts plus generator scripts as the source of truth.
- [Phase 01]: Java backend remains a minimal Spring Boot 3.3 skeleton with Actuator health only; auth, JWT, business controllers, AMQP declarations, and domain tables remain deferred. — Plan 01-03 follows D-22 and D-23 so later behavior phases add protected APIs and domain schema deliberately.
- [Phase 01]: Java app database configuration uses JAVA_DB_URL, JAVA_DB_USER, and JAVA_DB_PASSWORD with local corp_rag_java defaults. — These names give Plan 01-06 compose and migration targets one env surface for the Java-owned database.
- [Phase 01]: The backend Dockerfile is repository-root-context based so Maven can access backend modules and root contract YAML sources. — Plan 01-02 keeps contracts/ at the repo root and generated Java outputs under backend/corp-rag-contracts/target.
- [Phase 01]: Python AI service configuration uses AI_DB_URL as the shared Alembic and runtime database setting. — Gives Plan 01-06 one compose variable for the AI-owned corp_rag_ai Postgres database.
- [Phase 01]: Python generated contract outputs stay ignored while corp_rag_ai.contracts remains a tracked package namespace. — Preserves D-15 and D-17 while keeping Plan 01-02 generated modules importable from the documented path.
- [Phase 01]: Python AI service remains Phase 1 minimal with health and readiness only. — Matches D-22 and D-25; retrieval, embeddings, graph, guard, AMQP consumer, and business routers remain deferred.
- [Phase 01]: Compose defines the nine Phase 1 services with healthchecks and service_healthy dependency gates. - Verification started postgres, minio, rabbitmq, qdrant, neo4j, langfuse, java-backend, python-ai, and frontend successfully.
- [Phase 01]: Local Postgres creates separate corp_rag_java and corp_rag_ai databases/users for service ownership. - Langfuse uses a support database in the same local container and is not Java/Python-owned domain storage.
- [Phase 01]: Root Makefile targets are thin wrappers over contract verification, Docker Compose, Flyway, and Alembic. - `make` is unavailable in this Windows runner, but the underlying commands were verified directly.
- [Phase 02]: Java identity is complete for MVP auth, users, roles, permissions, access policies, access-filter resolution, and Phase 2 audit events. - Plans 02-01 through 02-07 passed contract verification and backend Maven verification.
- [Phase 02]: Access policies attach to roles and are additive when resolving user visibility. - PUBLIC remains visible by default, while non-public access requires resolved policy coverage.
- [Phase 02]: Generic mutation audit events join the caller transaction, while auth audit keeps independent transaction behavior where needed. - This avoids FK races during newly-created user flows.
- [Phase 02]: PostgreSQL integration tests use a JVM-lifetime singleton Testcontainer to stay compatible with Spring context caching. - Final verify executed Failsafe ITs with skipped count 0.
- [Phase 03]: Document visibility predicates are owned by DocumentRepository and built from ResolvedAccessFilter. - Plan 03-02 keeps active-row, doc type, department wildcard, and access-level filtering in SQL before pagination/counting.
- [Phase 03]: Request correlation uses MDC key correlationId populated by CorrelationIdFilter. - ProblemDetails and AuditEventWriter reuse the same UUID, while absent or invalid incoming headers are replaced with generated UUIDs.
- [Phase 03]: Outbox payload and headers are persisted as JSONB at the repository boundary. - Later services own typed document event envelope construction and AMQP publication behavior.
- [Phase 03]: Document upload writes MinIO objects before the metadata/outbox/audit transaction. - This prevents `document.uploaded` publication for missing objects; orphan cleanup after DB failure is deferred to Phase 7+ housekeeping.
- [Phase 03]: Java MinIO bucket initialization is compose-enabled and default-disabled. - `JAVA_MINIO_INITIALIZE_BUCKET=true` gives local runtime startup initialization while unit/app-context tests avoid requiring MinIO.
- [Phase 03]: ProblemDetails now supports structured `details`. - Upload duplicate failures return `details.existingDocumentId` for contract-aligned client handling.
- [Phase 03]: Document list/detail/raw/delete share repository SQL visibility; raw URL issuance is audited at presign time, and delete is status-agnostic soft delete with `document.deleted` outbox. - Plan 03-04 verified hidden documents return 404 and soft-deleted rows disappear immediately.
- [Phase 03]: RabbitMQ document lifecycle publishing uses generated constants, config-gated outbox scheduling, and persistent AMQP headers. - Plan 03-05 verified publish success/failure backoff, seven-day cleanup, and topology declarations without requiring live RabbitMQ in tests.
- [Phase 03]: Indexing-result consumers are disabled by default and enabled in compose. — Plan 03-06 added inbound RabbitMQ listeners; default-off listener wiring keeps tests broker-independent while compose enables runtime consumption.
- [Phase 03]: Consumer idempotency inserts processed_events before business handling and rolls back that insert on handler failure. — This implements duplicate ACK safety while allowing RabbitMQ retry or DLQ behavior when business processing fails.
- [Phase 03]: Late terminal events for soft-deleted documents are recorded as processed without changing document status or audit details. — Plan 03-06 keeps delete semantics authoritative and prevents Python result events from resurrecting rows.
- [Phase 03]: Correlation prefers a valid x-correlation-id AMQP header, then envelope metadata, then a generated UUID. — This preserves the HTTP to outbox to Python to Java audit chain while handling malformed or missing inbound headers.
- [Phase 04]: Python embeddings pivoted from HF Inference API to local FlagEmbedding for BAAI/bge-m3 dense+sparse output. — Research found HF free-tier feature extraction documents dense-only output; local FlagEmbedding preserves ADR-001 and Qdrant dense+sparse semantics.
- [Phase 04]: Phase 4 completed nine execution plans covering Docker/codegen, state/AMQP, parsing, chunking/sanitizer, embeddings/Qdrant, graph/Neo4j, orchestration, UAT, and the Phase 4.5 LLM provider pivot.
- [Phase 04]: python-ai Docker builds now use repository-root context and isolated builder codegen. - Plan 04-01 removes stale generated contracts before Docker codegen, excludes host generated outputs from the build context, and keeps PyYAML out of the runtime image.
- [Phase 04]: AI AMQP consumers are config-gated and default-disabled until full ingestion orchestration is wired. - Plan 04-02 prevents placeholder handlers from ACKing real queued documents while preserving passive RabbitMQ topology checks and manual ACK/NACK behavior.
- [Phase 04]: Stage-aware failed indexing events are formatted only through StageFailure safe templates. - Plan 04-02 exposes exception class names, MIME/parser/dependency summaries, and retryability without leaking raw exception text or tracebacks.
- [Phase 04]: Parser outputs normalize into the locked ParsedBlock fields only. - Plan 04-03 excludes parser-native metadata from the domain model while assigning deterministic positions and section paths in one pass.
- [Phase 04]: Docling PDF/DOCX parsing uses Markdown export plus the shared Markdown normalizer. - Plan 04-03 keeps normalization deterministic and records that direct page metadata is not retained in this adapter.
- [Phase 04]: Token counting uses tiktoken cl100k_base for deterministic parent/child chunk sizing. - Plan 04-04 adds a cached cl100k counter and boundary-aware child splitting.
- [Phase 04]: Table blocks are isolated as atomic parent/child chunks so they are never split. - Plan 04-04 preserves table Markdown text as a single child even when oversized.
- [Phase 04]: Suspicious sanitizer matches remain indexable with isSanitized=false unless the chunk is empty or garbage. - Plan 04-04 drops only empty, punctuation-only, and repeated-character chunks.
- [Phase 04]: Neo4j graph initialization is config-gated by AI_NEO4J_INITIALIZE_SCHEMA; DeepSeek/OpenRouter extraction and graph writes are deterministic and CI-safe.
- [Phase 04]: Upload and delete orchestration now uses terminal-after-outcome processed_events. - Plan 04-07 publishes indexed/failed results before terminal state+processed writes and ACK.
- [Phase 04]: Qdrant rollback is best-effort after vector, entity extraction, and graph upsert failures. - Plan 04-07 deletes by documentId before failed event publication so retries start from a clean vector state.
- [Phase 04]: DELETED tombstones suppress late upload work. - Plan 04-07 records the upload event as processed without publishing failed events for delete-before-upload and MinIO 404 delete races.
- [Phase 04]: DeepSeek V4 Flash through OpenRouter is the accepted LLM provider for entity extraction and later Phase 5 LLM use. - Phase 4.5 pivot is captured by ADR-004 and 04-09-SUMMARY.md.
- [Phase 04]: End-to-end UAT passed on 2026-05-19. - Evidence is recorded in 04-UAT-EVIDENCE.md; Scenario 1 was skipped because retained Phase 3 AMQP messages were lost before the Phase 4.5 pivot.

### Pending Todos

- Start Phase 5 discussion/planning. Recommended command: `$gsd-discuss-phase 5`, then `$gsd-plan-phase 5`.
- Seed or upload a fresh indexed corpus before Phase 5 retrieval work; the TechCorp UAT happy-path document was deleted during Scenario 6 cleanup.

### Blockers/Concerns

- No blocker for Phase 5 planning.
- Phase 5 should account for the Phase 4 UAT deferred items, especially duplicate upload reprocessing before load-sensitive retrieval demos.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Product | Streaming answers over SSE | Deferred to v2 | Initial ingest |
| Product | Self-service registration or SSO | Deferred to v2 | Initial ingest |
| Ops | Qdrant/Neo4j backup automation | Deferred to v2 | Initial ingest |
| Data | Full document version history | Deferred to v2 | Initial ingest |
| Phase 5 | Fix duplicate upload idempotency short-circuit so repeated event IDs do not call Qdrant, Neo4j, or OpenRouter again. | Backlog | Phase 4 UAT Scenario 5 |
| Phase 5/8 | Decide whether PDF support needs OCR engines or whether demo corpus stays on Markdown/plain text. | Backlog | Phase 4 UAT Scenario 3 |
| Phase 5 | Audit Docling dependency surface; direct dependency is `docling`, while `docling-slim` appears transitively in `uv.lock`. | Backlog | Phase 4 UAT |
| Phase 5 | Consider bumping `python-ai` memory limit from 4 GiB to 6 GiB before reranker/query work. | Backlog | Phase 4 UAT |
| Phase 5/7 | Decide orphan Neo4j entity cleanup strategy; retrieval must filter through accessible Document evidence. | Backlog | Phase 4 UAT Scenario 6 |

## Session Continuity

Last session: 2026-05-19T19:37:52.785Z
Stopped at: Phase 5 context gathered
Resume file: .planning/phases/05-retrieval-guards-query-api/05-CONTEXT.md
