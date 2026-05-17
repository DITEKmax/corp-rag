# Requirements: Corporate RAG System

**Defined:** 2026-05-11
**Core Value:** Employees can ask natural-language questions over permitted corporate documents and receive grounded, cited answers without leaking data across access boundaries.

## v1 Requirements

### Foundation

- [x] **FND-01**: Local Docker Compose environment can run core infrastructure for PostgreSQL, MinIO, RabbitMQ, Qdrant, Neo4j, and observability dependencies.
- [x] **FND-02**: Shared OpenAPI and AsyncAPI contracts define Java frontend API, Java-to-Python API, and RabbitMQ events before implementation.
- [x] **FND-03**: Generated Java DTOs/constants and Python Pydantic models/constants are produced from the shared contracts.

### Identity and Access

- [x] **AUTH-01**: User can log in, log out, and retrieve the current profile through secure Java endpoints.
- [x] **AUTH-02**: Admin can create users, roles, permissions, and access policies.
- [x] **AUTH-03**: Protected endpoints enforce role permissions and access policies.
- [x] **AUTH-04**: Java resolves each user's document access filter for downstream retrieval.

### Documents and Events

- [x] **DOC-01**: Authorized user can upload a document file with metadata and store the file in MinIO.
- [x] **DOC-02**: User can list, filter, inspect, delete, and open raw documents according to permissions.
- [x] **DOC-03**: Java tracks document indexing status, failure reason, chunk count, and indexed timestamp.
- [x] **EVT-01**: Java publishes document upload/delete events through an outbox-backed RabbitMQ topology.
- [x] **EVT-02**: Java consumes document indexed/failed events idempotently and updates document status.
- [x] **AUD-01**: Java records audit events for login, document, chat, user, role, indexing, and guard actions.

### Python Ingestion

- [x] **ING-01**: Python consumes document upload/delete events idempotently.
- [ ] **ING-02**: Python fetches source files from MinIO and parses PDF, DOCX, HTML, Markdown, and plain text into a normalized document representation.
- [ ] **ING-03**: Python chunks parsed documents into parent and child chunks with inherited document metadata.
- [ ] **ING-04**: Python sanitizes chunks and excludes unsafe chunks from retrieval.
- [ ] **ING-05**: Python creates bge-m3 dense+sparse embeddings and writes chunk points to Qdrant.
- [ ] **ING-06**: Python extracts entities/relations and writes graph data to Neo4j.
- [x] **ING-07**: Python publishes indexed/failed events with stage-aware details.

### Retrieval and Answering

- [ ] **RET-01**: Hybrid retriever queries Qdrant with dense+sparse bge-m3 vectors and RRF fusion.
- [ ] **RET-02**: Retrieval applies access filters in Qdrant and Neo4j so unauthorized chunks cannot be returned.
- [ ] **RET-03**: Graph retrievers support local and global entity-based retrieval for multi-hop, aggregation, and comparison questions.
- [ ] **RET-04**: Parent resolver and reranker reduce retrieved evidence to the final context.
- [ ] **AGT-01**: Query router classifies factual, aggregation, multi-hop, comparison, and unsupported queries.
- [ ] **AGT-02**: LangGraph orchestrates guard, retrieval, rerank, synthesis, and output guard nodes.
- [ ] **AGT-03**: Answer generation returns cited structured output with answer, citations, confidence, answered flag, and retrieval metadata.
- [ ] **SEC-01**: Guard stack blocks known prompt injection patterns, classifies unsafe requests, isolates retrieved context, and checks outputs.

### Chat and Frontend

- [ ] **CHAT-01**: Java stores conversations and messages for authenticated users.
- [ ] **CHAT-02**: Java chat query endpoint calls Python with the user's access filter and persists user/assistant messages.
- [ ] **UI-01**: Frontend provides login, app shell, routing, and session guard.
- [ ] **UI-02**: Frontend provides chat conversation list, message view, input, citation chips, and source viewer.
- [ ] **UI-03**: Frontend provides admin screens for documents, users, roles, and access policies.

