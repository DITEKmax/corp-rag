# ROADMAP

> Прогресс по проекту. Отмечай галочками `[x]` по мере закрытия. Активный эпик помечен стрелкой `← active`.

**Текущий milestone:** M1 — Skeleton
**Общая оценка:** ~42 рабочих дня (8–10 недель full-time, ~12 недель с буфером)

Полная декомпозиция задач внутри каждого эпика — в `docs/ARCHITECTURE.md` раздел 13.

---

## Milestone M1 — Skeleton (неделя 1–2)

**Definition of Done:** инфраструктура поднимается одной командой, пользователь логинится через API, базовые endpoint'ы отдают `405 Method Not Allowed`/`200 OK` где положено, Python health endpoint жив.

- [ ] **EPIC 1: Infrastructure & Setup** (1.5д) ← active
  - docker-compose с PostgreSQL, MinIO, RabbitMQ, Qdrant, Neo4j, Langfuse
  - .env.example, README skeleton
  - API keys получены (Gemini, OpenRouter)
- [ ] **EPIC 2: Contracts** (1.5д)
  - Maven multi-module setup
  - `contracts/openapi/api-v1.yaml` (Auth, Users, Documents, Chat)
  - `contracts/openapi/ai-service-v1.yaml`
  - `contracts/asyncapi/events-v1.yaml`
  - `contracts/constants.yaml`
  - Codegen для Java и Python DTO/constants
- [ ] **EPIC 3: Java — Auth + Users** (3д)
  - Spring Boot skeleton, Flyway, БД-сущности
  - Spring Security + JWT
  - `/auth/login`, `/auth/logout`, `/me`
  - `/users/*`, `/roles/*` CRUD
  - `GlobalExceptionHandler` + Problem Details
- [ ] **EPIC 9: Python — Skeleton + Contracts** (1.5д) **(параллельно с EPIC 3)**
  - FastAPI skeleton, pydantic-settings
  - Pydantic-модели из contracts
  - Langfuse, structlog
  - Health endpoints

---

## Milestone M2 — Documents Flow (неделя 3–5)

**Definition of Done:** админ загружает документ через REST → файл попадает в MinIO → событие через RabbitMQ → Python парсит → chunks в Qdrant → entities в Neo4j → событие назад в Java → статус документа `INDEXED`.

- [ ] **EPIC 4: Java — Documents + MinIO** (3д)
  - Document entity, миграции, repository
  - MinIO интеграция (put/get/presign)
  - `DocumentUploadService`, `DocumentQueryService`
  - `/documents/*` endpoints с HATEOAS
- [ ] **EPIC 5: Java — Outbox + AMQP Publisher** (2д)
  - `outbox_events` таблица + entity
  - `OutboxService`, `OutboxPublisher` (scheduled)
  - AmqpConfig (exchanges, queues, bindings, DLX)
  - `EventEnvelope` builder, сгенерированные `EventRoutingKeys`
- [ ] **EPIC 6: Java — AMQP Consumers** (1.5д)
  - `processed_events` таблица
  - `IdempotentConsumerSupport`
  - `DocumentIndexedConsumer`, `DocumentFailedConsumer`
- [ ] **EPIC 10: Python — Ingestion** (4д) **(самая большая фаза)**
  - MinIO client, docling parser, trafilatura для HTML
  - Chunker (parent + child, semantic)
  - Corpus sanitizer (Tier-0)
  - bge-m3 embedder
  - Qdrant repository + VectorIndexer
  - Entity extractor (Gemini Flash) + deduplication
  - Neo4j repository + GraphIndexer
  - `IngestionService` end-to-end
- [ ] **EPIC 11: Python — AMQP Consumer** (1д) **(параллельно с концом EPIC 10)**
  - aio-pika setup, idempotency table
  - DocumentUploaded/Deleted consumers
  - Event publisher (`document.indexed`, `document.indexing.failed`)

---

## Milestone M3 — Query Flow (неделя 6–8)

**Definition of Done:** пользователь задаёт вопрос через REST → классификатор → router → retrievers → reranker → синтез → ответ с цитатами. Работает на 30+ документах из корпуса.

- [ ] **EPIC 12: Python — Retrieval** (3д)
  - HybridRetriever (Qdrant dense+sparse+RRF)
  - ParentResolver
  - GraphLocalRetriever, GraphGlobalRetriever
  - Reranker (bge-reranker-v2-m3)
  - Access filter применяется везде
- [ ] **EPIC 13: Python — Guards** (1.5д)
  - RegexGuard (Tier-0)
  - LlmGuard (Tier-1 DeepSeek)
  - OutputGuard
  - Injection probes тесты
- [ ] **EPIC 14: Python — Agent (LangGraph)** (2д)
  - AgentState, узлы графа
  - StateGraph сборка + условный routing
  - Визуализация графа
