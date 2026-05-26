# corp-rag

Корпоративная RAG-система для внутреннего поиска и обобщения информации по документам компании.

> **Статус:** в разработке. Pet-проект + дипломная работа. Solo-разработчик, целевой горизонт ~12 недель.

## Что это

AI-ассистент, который отвечает на вопросы сотрудников по корпоративным документам. Не "ещё один чат-бот" — отличия:

- **Гибридный поиск** — dense embeddings + learned sparse + RRF + cross-encoder reranker
- **Графовая база знаний** — извлечение сущностей и связей в Neo4j → понимание "как A связано с B"
- **Agentic routing** — запрос классифицируется и направляется в подходящий retriever
- **Многоуровневая защита от prompt injection** — regex Tier-0 → LLM-классификатор → XML-изоляция контекста
- **RBAC** — фильтрация результатов поиска по правам пользователя на уровне векторной БД

## Стек

| Слой | Технология |
|---|---|
| Backend | Java 21 + Spring Boot 3.3 |
| AI-сервис | Python 3.12 + FastAPI + LangGraph |
| Frontend | Vanilla HTML5 + CSS3 + ES2022+ |
| Хранилища | PostgreSQL · Qdrant · Neo4j · MinIO |
| Брокер | RabbitMQ |
| Embedding | bge-m3 (dense + sparse) |
| LLM | Gemini 2.0 Flash Lite, DeepSeek V3 (OpenRouter) |

## Документация

Начни здесь:

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — полная архитектура системы (источник истины)
- **[docs/PATTERNS.md](docs/PATTERNS.md)** — паттерны программирования, которым следуем
- **[docs/CONTEXT.md](docs/CONTEXT.md)** — краткая сводка проекта (для быстрого онбординга)
- **[docs/decisions/](docs/decisions/)** — Architecture Decision Records
- **[ROADMAP.md](ROADMAP.md)** — milestone'ы, эпики, прогресс
- **[CLAUDE.md](CLAUDE.md)** — постоянный контекст для AI-ассистента (Claude Code)

## Структура

```
corp-rag/
├── docs/             # документация и ADR
├── backend/          # Java Spring сервис
├── ai-service/       # Python AI сервис
├── frontend/         # SPA на vanilla HTML/CSS/JS
└── infra/            # docker-compose, скрипты деплоя
```

## Запуск

Локальный compose поднимает Java API, Python AI, frontend и инфраструктуру:

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

Основные URL:

- Frontend: http://localhost
- Java API: http://localhost:8080
- Python AI: http://localhost:8000

Frontend вызывает только Java API (`http://localhost:8080/api/v1` по умолчанию). Для другого окружения можно задать `window.CORP_RAG_API_BASE` до загрузки `frontend/js/app.js`.

## Лицензия

MIT (будет добавлено).
