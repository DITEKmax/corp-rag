# Паттерны программирования

> Этот документ — компас. Если что-то в коде кажется неправильным, скорее всего ты нарушаешь один из этих паттернов. Все паттерны применяются обоими сервисами (Java и Python), если не указано иное.

Каждый паттерн содержит:
- **Суть** — что это значит.
- **Где применён** — конкретные места в системе.

Маппинг паттерн → конкретный класс/файл — в `ARCHITECTURE.md` раздел 12.

---

## 1. Контракт-первый подход

### Contract-First

**Суть.** Сначала описывается договор между частями системы: какие операции доступны, какие данные принимаются, какие ответы и ошибки возможны. Реализация подчиняется контракту, а не наоборот.

**Где.** OpenAPI и AsyncAPI YAML коммитятся **до** любого кода, который их реализует.

### Отдельный модуль контракта

**Суть.** Контракт вынесен отдельно от реализации: API-модели, интерфейсы, схемы, события, ошибки, routing keys. Все участники подключают один и тот же контракт.

**Где.** Корневой каталог `contracts/` содержит общий YAML/manifest source of truth. Java потребляет его через Maven-модуль `backend/corp-rag-contracts/`, Python — через скрипт генерации Pydantic-моделей и констант.

### Compile-Time Safety

**Суть.** Если часть системы нарушила контракт, это должно обнаруживаться как можно раньше: при сборке, генерации типов, запуске схемы или тестах, а не в продакшене.

**Где.**
- Java: openapi-generator-maven-plugin генерирует DTO; Bean Validation, MapStruct.
- Python: Pydantic v2 валидация на роутерах, codegen из тех же YAML.

### Schema as API

**Суть.** Для GraphQL, AsyncAPI, OpenAPI, Protobuf и подобных подходов схема становится главным контрактом. Она описывает не только данные, но и допустимые операции.

**Где.** OpenAPI/AsyncAPI YAML — единственный источник истины. Документация генерируется из них, DTO генерируются из них, тесты опираются на них.

### Versioning

**Суть.** Контракты меняются. Заранее думаем о версиях API, схем, событий и DTO, чтобы не ломать старых клиентов.

**Где.** `/api/v1/...` префикс. Поле `eventVersion: "1.0"` в `EventEnvelope.metadata`.

---

## 2. Слои и границы

### Adapter Layer

**Суть.** Внешний слой не содержит бизнес-логики. Он только принимает внешний формат запроса и переводит его во внутренний вызов.

**Где.**
- Java: `adapter/rest/` (controllers), `adapter/amqp/` (consumers, publishers), `adapter/client/` (AI service client).
- Python: `adapter/rest/` (FastAPI routers), `adapter/amqp/` (consumers).

### Тонкий Transport Layer

**Суть.** HTTP, GraphQL, RabbitMQ, UI-форма или CLI — это транспорт. Он не должен диктовать доменную модель. Его задача: принять, проверить, преобразовать, передать дальше.

**Где.** Контроллеры в Java и routers в Python никогда не содержат логики дальше валидации и вызова `service`-слоя.

### Service Layer

**Суть.** Бизнес-логика живёт в сервисах/use cases. Один и тот же сервис может использоваться REST API, GraphQL API, обработчиком сообщений или UI.

**Где.** `service/` пакеты в обоих языках. Например, `DocumentUploadService` в Java может вызываться из контроллера, из тестов, в будущем — из CLI.

### Layered Responsibility

**Суть.** Каждый слой отвечает за своё:
- `contract` — договор
- `adapter` — вход/выход
- `service` — сценарий
- `domain` — правила
- `storage`/`repository` — состояние
- `integration` — внешние системы
- `presenter`/`assembler` — публичное представление

**Где.** Пакетная структура обоих сервисов (см. `ARCHITECTURE.md` §4.4, §5.1).

---

## 3. DTO и валидация

### DTO Separation

**Суть.** Входные и выходные модели разделяются.
- Request/Input — то, что приходит извне.
- Response/View/Event — то, что система отдаёт наружу.

Не отдавай entity или внутренние объекты напрямую.

**Где.** Java: DTO в contracts-модуле, entity в `domain/`. Python: Pydantic-модели в `corp_rag_ai/contracts/generated/`, domain-объекты в `domain/`.

### Semantic DTO

**Суть.** Разные действия получают разные модели. Создание, полное обновление, частичное обновление, фильтрация и ответ — это разные смыслы, значит им часто нужны разные DTO.

**Где.** `CreateDocumentRequest` ≠ `UpdateDocumentRequest` ≠ `DocumentResponse` ≠ `DocumentSummary`. Не один универсальный `DocumentDto`.

### Input/Output Type Split

**Суть.** Типы для входа и выхода разделяются. Входные типы не содержат связей и вычисляемых полей, выходные могут содержать связи, метаданные и производные значения.

**Где.** Request-DTO без `id`, `createdAt`, `_links`. Response-DTO с ними.

### PUT/PATCH Semantics

**Суть.** Полная замена и частичное обновление не смешиваются.
- Полная замена требует полный набор данных.
- Частичное обновление меняет только явно переданные поля.

