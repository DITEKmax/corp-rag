# Corporate RAG System

## What This Is

Corporate RAG System is an internal AI assistant for searching and summarizing company documents with mandatory source citations. It is built as a serious diploma/portfolio project: Java Spring handles enterprise backend concerns, Python handles the RAG/ML pipeline, and a vanilla SPA talks only to Java.

## Core Value

Employees can ask natural-language questions over permitted corporate documents and receive grounded, cited answers without leaking data across access boundaries.

## Requirements

### Validated

- [x] Phase 1 validated the contract-first foundation: root OpenAPI/AsyncAPI/constants contracts generate Java and Python surfaces.
- [x] Phase 1 validated the runnable local platform: Docker Compose starts postgres, minio, rabbitmq, qdrant, neo4j, langfuse, Java backend, Python AI service, and frontend with healthy checks.
- [x] Phase 2 validated Java-owned identity, users, roles, permissions, access policies, access-filter resolution, and Phase 2 audit flows.

### Active

- [ ] Internal users can authenticate, access only allowed documents, and ask cited questions over corporate knowledge.
- [ ] Admin users can manage documents, users, roles, and access policies.
- [ ] Documents can be uploaded, stored, indexed asynchronously, retrieved through hybrid/graph search, and cited in answers.
- [ ] Prompt injection defenses and evaluation metrics make the system defensible as more than a chatbot demo.
- [ ] The MVP can run locally in a Docker Compose internal-contour style setup.

### Out of Scope

- Self-service public registration — enterprise MVP uses admin-created users.
- Frontend calls directly to Python — Java remains the only browser-facing API.
- Streaming answer delivery — MVP returns complete answers; SSE can be added later.
- Full document version history — MVP overwrites document records; richer versioning is deferred.
- Automated Qdrant/Neo4j backups — documented as future work for the diploma extension.
- Paid-only model dependencies — free/conditional-free tiers or local/on-premise options must remain viable.

## Context

The source documents define a solo-developer MVP with a 10-12 week target and an initial corpus of 30-50 documents, later expandable to 500+ documents. The system is intentionally stronger than a tutorial chatbot: it combines hybrid search, Graph RAG, agentic routing, multi-tier guards, RBAC at retrieval time, RAGAS/retrieval metrics, injection probes, Langfuse traces, and an ablation table.

The system shape is three application services plus infrastructure:

- Java Spring Backend: auth, RBAC, users, roles, document metadata, chat history, audit, MinIO orchestration, REST API for frontend, AMQP publisher/consumer.
- Python AI Service: parsing, chunking, sanitization, bge-m3 embeddings, Qdrant vector storage, Neo4j graph storage, retrieval, reranking, guards, generation, evaluation.
- Frontend SPA: semantic HTML/CSS/vanilla JS, BEM styling, communicates only with Java.

## Current State

Phase 1 is complete as of 2026-05-11. Phase 2 is complete as of 2026-05-12. The repository now has the contract baseline, service skeletons, local Docker Compose platform, Java auth/session behavior, admin user and role management, access policies, Java-resolved access filters, and Phase 2 audit coverage. Phase 3 is next: document metadata, object storage orchestration, document events, indexing status updates, and expanded audit coverage.

## Constraints

- **Architecture**: Java and Python are separate services with database-per-service ownership.
- **Contracts**: OpenAPI, AsyncAPI, and `constants.yaml` live in top-level `contracts/` as the shared source of truth and are written before implementation.
- **Security**: Retrieval must enforce access level, department, and document type filters before chunks reach generation.
- **RAG Quality**: Evaluation is required; RAGAS, retrieval metrics, injection probes, and ablation are part of done.
- **Budget**: LLM/embedding choices should work with free or conditional-free tiers and preserve an on-premise story.
- **Deployment**: MVP runs through Docker Compose with internal-contour assumptions.
- **Frontend**: Vanilla HTML5/CSS3/JavaScript; no utility CSS framework.
- **Timeline**: Scope should fit a solo-developer MVP around 10-12 weeks.

## Locked Decisions

<decisions status="locked">

- **ADR-001**: Use `BAAI/bge-m3` for dense 1024-dimensional and learned sparse embeddings in one pipeline.
- **ADR-002**: Use Qdrant for dense+sparse vector storage and payload-filtered retrieval.
- **ADR-003**: Split Java Spring backend and Python AI service; frontend talks only to Java; Java/Python communicate by REST for queries and RabbitMQ for indexing.
- **Contract location**: Shared YAML contracts live in top-level `contracts/`; Java and Python both consume that source rather than owning separate service-local YAML.
- **Contract constants**: Routing keys, queue names, exchange names, and error codes live in `contracts/constants.yaml` and generate Java/Python constants.

</decisions>

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| bge-m3 embeddings | Multilingual ru+en support, dense+sparse in one model, MIT license | — Pending |
| Qdrant vector DB | Native hybrid query, payload filters for RBAC, simple Docker setup | — Pending |
| Java + Python split | Each language handles its strong domain: Spring enterprise backend and Python ML/RAG | — Pending |
| Neo4j graph store | Enables entity/relation modeling for multi-hop and aggregation questions | — Pending |
| LangGraph agent | Provides explicit state machine and conditional routing for retrieval/generation | — Pending |
| RabbitMQ indexing | Long-running indexing needs retry, DLQ, and asynchronous delivery | — Pending |

---
*Last updated: 2026-05-12 after completing Phase 2*
