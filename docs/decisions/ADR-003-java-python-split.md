# ADR-003: Разделение Java и Python — два сервиса

- **Статус:** Accepted
- **Дата:** 2026-05-11
- **Затронутые компоненты:** вся система (архитектурное решение верхнего уровня)

## Контекст

Изначальный план реализации был полностью на Python (FastAPI + Streamlit). По требованию проекта (показать enterprise-уровень бэкенда, применить паттерны Spring) backend нужно делать на **Java Spring**, а ИИ-часть — на Python.

Возникает вопрос: **как разделить ответственности?**

Возможные подходы:
- A. Один Java-сервис, ML-работа через Java-обёртки (DJL, ONNX Runtime Java).
- B. Один Python-сервис, бэкенд тоже на Python (FastAPI + SQLAlchemy + Authlib), как было изначально.
- C. **Два сервиса**: Java для бэкенда, Python для AI-пайплайна.

Ограничения и обстоятельства:
- Solo-разработчик, ~12 недель.
- Дипломный проект — важна архитектурная зрелость, демонстрация enterprise-паттернов.
- ML-экосистема (bge-m3, FlagEmbedding, LangGraph, RAGAS, docling) — нативно Python.
- Spring-экосистема (Security, JPA, AMQP, Bean Validation) — нативно Java.
- Frontend задан как vanilla HTML/CSS/JS — без проблем общаться с любым из языков.

## Решение

**Два сервиса:**

1. **Java Spring Backend** (port 8080)
   - Auth, RBAC, пользователи, метаданные документов, история чатов, аудит
   - Owner: PostgreSQL, MinIO (для загрузки файлов)
   - Публикует события в RabbitMQ
   - Frontend ходит **только** в этот сервис

2. **Python AI Service** (port 8000)
   - Весь RAG-пайплайн: parsing, chunking, embedding, retrieval, reranking, generation, guards, evaluation
   - Owner: Qdrant, Neo4j, свой минимальный Postgres (только для idempotency processed_events)
   - Внутренний сервис, наружу не выставляется

**Связь:**
- **REST sync** (Java → Python) для запросов пользователя — нужна низкая задержка
- **RabbitMQ async** (Java ↔ Python) для индексации документов — длится минуты, может падать, нуждается в retry/DLQ

## Альтернативы

### Альтернатива A: Один Java-сервис, ML через Java-обёртки
- За: один язык, одна сборка, проще деплой.
- Против:
  - DJL/ONNX Runtime Java живые, но экосистема в разы беднее Python.
  - bge-m3 требует FlagEmbedding (Python-only). На Java придётся либо экспортировать в ONNX и терять часть качества, либо звать Python всё равно.
  - LangGraph — Python-only, аналога на Java нет.
  - RAGAS — Python-only.
  - docling — Python-only.
  - Получится Java-сервис, постоянно вызывающий Python через subprocess или JEP/Jython — хуже всех вариантов.
- **Вердикт:** отвергнуто — теряем 80% ML-экосистемы.

### Альтернатива B: Один Python-сервис (FastAPI + SQLAlchemy + Authlib)
- За: один язык, проще deploy, меньше сложности коммуникации между сервисами.
- Против:
  - Не показывает работу со Spring (это **требование** дипломки для архитектурно-сильного проекта).
  - FastAPI отличный фреймворк, но не имеет такой "ребровой" enterprise-стандартизации, как Spring (HATEOAS, Bean Validation, JPA, Spring Security, Spring HATEOAS, Spring AMQP).
  - Меньше материала для архитектурной части отчёта (паттерны типа Outbox + Spring Security + HATEOAS — это сильная сторона Spring).
- **Вердикт:** отвергнуто — не соответствует целям проекта.

### Альтернатива C (выбрана): два сервиса
- За:
  - Каждый язык на своей сильной стороне (Java — enterprise бэкенд, Python — ML).
  - Чисто разделённые БД (PostgreSQL у Java, Qdrant + Neo4j у Python) — реализуется паттерн **Database per service**.
  - Можно реально применить event-driven паттерны (Outbox, Event Envelope, Idempotent Consumer, DLQ) — это даст контент в отчёт.
  - Frontend по сути BFF-pattern: общается только с Java, не дублирует auth.
- Против:
  - Сложнее в setup (два деплоймента, два процесса).
  - Контракты надо синхронизировать между языками (OpenAPI codegen помогает).
  - Больше точек отказа (но это решается health checks и retry-семантикой).
- **Вердикт:** принято.

## Последствия

### Что получаем
- **Архитектурная зрелость на защите.** Можно показывать sequence-диаграммы с REST + AMQP, рассуждать про CAP, доставку, идемпотентность.
- **Реальное применение всех 35 паттернов** из `PATTERNS.md`, особенно event-driven (Outbox, Idempotent Consumer, DLQ, Event Envelope, Routing Keys as Constants).
- **Database per service** — реальное, а не на словах.
- **Возможность масштабировать сервисы независимо.** Если индексация — узкое место, можно поднять 3 инстанса Python AI service. Java backend — 1 инстанс.
- **Чистое portfolio** — два разнотипных репозитория (или подмодуля): Spring и Python-ML. Каждый можно показать релевантному работодателю.

### Чем платим
- **Сложность инфраструктуры.** Docker Compose с ~9 контейнерами вместо ~6.
- **Время на синхронизацию контрактов.** OpenAPI/AsyncAPI YAML нужно держать в актуальном состоянии для обеих сторон. Митигируется codegen для обоих языков.
- **Cross-service отладка.** Когда что-то ломается, нужно смотреть логи в обоих сервисах + Langfuse. Митигируется correlation ID, который пробрасывается через `EventEnvelope.metadata.correlationId` и HTTP-заголовок.
- **Двойной CI.** Java и Python собираются и тестируются раздельно. Не критично.
- **Дублирование некоторых "тривиальных" фрагментов.** Например, RFC 7807 формат ошибок надо реализовать в обоих сервисах (но контракт ошибок один и тот же).

### Что должно произойти если выбор окажется неправильным
Сигналы:
- Слишком много времени тратится на синхронизацию контрактов — реализация эпиков буксует.
- Координация двух сервисов отъедает > 30% времени по сравнению с одноязычным вариантом.

Стоимость возврата:
- Очень высокая. Возврат к моноязыку (Python) означает переписать **весь** backend с нуля. Это разумно только на старте.

Решение: контрольная точка после **Milestone M1 (Skeleton)** — если к концу 2-й недели сервисы не общаются базово, серьёзно пересмотреть.

## Ссылки

- Паттерн Database per service: https://microservices.io/patterns/data/database-per-service.html
- Паттерн Outbox: https://microservices.io/patterns/data/transactional-outbox.html
- Spring Boot 3.3: https://docs.spring.io/spring-boot/3.3/reference/
- FastAPI: https://fastapi.tiangolo.com/
