# CLAUDE.md — контекст проекта для Claude Code

> Этот файл читается Claude Code при каждом запуске в этой папке. Держи его коротким и точным. Детали — в `docs/ARCHITECTURE.md`.

## О проекте

**corp-rag** — корпоративная RAG-система (Retrieval-Augmented Generation) для поиска и обобщения информации по внутренним документам. Pet-проект + дипломная работа. Solo-разработчик, ~12 недель.

Полная архитектура: **`docs/ARCHITECTURE.md`** — это **источник истины**. При любом конфликте между твоей памятью и этим документом — побеждает документ.

## Технологический стек

| Слой | Технология |
|---|---|
| Backend (бизнес-логика, auth, RBAC) | **Java 21 + Spring Boot 3.3** |
| AI-сервис (RAG-пайплайн) | **Python 3.12 + FastAPI** |
| Frontend | **Vanilla HTML5 + CSS3 + JS (ES2022+)** |
| Хранилища | PostgreSQL, Qdrant, Neo4j, MinIO |
| Брокер | RabbitMQ |
| Embedding | bge-m3 (dense + learned sparse) |
| Reranker | bge-reranker-v2-m3 |
| LLM генерация | Gemini 2.0 Flash Lite (через Google AI Studio free tier) |
| LLM вспомогательные | DeepSeek V3 через OpenRouter `:free` |
| Orchestration AI | LangGraph |

## Структура репозитория

```
corp-rag/
├── docs/
│   ├── ARCHITECTURE.md      # источник истины по архитектуре
│   ├── PATTERNS.md           # паттерны программирования (обязательно следовать)
│   ├── CONTEXT.md            # краткая сводка проекта
│   └── decisions/            # ADR — Architecture Decision Records
├── backend/                  # Java Spring сервис (multi-module Maven)
├── ai-service/               # Python AI сервис
├── frontend/                 # SPA на vanilla HTML/CSS/JS
├── infra/                    # docker-compose, скрипты деплоя
├── ROADMAP.md                # milestones + эпики, чек-лист прогресса
└── CLAUDE.md                 # этот файл
```

## Правила, которые НЕЛЬЗЯ нарушать

1. **Следуй паттернам из `docs/PATTERNS.md`.** Они не декоративные — это решения, принятые до тебя. Если паттерн кажется неудобным для конкретной задачи — НЕ обходи его молча. Подними вопрос пользователю, обсудите, при необходимости — занесите изменение в ADR (`docs/decisions/`).

2. **Контракт первичен.** OpenAPI, AsyncAPI и `constants.yaml` в корневом `contracts/` — единственный источник истины для API, событий, routing keys, queue/exchange names и error codes. Любое изменение endpoint'а, события или контрактной константы начинается с `contracts/`, не с кода.

3. **DTO/contract constants и domain не смешиваются.** DTO и контрактные константы генерируются из `contracts/`, domain-сущности живут в `domain/`. Никогда не отдавай entity наружу через REST.

4. **Database per service.** Java владеет PostgreSQL. Python владеет Qdrant + Neo4j (+ свой минимальный Postgres для idempotency). Никаких JDBC-коннектов из Java в Qdrant и из Python в основную Postgres.

5. **Frontend общается только с Java.** Python наружу не торчит — это внутренний сервис.

6. **Все ошибки — RFC 7807 Problem Details.** Никаких произвольных JSON со строкой `"error": "..."`.

7. **События идут через конверт `EventEnvelope { metadata, payload }`.** Routing keys — только из сгенерированных констант из `contracts/constants.yaml` (`EventRoutingKeys` в Java, `routing_keys.py` в Python).

8. **`document.uploaded` публикуется через Outbox.** Никаких прямых `rabbitTemplate.send()` для критичных событий.

9. **Consumer'ы идемпотентны.** Проверяй `eventId` в таблице `processed_events` перед обработкой.

10. **Атомарные коммиты на каждую задачу.** Один коммит = одна закрытая задача из ROADMAP.md. Conventional Commits: `feat(epic-05): add outbox publisher`.

## Стиль кода

### Java
- Java 21, использовать `record` для DTO и immutable value objects.
- Spring Boot 3.x идиомы (`@RestController`, `@Service`, `@Repository`).
- Конструкторная инъекция, никаких `@Autowired` на полях.
- `Optional` для возможно-отсутствующих значений.
- Lombok минимально (только `@Slf4j`). Записи и явные конструкторы предпочтительнее.
- Maven multi-module. Тесты с Testcontainers для интеграционных.