**Где.** `PUT /api/v1/roles/{id}` — полная замена, требует все поля роли. `PATCH /api/v1/users/{id}` — JSON Merge Patch (`application/merge-patch+json`), меняет только переданные.

### Validation at Boundary

**Суть.** Валидация выполняется на границе системы: API, форма, событие, команда. Некорректные данные не должны попадать в бизнес-логику.

**Где.**
- Java: `@Valid` в контроллерах, Bean Validation аннотации в DTO.
- Python: автоматическая валидация Pydantic на роутерах.

### Custom Validation

**Суть.** Если стандартных проверок недостаточно, создаётся доменная валидация: уникальность, формат бизнес-идентификатора, допустимый переход состояния, специфичные правила.

**Где.**
- Java: кастомные аннотации `@UniqueDocumentTitle`, `@ValidStorageKey`.
- Python: `@field_validator` в Pydantic-моделях.

### Custom Scalar / Type Mapping

**Суть.** Если внешний контракт не знает внутренний тип напрямую, вводится явное правило преобразования: дата, UUID, деньги, enum, JSON, binary.

**Где.** UUID представляется как строка в JSON. Даты — ISO-8601 в UTC. Enum'ы — строковые литералы. Деньги (если появятся) — в минимальных единицах + явная валюта.

---

## 4. Ошибки

### Centralized Error Handling

**Суть.** Ошибки приводятся к единому формату. Клиент не должен гадать, что значит произвольный текст ошибки. Для каждого типа ошибки есть понятный код, описание и детали.

**Где.**
- Java: `GlobalExceptionHandler` (`@ControllerAdvice`) + `ProblemDetailFactory`.
- Python: `error_handlers.py` через FastAPI exception handlers.

### Typed Domain Exceptions

**Суть.** Доменная ошибка должна быть отдельным типом, а не случайным `RuntimeException`. Например: ресурс не найден, конфликт уникальности, запрещённый переход состояния.

**Где.**
- Java: `domain/exception/`: `ResourceNotFoundException`, `AccessDeniedException`, `DuplicateResourceException`, `AiServiceUnavailableException`, `DocumentIndexingException`, ...
- Python: `domain/exceptions.py`: тот же набор.

### Consistent Error Contract

**Суть.** Формат ошибок тоже часть контракта. REST использует problem-details, GraphQL — errors с классификацией, очереди — error event или DLQ.

**Где.** Все REST-ответы об ошибках — **RFC 7807 Problem Details**:
```json
{
  "type": "https://corprag.local/problems/document-not-found",
  "title": "Document not found",
  "status": 404,
  "detail": "Document with id '...' does not exist",
  "instance": "/api/v1/documents/...",
  "errorCode": "DOCUMENT_NOT_FOUND",
  "correlationId": "uuid"
}
```
Для очередей — отдельная DLQ + событие `document.indexing.failed` с `errorCode`.

---

## 5. Представление и пагинация

### Hypermedia / Discoverability

**Суть.** Клиенту лучше не зашивать внутренние URL и переходы. Система отдаёт ссылки, доступные действия или схему, чтобы клиент узнавал возможности динамически.

**Где.** Spring HATEOAS, `_links` в ответах. Особенно для `DocumentResponse`, `ConversationResponse`, `Citation`.

### Assembler / Presenter

**Суть.** Преобразование внутренних данных в ответ клиенту выносится отдельно. Там собираются ссылки, представления, форматирование, вложенные данные и публичная форма объекта.

**Где.** Java: `assembler/` пакет. `DocumentAssembler`, `ConversationAssembler`, `MessageAssembler`.

### Pagination Pattern

**Суть.** Любой список должен иметь пагинацию: элементы, номер страницы, размер, всего элементов, всего страниц, признак последней страницы.

**Где.** Единый `PagedResponse<T>` в Java:
```json
{
  "content": [...],
  "page": 0,
  "size": 20,
  "total": 137,
  "totalPages": 7,
  "last": false
}
```
Применяется ко всем list-endpoint'ам.

### Filtering as Contract

**Суть.** Фильтры должны быть явно описаны: query params, input object, search DTO или command object. Не стоит добавлять неявные фильтры "как получится".

**Где.** Java: `DocumentFilter` объект, передаётся через `@ModelAttribute`. Все query параметры явные, в OpenAPI описаны.

### Root Entry Point

**Суть.** У сложного API полезна единая точка входа: корневой endpoint, schema, service registry или metadata endpoint. От неё клиент может узнать доступные ресурсы и операции.

**Где.** `GET /api/v1/` — `RootController`, отдаёт `_links` ко всем коллекциям ресурсов.

### Resolver Pattern

**Суть.** Вложенные или связанные данные загружаются только тогда, когда они реально запрошены. Это снижает лишнюю загрузку и делает API гибче.

**Где.** Python: `parent_resolver.py` — родительские чанки достаются только когда нужно сформировать контекст для LLM, а не при каждом векторном поиске.

### Complexity Limits