- [ ] **EPIC 15: Python — Query API** (1д)
  - `/v1/query` endpoint
  - `/v1/documents/{id}/chunks/{cid}`
- [ ] **EPIC 7: Java — Chat + AiServiceClient** (2.5д)
  - conversations, messages таблицы
  - `AccessPolicyResolver`
  - `AiServiceClient` (RestClient)
  - `ChatService.query()`
  - `/chat/*` endpoints + rate limit
- [ ] **EPIC 8: Java — Audit + RootController** (1д) **(параллельно)**
  - audit_events таблица + сервис
  - Интеграция в use cases
  - `RootController`

---

## Milestone M4 — UI + Evaluation (неделя 9–11)

**Definition of Done:** пользователь логинится, ведёт диалог с цитатами через UI; админ загружает документы; есть метрики качества (RAGAS + retrieval + injection).

- [ ] **EPIC 16: Frontend — Foundation** (2д)
  - Структура, CSS-каркас, BEM
  - `api/client.js`, router, session, guard
- [ ] **EPIC 17: Frontend — Login + Layout** (1д)
  - LoginPage, app shell
- [ ] **EPIC 18: Frontend — Chat** (2д)
  - ConversationList, ChatMessage, CitationCard, SourceModal
  - ChatInput, ChatPage
- [ ] **EPIC 19: Frontend — Admin** (2д)
  - DocumentsPage + upload
  - UsersPage, RolesPage с RoleEditor
- [ ] **EPIC 20: Evaluation** (2.5д)
  - Сбор корпуса (15 GitLab + 15 синтетических ru)
  - golden_qa.jsonl
  - ragas_runner, retrieval_metrics, injection_runner
  - **BM25 baseline** через `bm25s` для ablation-таблицы

---

## Milestone M5 — Polish + Defense (неделя 12)

**Definition of Done:** README с диаграммой и демо-GIF, ADR для ключевых решений, видео-демо 3 мин, регрессия golden dataset зелёная.

- [ ] **EPIC 21: Observability + Polish** (1.5д)
  - Langfuse декораторы
  - Latency метрики в response
  - README с диаграммой, демо-GIF
  - 5 ключевых ADR в `docs/decisions/`
- [ ] **EPIC 22: Deploy + финал** (1д)
  - Финализация docker-compose
  - Скрипт `make seed-corpus`
  - Финальная регрессия
  - Видео-демо

---

## Что НЕ входит в курсовую (вынесено в диплом)

Эти пункты сознательно остаются за рамкой MVP — на расширение:

- [ ] Self-RAG / self-correction (модель оценивает retrieval, переформулирует запрос)
- [ ] Query decomposition (сложный вопрос → подвопросы → ответы → синтез)
- [ ] Multi-turn conversation memory с summary-подходом
- [ ] Incremental indexing (change detection по hash'у документа)
- [ ] Локальный LLM-деплой через Ollama/vLLM (Qwen2.5-7B) — важно для on-premise
- [ ] Расширенная human evaluation (50 ответов оценивают сокурсники)
- [ ] Корпус 500+ документов (вместо 30–50)
- [ ] Cross-encoder finetuning на своём домене
- [ ] React-фронтенд (вместо vanilla — если найдутся причины)
- [ ] Streaming-ответ Gemini через SSE на фронт

---

## Конвенции работы с этим документом

1. Один эпик — одна feature-ветка: `feature/epic-NN-short-slug`.
2. При старте эпика — отметь стрелкой `← active`. После завершения — `[x]` и убрать стрелку с этого, поставить на следующий.
3. Внутри эпика задачи коммить атомарно (см. `ARCHITECTURE.md` раздел 13).
4. После закрытия milestone — короткая запись в CHANGELOG (создастся когда понадобится).
5. Сдвиги дедлайнов — нормально, главное — фиксировать факт. Можно добавлять `(was: M2 / actual: M3)` в скобках если что-то сдвинулось.

---

## Критический путь

```
M1 Infra → M1 Contracts → [M1 Java Auth, M1 Python Skeleton] (параллельно)
       → M2 Java Documents → M2 Outbox → [M2 Java Consumers, M2 Python Ingestion + AMQP] (параллельно)
       → M3 Python Retrieval → M3 Guards → M3 Agent → M3 Query API
       → M3 Java Chat (зависит от Python Query API готового)
       → M4 Frontend (зависит от Java endpoints)
       → M4 Evaluation → M5 Polish → M5 Defense
```

Узкие места:
- **EPIC 10 (Python Ingestion)** — самая длинная задача, рисковая. Если буксует — упрощать (отложить Graph extraction в EPIC 14, делать только vector).
- **EPIC 14 (LangGraph Agent)** — рисковая по неочевидности. Имеет смысл сначала реализовать без агента (линейная цепочка), потом обернуть в LangGraph.