### Python
- Python 3.12, type hints обязательны на public API.
- Pydantic v2 для всех DTO и settings.
- FastAPI идиомы (`APIRouter`, `Depends`, `BackgroundTasks` где нужно).
- async/await везде где есть I/O.
- `uv` для управления зависимостями.
- pytest + pytest-asyncio.

### Frontend
- ES2022+, ESM модули (`<script type="module">`).
- BEM для CSS-классов: `.message`, `.message__content`, `.message--user`.
- **Никакого** utility CSS (Tailwind, Bootstrap-utility).
- CSS custom properties для темы.
- Никаких фреймворков (React, Vue, Svelte). Vanilla.

## Конвенции именования

### Java пакеты
- `com.corprag.{layer}.{module}` — например, `com.corprag.service.document`.
- Слои: `adapter`, `service`, `domain`, `repository`, `assembler`, `security`, `config`, `shared`.

### Python модули
- snake_case для файлов и модулей.
- `service/`, `pipeline/`, `adapter/`, `domain/`, `repository/`, `agent/`, `shared/`.

### Git branches
- `feature/epic-NN-short-slug` — например, `feature/epic-05-outbox`.
- `fix/epic-NN-short-slug` — багфиксы внутри эпика.
- `chore/short-slug` — инфраструктурные изменения.

### Routing keys (RabbitMQ)
- `document.uploaded`, `document.indexed`, `document.deleted`, `document.indexing.failed`.
- Точечная нотация, всё lowercase.

### Endpoints
- `/api/v1/...` для Java (внешний API).
- `/v1/...` для Python (внутренний API).

## Куда смотреть для типичных задач

| Хочу... | Иди в раздел `ARCHITECTURE.md` |
|---|---|
| Понять как Java вызывает Python | §7.2 Sequence: запрос пользователя |
| Понять как идёт индексация | §7.1 Sequence: загрузка документа |
| Узнать структуру таблиц Postgres | §9.1 |
| Узнать payload события | §8.3 |
| Понять какой паттерн где применён | §12 Карта паттернов |
| Найти следующую задачу | `ROADMAP.md` (текущий milestone) |
| Понять структуру пакетов Java | §4.4 |
| Понять структуру пакетов Python | §5.1 |
| Узнать про защиту от prompt injection | §10.4 |
| Узнать формат system prompt'а | §11.4.1 |

## Прогресс

Текущий milestone: **M1 — Skeleton** (см. `ROADMAP.md`).

Активный эпик отмечается стрелкой в `ROADMAP.md`. После завершения эпика:
1. Отметь его как `[x]` в `ROADMAP.md`.
2. Сделай мерж feature-ветки в `main`.
3. Если по ходу принимались архитектурные решения — добавь ADR в `docs/decisions/`.
4. Обнови `ARCHITECTURE.md`, если фактическая реализация отошла от спецификации (или подними вопрос).

## Когда останавливаться и звать пользователя

- Архитектурное решение, не описанное в `ARCHITECTURE.md`.
- Конфликт между требованиями и паттернами.
- Изменение схемы БД с breaking-эффектом на уже работающие части.
- Необходимость новой внешней зависимости (новая библиотека, новый сервис в docker-compose).
- Тесты ломаются после изменения и не очевидно почему.

Не молча "пофиксить" — обсудить.

## Команды (будут добавляться по ходу)

> Этот раздел заполняется по мере того, как появляется инфраструктура. Сейчас пусто.

```bash
# Поднять локальную инфраструктуру (появится в Epic 1)
# cd infra && docker compose up -d

# Сборка Java-бэкенда (появится в Epic 2)
# cd backend && ./mvnw clean package

# Запуск Python-сервиса (появится в Epic 9)
# cd ai-service && uv run uvicorn corp_rag_ai.main:app --reload

# Запуск фронтенда (появится в Epic 16)
# cd frontend && python -m http.server 8081
```

---

**Резюме одной фразой:** делай как описано в `docs/ARCHITECTURE.md`, следуй паттернам из `docs/PATTERNS.md`, отмечай прогресс в `ROADMAP.md`, фиксируй важные решения в `docs/decisions/`, спрашивай при сомнениях.