### Evaluation and Delivery

- [ ] **EVAL-01**: Golden dataset covers factual, aggregation, multi-hop, and out-of-scope questions.
- [ ] **EVAL-02**: RAGAS and retrieval metrics report faithfulness, relevancy, context precision/recall, recall@k, and MRR.
- [ ] **EVAL-03**: Injection probes measure guard block rate.
- [ ] **EVAL-04**: Ablation compares BM25, dense, sparse, hybrid, and hybrid+reranker variants.
- [ ] **OPS-01**: Langfuse traces and service metrics are available for demo and diagnostics.
- [ ] **DEL-01**: Production-like Docker Compose, seed corpus script, final regression, README/demo assets, and short video demo are ready.

## v2 Requirements

### Deferred Product Scope

- **V2-DOC-01**: Full document version history instead of MVP overwrite behavior.
- **V2-CHAT-01**: Streaming chat answers over SSE.
- **V2-AUTH-01**: Self-service registration or SSO integration.
- **V2-OPS-01**: Scheduled Qdrant/Neo4j backups.
- **V2-LLM-01**: Fully local model runtime path through Ollama, vLLM, or similar on-premise stack.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Frontend-to-Python direct calls | Breaks BFF/security boundary; Java must remain the browser-facing API. |
| Public self-registration | Enterprise MVP assumes admin-created users. |
| Streaming answers in MVP | Full-answer response is sufficient for MVP; SSE can be added later. |
| Production backup automation | Useful later, but not required to prove MVP behavior. |
| Paid-only model dependency | Conflicts with the budget/on-premise diploma constraint. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FND-01 | Phase 1 | Complete |
| FND-02 | Phase 1 | Complete |
| FND-03 | Phase 1 | Complete |
| AUTH-01 | Phase 2 | Complete |
| AUTH-02 | Phase 2 | Complete |
| AUTH-03 | Phase 2 | Complete |
| AUTH-04 | Phase 2 | Complete |
| DOC-01 | Phase 3 | Complete |
| DOC-02 | Phase 3 | Complete |
| DOC-03 | Phase 3 | Complete |
| EVT-01 | Phase 3 | Complete |
| EVT-02 | Phase 3 | Complete |
| AUD-01 | Phase 3 | Complete |
| ING-01 | Phase 4 | Complete |
| ING-02 | Phase 4 | Pending |
| ING-03 | Phase 4 | Pending |
| ING-04 | Phase 4 | Pending |
| ING-05 | Phase 4 | Pending |
| ING-06 | Phase 4 | Pending |
| ING-07 | Phase 4 | Complete |
| RET-01 | Phase 5 | Pending |
| RET-02 | Phase 5 | Pending |
| RET-03 | Phase 5 | Pending |
| RET-04 | Phase 5 | Pending |
| AGT-01 | Phase 5 | Pending |
| AGT-02 | Phase 5 | Pending |
| AGT-03 | Phase 5 | Pending |
| SEC-01 | Phase 5 | Pending |
| CHAT-01 | Phase 6 | Pending |
| CHAT-02 | Phase 6 | Pending |
| UI-01 | Phase 6 | Pending |
| UI-02 | Phase 6 | Pending |
| UI-03 | Phase 6 | Pending |
| EVAL-01 | Phase 7 | Pending |
| EVAL-02 | Phase 7 | Pending |
| EVAL-03 | Phase 7 | Pending |
| EVAL-04 | Phase 7 | Pending |
| OPS-01 | Phase 7 | Pending |
| DEL-01 | Phase 8 | Pending |

**Coverage:**
- v1 requirements: 39 total
- Mapped to phases: 39
- Unmapped: 0

---
*Requirements defined: 2026-05-11*
*Last updated: 2026-05-11 after ingesting docs/*