**Суть.** Гибкие API нужно ограничивать: глубина запроса, сложность, размер страницы, лимит payload, timeout. Гибкость без ограничений быстро становится DoS-поверхностью.

**Где.**
- Java: Bucket4j 30 req/min на `/chat/query`, max upload 50 MB, max page size 100.
- Python: max query length 2000 chars, LLM timeout 30 сек, reranker timeout 5 сек, top-k cap = 20.

---

## 6. Событийная архитектура

### Event-Driven Decoupling

**Суть.** Когда результат операции нужен другим частям системы, лучше публиковать событие, а не вызывать всех напрямую. Publisher не должен знать consumers.

**Где.** Java публикует `document.uploaded` не зная о Python. Если завтра появится сервис аналитики — он просто подпишется на тот же exchange.

### Event Contract

**Суть.** События тоже имеют контракт: тип события, payload, metadata, версия, routing key. Producer и consumer зависят от одного описания события.

**Где.** AsyncAPI YAML в `contracts/asyncapi/events-v1.yaml`. Из него генерируются Java и Python модели события.

### Event Envelope

**Суть.** Бизнес-событие оборачивается в конверт: metadata + payload. Metadata нужна для трассировки, дедупликации, аудита, маршрутизации и диагностики.

**Где.** Все события идут как:
```json
{
  "metadata": {
    "eventId": "uuid",
    "eventType": "document.uploaded",
    "eventVersion": "1.0",
    "occurredAt": "2026-05-11T10:30:00Z",
    "correlationId": "uuid",
    "sourceService": "backend"
  },
  "payload": { ... }
}
```

### Routing Keys as Constants

**Суть.** Имена маршрутов, topic keys, queue names и event types должны быть общими константами/контрактом, а не строками, раскиданными по коду.

**Где.** `contracts/constants.yaml` — единственный источник routing keys, queue names, exchange names и error codes. Из него генерируются Java `EventRoutingKeys`, `QueueNames`, `ExchangeNames`, `ErrorCodes` и Python `routing_keys.py`, `queue_names.py`, `exchange_names.py`, `error_codes.py`. Никаких `"document.uploaded"` строковых литералов в логике.

---

## 7. Доставка и идемпотентность

### Fire-and-Forget Publication

**Суть.** Если событие вторично по отношению к бизнес-операции, публикация не должна ломать основную операцию. Ошибка логируется, событие может быть потеряно или восстановлено другим механизмом.

**Где.** Audit-события (если будут публиковаться) — fire-and-forget. Основная операция (запись в audit_events таблицу) не должна падать из-за недоступности брокера.

### Outbox for Strong Delivery

**Суть.** Если событие критично, простой fire-and-forget слабоват. Тогда используется outbox: сначала операция и событие сохраняются в одной транзакции, потом отдельный процесс публикует событие в брокер.

**Где.** `document.uploaded`, `document.deleted` — через таблицу `outbox_events` + scheduled `OutboxPublisher`. Гарантия: если документ записан в БД, событие **обязательно** будет опубликовано (eventually).

### Idempotent Consumer

**Суть.** Consumer должен уметь безопасно обработать одно и то же сообщение повторно. Для этого нужен eventId, журнал обработанных событий или проверка текущего состояния.

**Где.**
- Java: `IdempotentConsumerSupport` + таблица `processed_events`. Проверка `eventId` перед обработкой.
- Python: `idempotent.py` + аналогичная таблица в его Postgres.

### Dead Letter Queue

**Суть.** Сообщения, которые не удалось обработать, не должны теряться или бесконечно крутиться. Они уходят в DLQ для анализа и ручного/автоматического восстановления.

**Где.** Каждая queue в RabbitMQ имеет DLX (Dead Letter Exchange) и соответствующую DLQ. Например: `ai.document.uploaded` → `ai.document.uploaded.dlq` после 5 неудачных попыток.

---

## 8. Структура и эволюция

### One Source of Truth

**Суть.** Одинаковые правила не дублируются в разных местах. Если URL, схема события, DTO или ошибка нужны нескольким частям системы, они должны жить в одном источнике.

**Где.**
- Корневой `contracts/` для DTO, событий и контрактных констант.
- Единые enum значения (`AccessLevel`, `DocType`, `Department`) в обоих языках — generated из OpenAPI.
- Routing keys, queue names, exchange names и error codes — generated из `contracts/constants.yaml`.

---

## Чек-лист перед мержом задачи

Перед `git push`/PR пробеги глазами:

- [ ] DTO отдельны от entity?
- [ ] Валидация на границе (контроллер/роутер)?
- [ ] Все ошибки — Problem Details?
- [ ] Если работаешь с событием — есть конверт?
- [ ] Если consumer — проверка `eventId`?
- [ ] Если publish критичного события — через outbox?
- [ ] Если новый endpoint — описан в OpenAPI?
- [ ] Если новое событие — описано в AsyncAPI?
- [ ] Тесты покрывают happy path и хотя бы один error case?
- [ ] Коммит атомарный, с описательным именем?

Если хоть на один "нет" — стоп, разберись или подними вопрос.
