# Synthesized Context

Source classifications: `.planning/intel/classifications/`

## Project Intent

- source: `docs/CONTEXT.md`
- The project is a corporate RAG assistant for internal company use. Employees ask natural-language questions over corporate documents and receive answers with mandatory source citations.
- The project is both a diploma project and a portfolio project. It should demonstrate modern RAG, enterprise backend architecture, and measurable evaluation rather than a tutorial chatbot.

## Scope and Constraints

- source: `docs/CONTEXT.md`, `docs/ARCHITECTURE.md`
- Solo developer, target MVP window around 10-12 weeks.
- MVP corpus is 30-50 documents, later expandable to 500+ documents.
- LLM usage should prefer free or conditionally free tiers such as Gemini Free and OpenRouter `:free`.
- Deployment target is Docker Compose in an internal/on-premise style environment.
- The system should be defensible academically through architecture decisions, ablation results, guard metrics, and traces.

## System Shape

- source: `docs/CONTEXT.md`, `docs/ARCHITECTURE.md`
- Java Spring Backend is the BFF and enterprise state owner.
- Python AI Service is the RAG and ML owner.
- Frontend SPA talks only to Java.
- Java and Python use REST for user query latency and RabbitMQ for asynchronous indexing.
- Files are stored in MinIO.
- Qdrant stores dense+sparse chunk vectors; Neo4j stores entity/relation graph data.

## Engineering Pattern Baseline

- source: `docs/PATTERNS.md`
- Required patterns include contract-first, separate contract module, compile-time safety, schema as API, versioning, adapter/service/domain/repository layering, DTO separation, validation at boundaries, centralized error handling, Problem Details, HATEOAS, pagination, explicit filters, event envelopes, routing key constants, outbox, idempotent consumers, DLQ, and one source of truth.

## Open Questions Carried Forward

- source: `docs/ARCHITECTURE.md`
- JWT TTL defaults to 30 minutes access and 7 days refresh unless revisited.
- Document `uploaded_by` defaults to a foreign key.
- Streaming answers through SSE are deferred; MVP waits for full answer.
- MVP UI language defaults to Russian only.
- User registration is admin-only in MVP.
- Conversations are private in MVP.
- Document versioning defaults to overwrite in MVP, richer versioning later.
- Embedding compute defaults to HuggingFace Inference API for MVP, with local/on-premise path for the diploma demo.
- Langfuse uses its own Postgres service.
- Qdrant/Neo4j backups are future work for MVP.

## ADR Process Context

- source: `docs/decisions/README.md`, `docs/decisions/ADR-template.md`
- ADRs are used for decisions affecting multiple components, involving nontrivial alternatives, or needing future explanation.
- Accepted ADRs are immutable except for superseding updates.
- Likely future ADRs include sparse retrieval, Graph RAG dependency strategy, chunking strategy, outbox polling vs CDC, JWT vs sessions, embedding hosting, and reranker hosting.
