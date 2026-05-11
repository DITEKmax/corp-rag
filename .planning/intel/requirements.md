# Synthesized Requirements

Source classifications: `.planning/intel/classifications/`

## Product Requirements

### REQ-PROD-01: Internal cited RAG assistant

- source: `docs/CONTEXT.md`, `docs/ARCHITECTURE.md`
- description: Employees can ask natural-language questions over corporate documents and receive answers grounded in available source documents.
- acceptance criteria:
  - Answers include citations to source document chunks or sections.
  - The assistant answers on the language of the user query.
  - If available documents do not contain the answer, the assistant says so instead of inventing.
- scope: chat, citations, RAG answer generation

### REQ-PROD-02: Enterprise access control

- source: `docs/CONTEXT.md`, `docs/ARCHITECTURE.md`
- description: The system authenticates users, assigns roles, and enforces document access rights before retrieval.
- acceptance criteria:
  - Users authenticate through the Java backend.
  - Roles contain permissions and access policies.
  - Retrieval filters by access level, department, and document type.
  - Users never receive chunks they are not allowed to access.
- scope: authentication, authorization, RBAC, access filters

### REQ-PROD-03: Document lifecycle management

- source: `docs/ARCHITECTURE.md`
- description: Authorized users can upload, list, view, and delete documents with metadata.
- acceptance criteria:
  - Uploaded files are stored in MinIO.
  - Metadata is stored in Java-owned PostgreSQL.
  - Document status moves through uploaded, indexing, indexed, or failed states.
  - Raw documents are exposed through presigned URLs rather than direct file serving.
- scope: documents, MinIO, metadata, status tracking

### REQ-PROD-04: Asynchronous document indexing

- source: `docs/ARCHITECTURE.md`
- description: Document indexing runs asynchronously through RabbitMQ and reports completion or failure back to Java.
- acceptance criteria:
  - Java publishes `document.uploaded` and `document.deleted` events.
  - Python consumes upload/delete events idempotently.
  - Python publishes `document.indexed` or `document.indexing.failed`.
  - Failed events include stage-aware error details.
- scope: RabbitMQ, indexing events, outbox, idempotent consumers

### REQ-PROD-05: Hybrid and graph retrieval

- source: `docs/CONTEXT.md`, `docs/ARCHITECTURE.md`
- description: Queries can retrieve evidence using hybrid vector search, graph traversal, parent resolution, and reranking.
- acceptance criteria:
  - Hybrid retrieval combines dense and learned sparse bge-m3 vectors through Qdrant RRF.
  - Graph local/global retrievers can support multi-hop, aggregation, and comparison questions.
  - Parent chunks are resolved before answer synthesis.
  - Cross-encoder reranking reduces retrieved evidence to the final context.
- scope: Qdrant, Neo4j, hybrid retrieval, Graph RAG, reranking

### REQ-PROD-06: Agentic query routing

- source: `docs/CONTEXT.md`, `docs/ARCHITECTURE.md`
- description: The AI service classifies query intent and routes each query to the appropriate retriever path.
- acceptance criteria:
  - Router recognizes factual lookup, aggregation, multi-hop, comparison, and unsupported classes.
  - Router returns the selected retriever path in retrieval metadata.
  - Unsupported or unsafe requests do not proceed to normal answer generation.
- scope: LangGraph, query router, retrieval metadata

### REQ-PROD-07: Prompt injection protection

- source: `docs/CONTEXT.md`, `docs/ARCHITECTURE.md`
- description: The system protects user input, corpus chunks, prompts, and outputs against prompt injection and unsafe disclosure.
- acceptance criteria:
  - Tier-0 regex guard can block known injection patterns.
  - Corpus chunks are sanitized during indexing and unsafe chunks are excluded from retrieval.
  - Tier-1 LLM classifier produces structured safety classes.
  - Retrieved context is isolated from instructions in the generation prompt.
  - Output guard checks citation presence and PII patterns.
- scope: input guard, corpus sanitizer, LLM guard, XML prompt isolation, output guard

### REQ-PROD-08: Conversation workflow

- source: `docs/ARCHITECTURE.md`
- description: Users can create conversations, ask questions, view message history, and inspect cited chunks.
- acceptance criteria:
  - Java stores conversations and messages.
  - Query responses include answer, citations, confidence, conversation ID, message ID, and retrieval metadata.
  - Citation viewer can fetch the cited chunk and raw document link.
  - Conversations are private in MVP.
- scope: chat, conversations, messages, citations

### REQ-PROD-09: Admin workflows

- source: `docs/ARCHITECTURE.md`
- description: Admin users can manage users, roles, access policies, and documents through the Java API and frontend.
- acceptance criteria:
  - Users and roles have CRUD endpoints.
  - Role assignment and removal are supported.
  - Document management supports filters, pagination, upload, raw access, and delete.
  - Frontend includes admin screens for documents, users, and roles.
- scope: admin UI, users, roles, documents

### REQ-PROD-10: Quality evaluation

- source: `docs/CONTEXT.md`, `docs/ARCHITECTURE.md`
- description: The project demonstrates RAG quality and safety with measurable evaluation artifacts.
- acceptance criteria:
  - Golden dataset contains factual, aggregation, multi-hop, and out-of-scope examples.
  - RAGAS metrics cover faithfulness, answer relevancy, context precision, and context recall.
  - Retrieval metrics include recall@5, recall@10, and MRR.
  - Injection probes measure guard block rate.
  - Ablation compares BM25, dense, sparse, hybrid, and hybrid+reranker.
- scope: evaluation, golden dataset, RAGAS, retrieval metrics, injection probes

### REQ-PROD-11: Local deployment and observability

- source: `docs/CONTEXT.md`, `docs/ARCHITECTURE.md`
- description: The MVP runs through Docker Compose in an internal/on-premise style environment with observability.
- acceptance criteria:
  - Compose starts Java, Python, frontend, PostgreSQL, MinIO, RabbitMQ, Qdrant, Neo4j, Langfuse, Prometheus, and Grafana services as needed.
  - Health/readiness endpoints indicate service dependencies.
  - Langfuse traces LLM chains.
  - Prometheus/Grafana expose service metrics.
- scope: Docker Compose, health checks, observability

## Implementation Epics Extracted From Source

- source: `docs/ARCHITECTURE.md`
- epics:
  1. Infrastructure & Setup
  2. Contracts
  3. Java Auth + Users
  4. Java Documents + MinIO
  5. Java Outbox + AMQP Publisher
  6. Java AMQP Consumers
  7. Java Chat + AiServiceClient
  8. Java Audit + RootController
  9. Python Skeleton + Contracts
  10. Python Ingestion
  11. Python AMQP Consumer
  12. Python Retrieval
  13. Python Guards
  14. Python Agent
  15. Python Query API
  16. Frontend Foundation
  17. Frontend Login + Layout
  18. Frontend Chat
  19. Frontend Admin
  20. Evaluation
  21. Observability + Polish
  22. Deploy and final regression
