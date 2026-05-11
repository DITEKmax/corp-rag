# Synthesized Technical Constraints

Source classifications: `.planning/intel/classifications/`

## Architecture Constraints

### Service ownership

- source: `docs/ARCHITECTURE.md`, `docs/decisions/ADR-003-java-python-split.md`
- type: nfr
- constraint: Java owns user/access/document/chat/audit state; Python owns AI/RAG state; frontend communicates only with Java.

### Database per service

- source: `docs/ARCHITECTURE.md`, `docs/PATTERNS.md`, `docs/decisions/ADR-003-java-python-split.md`
- type: nfr
- constraint: Each service owns its own database. Java must not connect directly to Qdrant/Neo4j, and Python must not own Java domain metadata.

### Contract-first implementation

- source: `docs/ARCHITECTURE.md`, `docs/PATTERNS.md`
- type: api-contract
- constraint: OpenAPI, AsyncAPI, and constants manifests are written before implementation and generate Java DTOs/constants and Python Pydantic models/constants.

### Layered responsibility

- source: `docs/ARCHITECTURE.md`, `docs/PATTERNS.md`
- type: nfr
- constraint: Transport layers map and validate only; use cases live in service layers; domain rules stay out of adapters and repositories.

## API Contract Constraints

### Java REST API

- source: `docs/ARCHITECTURE.md`
- type: api-contract
- constraint: Java exposes `/api/v1` JSON endpoints for auth, users, roles, documents, chat, and root discovery.

### Python internal REST API

- source: `docs/ARCHITECTURE.md`
- type: api-contract
- constraint: Python exposes internal `/v1/query`, `/v1/documents/{docId}/chunks/{chunkId}`, `/health`, and `/ready` endpoints for Java.

### Error format

- source: `docs/ARCHITECTURE.md`, `docs/PATTERNS.md`
- type: api-contract
- constraint: REST errors use RFC 7807 Problem Details with `type`, `title`, `status`, `detail`, `instance`, `errorCode`, `correlationId`, and optional validation errors.

### HATEOAS and root entry point

- source: `docs/ARCHITECTURE.md`, `docs/PATTERNS.md`
- type: api-contract
- constraint: Java responses expose discoverable `_links`, especially document, conversation, citation, and root responses.

## Event and Messaging Constraints

### RabbitMQ topology

- source: `docs/ARCHITECTURE.md`
- type: protocol
- constraint: Use topic exchange `corp-rag.documents` with upload/delete events to Python and indexed/failed events back to Java.

### Event envelope

- source: `docs/ARCHITECTURE.md`, `docs/PATTERNS.md`
- type: protocol
- constraint: All events use metadata containing `eventId`, `eventType`, `eventVersion`, `occurredAt`, `correlationId`, and `sourceService`.

### Outbox for critical publication

- source: `docs/ARCHITECTURE.md`, `docs/PATTERNS.md`
- type: nfr
- constraint: Critical document events are published through a Java outbox table and scheduled publisher.

### Idempotent consumers and DLQ

- source: `docs/ARCHITECTURE.md`, `docs/PATTERNS.md`
- type: nfr
- constraint: Consumers record processed event IDs and queues have dead-letter exchanges/queues.

## Data Constraints

### Java PostgreSQL schema

- source: `docs/ARCHITECTURE.md`
- type: schema
- constraint: Java schema includes users, roles, user_roles, documents, conversations, messages, audit_events, outbox_events, and processed_events.

### Qdrant collection schema

- source: `docs/ARCHITECTURE.md`, `docs/decisions/ADR-002-vector-database.md`
- type: schema
- constraint: Qdrant collection `documents_chunks` stores dense vector `dense` size 1024, sparse vector `sparse`, and payload fields for chunk/document metadata and RBAC filters.

### Neo4j graph schema

- source: `docs/ARCHITECTURE.md`
- type: schema
- constraint: Neo4j stores Entity, Document, and Chunk nodes with RELATES, MENTIONED_IN, and BELONGS_TO relationships.

### Python-side Postgres schema

- source: `docs/ARCHITECTURE.md`
- type: schema
- constraint: Python stores only processed_events and ingestion_state for idempotency and indexing progress.

## Security Constraints

### Authentication

- source: `docs/ARCHITECTURE.md`
- type: nfr
- constraint: Passwords use BCrypt; JWT uses HS256 with env secret; cookies are HttpOnly, Secure, SameSite=Strict, and Path=/.

### Authorization

- source: `docs/ARCHITECTURE.md`
- type: nfr
- constraint: Java computes an AccessFilter from the authenticated user and Python applies it to Qdrant and Neo4j retrieval paths.

### Prompt injection defense

- source: `docs/ARCHITECTURE.md`
- type: nfr
- constraint: Guards must include Tier-0 regex, Tier-1 LLM classifier, XML context isolation, and optional output checks for citations and PII.

### Complexity limits

- source: `docs/ARCHITECTURE.md`, `docs/PATTERNS.md`
- type: nfr
- constraint: Java limits chat queries to 30 req/min per user and upload size to 50 MB; Python limits query length to 2000 chars, LLM calls to 30s, reranking to 5s, and retriever top-k to 20.

## Frontend Constraints

### Vanilla SPA

- source: `docs/ARCHITECTURE.md`
- type: nfr
- constraint: Frontend uses semantic HTML5, CSS3 with BEM, vanilla ES modules, Fetch API, optional EventSource, and no utility CSS framework.

## Evaluation Constraints

### RAG quality gate

- source: `docs/ARCHITECTURE.md`, `docs/CONTEXT.md`
- type: nfr
- constraint: Evaluation uses RAGAS, retrieval metrics, injection probes, and an ablation baseline before project completion.
