# Synthesized Decisions

Source classifications: `.planning/intel/classifications/`

## Locked ADR Decisions

### ADR-001: Embedding model — bge-m3

- source: `docs/decisions/ADR-001-embedding-model.md`
- status: Accepted
- locked: true
- scope: Python AI Service ingestion and retrieval, Qdrant hybrid search
- decision: Use `BAAI/bge-m3` as the embedding model for both dense and learned sparse representations.
- implementation constraints:
  - Dense vector size is 1024.
  - Learned sparse output replaces a separate BM25 production index.
  - Dense and sparse vectors are stored in one Qdrant point.
  - BM25 remains as an evaluation baseline, not the production retriever.
- rejected alternatives:
  - Qwen3-Embedding-8B, because it lacks built-in sparse retrieval and would require a separate BM25 path.
  - OpenAI `text-embedding-3-large`, because it creates a paid vendor dependency and weakens on-premise positioning.
  - `intfloat/multilingual-e5-large`, because it is dense-only.

### ADR-002: Vector database — Qdrant

- source: `docs/decisions/ADR-002-vector-database.md`
- status: Accepted
- locked: true
- scope: Python AI Service indexing and retrieval
- decision: Use Qdrant as the vector database for dense + sparse chunk embeddings and payload-filtered retrieval.
- implementation constraints:
  - Run Qdrant through Docker using `qdrant/qdrant:latest`.
  - Use one collection named `documents_chunks`.
  - Configure dense vector search with Cosine distance.
  - Store learned sparse vectors in the same collection.
  - Create payload indexes for `documentId`, `language`, `docType`, `department`, and `accessLevel`.
  - Apply RBAC retrieval filtering through Qdrant payload filters.
- rejected alternatives:
  - Weaviate, because it is heavier than required.
  - Milvus, because its Docker topology is too complex for the target corpus.
  - pgvector, because it weakens database-per-service boundaries and lacks the desired native hybrid path.
  - Chroma, because it is not production-grade enough for this project.

### ADR-003: Разделение Java и Python — два сервиса

- source: `docs/decisions/ADR-003-java-python-split.md`
- status: Accepted
- locked: true
- scope: whole-system service architecture
- decision: Split the system into a Java Spring backend and a Python AI service.
- implementation constraints:
  - Java Spring Backend owns auth, RBAC, users, document metadata, chat history, audit, PostgreSQL, and MinIO orchestration.
  - Python AI Service owns parsing, chunking, embeddings, retrieval, reranking, generation, guards, evaluation, Qdrant, and Neo4j.
  - Frontend communicates only with Java.
  - Java calls Python synchronously over REST for user queries.
  - Java and Python communicate asynchronously through RabbitMQ for document indexing.
  - Services follow database-per-service boundaries.
- rejected alternatives:
  - Single Java service for ML, because the required ML ecosystem is Python-native.
  - Single Python service, because it would not satisfy the project goal of demonstrating Spring enterprise patterns.

## Additional Non-Locked Decision Signals

### Graph database

- source: `docs/CONTEXT.md`, `docs/ARCHITECTURE.md`
- locked: false
- decision signal: Use Neo4j Community for the knowledge graph because it is an industry-standard graph database with Cypher and built-in visualization.

### LLM layer

- source: `docs/CONTEXT.md`, `docs/ARCHITECTURE.md`
- locked: false
- decision signal: Use Gemini 2.0 Flash Lite for answer generation, DeepSeek V3 through OpenRouter `:free` as fallback/query router/input guard, and Gemini 2.0 Flash for entity/relation extraction.

### Agent orchestration

- source: `docs/CONTEXT.md`, `docs/ARCHITECTURE.md`
- locked: false
- decision signal: Use LangGraph StateGraph for query orchestration with conditional routing across guard, hybrid, graph, rerank, synthesis, and output-guard nodes.

### Frontend implementation

- source: `docs/ARCHITECTURE.md`
- locked: false
- decision signal: Use a vanilla HTML5/CSS3/JavaScript SPA, BEM CSS methodology, no utility CSS, and communication only through the Java backend.
