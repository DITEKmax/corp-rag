# Roadmap: Corporate RAG System

## Overview

This roadmap turns the ingested architecture, ADRs, and implementation breakdown into eight coherent delivery phases. It starts with local infrastructure and contracts, builds the Java enterprise backbone, adds asynchronous document indexing, delivers the Python RAG pipeline and guarded query API, then finishes with the user-facing chat/admin experience, evaluation evidence, and production-like demo readiness.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Foundation & Contracts** - Local infrastructure and shared API/event contracts are ready.
- [x] **Phase 2: Identity, Users & Access Control** - Java authentication, users, roles, permissions, and access filters work.
- [x] **Phase 3: Documents, Events & Audit** - Java can manage documents and exchange indexing events safely. (completed 2026-05-17)
- [ ] **Phase 4: Python Ingestion & Indexing** - Python can parse, sanitize, embed, vector-index, graph-index, and report document status.
- [ ] **Phase 5: Retrieval, Guards & Query API** - Python can route queries, retrieve permitted evidence, guard prompts, and return cited answers.
- [ ] **Phase 6: Chat & Frontend Experience** - Users can use the browser app for login, chat, citations, and admin workflows.
- [ ] **Phase 7: Evaluation & Observability** - Quality, safety, ablation, traces, and metrics are measurable.
- [ ] **Phase 8: Delivery Polish & Demo Readiness** - Production-like compose, seed corpus, final regression, README, and demo assets are ready.

## Phase Details

### Phase 1: Foundation & Contracts
**Goal**: The repo has a runnable local platform and contract-first foundation for Java, Python, frontend, and message flows.
**Depends on**: Nothing (first phase)
**Requirements**: FND-01, FND-02, FND-03
**Success Criteria** (what must be TRUE):
  1. Developer can start the core infrastructure stack through Docker Compose.
  2. Java, Python, frontend, and contract directories exist with consistent project structure.
  3. OpenAPI and AsyncAPI files describe the v1 REST and RabbitMQ contracts.
  4. Generated DTO/model code can be produced from the contracts.
**Plans:** 6 plans
Plans:
- [x] 01-01-PLAN.md - Define root OpenAPI, AsyncAPI, and constants contracts.
- [x] 01-02-PLAN.md - Add contract generation and verification harness.
- [x] 01-03-PLAN.md - Scaffold Java Spring Boot backend foundation.
- [x] 01-04-PLAN.md - Scaffold Python FastAPI AI-service foundation.
- [x] 01-05-PLAN.md - Add static frontend nginx shell.
- [x] 01-06-PLAN.md - Wire Docker Compose, Postgres initialization, env examples, and Makefile targets.

### Phase 2: Identity, Users & Access Control
**Goal**: Authenticated users and admins can operate within role and document-access boundaries enforced by Java.
**Depends on**: Phase 1
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04
**Success Criteria** (what must be TRUE):
  1. User can log in, stay authenticated through secure cookies, call `/me`, and log out.
  2. Admin can create users and roles and assign/remove role membership.
  3. Protected endpoints reject unauthorized users and users without required permissions.
  4. Java can resolve a user's access filter for downstream document retrieval.
**Plans:** 7 plans
Plans:
**Wave 1**
- [x] 02-01-PLAN.md - Extend Phase 2 contracts and constants.

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 02-02-PLAN.md - Add backend security dependencies and validation harness.

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 02-03-PLAN.md - Add identity schema, seed data, domain records, and repositories.

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 02-04-PLAN.md - Implement core auth, sessions, cookies, JWT, and security filters.

**Wave 5** *(blocked on Wave 4 completion)*
- [x] 02-05-PLAN.md - Implement first-admin bootstrap, password lifecycle, and user management.
- [x] 02-06-PLAN.md - Implement roles, permissions, and user-role assignment.

**Wave 6** *(blocked on Wave 5 completion)*
- [x] 02-07-PLAN.md - Implement access policies, access filters, audit integration, and full flow tests.

### Phase 3: Documents, Events & Audit
**Goal**: Java owns document metadata, object storage orchestration, document events, indexing status updates, and audit logging.
**Depends on**: Phase 2
**Requirements**: DOC-01, DOC-02, DOC-03, EVT-01, EVT-02, AUD-01
**Success Criteria** (what must be TRUE):
  1. Authorized user can upload a document with metadata and retrieve document listings/details.
  2. Java stores document files in MinIO and metadata/status in PostgreSQL.
  3. Document upload/delete events are persisted through the outbox and published to RabbitMQ.
  4. Java idempotently consumes indexed/failed events and updates document status.
  5. Significant auth, document, role, chat, indexing, and guard events are auditable.
**Plans:** 6/6 plans complete
**Status:** Complete - automated verification passed and Docker-backed HUMAN UAT passed on 2026-05-17.
Plans:
**Wave 1**
- [x] 03-01-PLAN.md - Align Phase 3 REST, event, and constants contracts.

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 03-02-PLAN.md - Add document/outbox/processed-event schema, repositories, and correlation foundation.

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 03-03-PLAN.md - Implement MinIO/Tika document upload and document.uploaded outbox creation.

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 03-04-PLAN.md - Implement visible document list/detail/raw/delete APIs and document.deleted outbox creation.

**Wave 5** *(blocked on Wave 4 completion)*
- [x] 03-05-PLAN.md - Add RabbitMQ topology and scheduled outbox publisher.

**Wave 6** *(blocked on Wave 5 completion)*
- [x] 03-06-PLAN.md - Implement idempotent indexing-result consumers and full lifecycle verification.

### Phase 4: Python Ingestion & Indexing
**Goal**: Python turns uploaded documents into sanitized chunks, Qdrant vectors, Neo4j graph data, and completion/failure events.
**Depends on**: Phase 3
**Requirements**: ING-01, ING-02, ING-03, ING-04, ING-05, ING-06, ING-07
**Success Criteria** (what must be TRUE):
  1. Python consumes upload/delete events once even when RabbitMQ redelivers messages.
  2. Supported source files are parsed into normalized content with sections/tables where available.
  3. Chunks are sanitized, embedded with bge-m3 dense+sparse vectors, and upserted to Qdrant.
  4. Entities and relations are extracted and written to Neo4j.
  5. Java receives indexed or failed events with enough detail to update document status.
**Plans:** 6/8 plans complete
**Status:** In progress - Wave 6 Gemini entity extraction and Neo4j graph indexing completed on 2026-05-17.
Plans:
**Wave 1**
- [x] 04-01-PLAN.md - Fix python-ai repo-root Docker codegen and local bge-m3 runtime contour.

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 04-02-PLAN.md - Add AI ingestion state, AMQP foundation, and stage-aware failure reporting.

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 04-03-PLAN.md - Implement normalized parsing for PDF, DOCX, HTML, Markdown, and plain text.

**Wave 4** *(blocked on Waves 2 and 3 completion)*
- [x] 04-04-PLAN.md - Implement deterministic parent/child chunking and Tier-0 sanitizer.

**Wave 5** *(blocked on Waves 1 and 4 completion)*
- [x] 04-05-PLAN.md - Implement local FlagEmbedding bge-m3 embeddings and Qdrant vector indexing.

**Wave 6** *(blocked on Wave 5 completion)*
- [x] 04-06-PLAN.md - Implement Gemini entity extraction and provenance-first Neo4j graph indexing.

**Wave 7** *(blocked on Waves 2-6 completion)*
- [ ] 04-07-PLAN.md - Wire full upload/delete ingestion orchestration and terminal event semantics.

**Wave 8** *(blocked on Wave 7 completion)*
- [ ] 04-08-PLAN.md - Add Phase 4 UAT checklist, live smoke helpers, and end-to-end UAT evidence.

### Phase 5: Retrieval, Guards & Query API
**Goal**: Python can safely answer Java query requests using access-filtered hybrid/graph retrieval and cited structured generation.
**Depends on**: Phase 4
**Requirements**: RET-01, RET-02, RET-03, RET-04, AGT-01, AGT-02, AGT-03, SEC-01
**Success Criteria** (what must be TRUE):
  1. Query API rejects or flags unsafe input before retrieval or generation.
  2. Hybrid and graph retrievers apply access filters before returning chunks.
  3. Query router selects retrieval strategy for factual, aggregation, multi-hop, comparison, or unsupported queries.
  4. Parent resolution and reranking produce compact, relevant context for generation.
  5. Query response includes answer, citations, confidence, answered flag, guard verdict when relevant, and retrieval metadata.
**Plans**: TBD

### Phase 6: Chat & Frontend Experience
**Goal**: Users can complete the core workflows in the browser: login, chat with citations, inspect sources, and perform admin tasks.
**Depends on**: Phase 5
**Requirements**: CHAT-01, CHAT-02, UI-01, UI-02, UI-03
**Success Criteria** (what must be TRUE):
  1. User can create or continue a private conversation and see persisted message history.
  2. Chat query flow calls Python through Java and displays answer, citations, confidence, and guard results.
  3. User can open a cited chunk/source from the answer UI.
  4. Admin can manage documents, users, roles, and access policies from frontend screens.
**Plans**: TBD
**UI hint**: yes

### Phase 7: Evaluation & Observability
**Goal**: The project has evidence for answer quality, retrieval quality, guard effectiveness, ablation, and runtime traces.
**Depends on**: Phase 6
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04, OPS-01
**Success Criteria** (what must be TRUE):
  1. Golden dataset covers factual, aggregation, multi-hop, and out-of-scope questions.
  2. RAGAS and retrieval metric runners produce repeatable reports.
  3. Injection probes measure and report block rate.
  4. Ablation compares BM25, dense, sparse, hybrid, and hybrid+reranker retrieval variants.
  5. Langfuse traces and service metrics are visible for debugging and demo.
**Plans**: TBD

### Phase 8: Delivery Polish & Demo Readiness
**Goal**: The MVP is packaged for a production-like local run and can be demonstrated with seeded corpus, regression evidence, and documentation.
**Depends on**: Phase 7
**Requirements**: DEL-01
**Success Criteria** (what must be TRUE):
  1. Production-like Docker Compose starts the full MVP stack.
  2. Seed corpus script loads demo documents and triggers indexing.
  3. Final regression proves the core chat/citation/evaluation path still works.
  4. README, architecture diagram, demo assets, and short video are ready for review.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Contracts | 6/6 | Complete | 2026-05-11 |
| 2. Identity, Users & Access Control | 7/7 | Complete | 2026-05-12 |
| 3. Documents, Events & Audit | 6/6 | Complete | 2026-05-17 |
| 4. Python Ingestion & Indexing | 6/8 | In progress | - |
| 5. Retrieval, Guards & Query API | 0/TBD | Not started | - |
| 6. Chat & Frontend Experience | 0/TBD | Not started | - |
| 7. Evaluation & Observability | 0/TBD | Not started | - |
| 8. Delivery Polish & Demo Readiness | 0/TBD | Not started | - |
