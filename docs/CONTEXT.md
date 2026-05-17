# CONTEXT — краткая сводка проекта

> Этот файл — "лифт-питч" проекта. Прочитав его, можно за минуту понять, что строится и в каких рамках. Подробности — в `ARCHITECTURE.md`.

## Что строим

Корпоративную **RAG-систему** (Retrieval-Augmented Generation) — AI-ассистент для внутреннего использования в компании. Сотрудники задают вопросы на естественном языке по корпоративным документам, система отвечает с обязательным цитированием источников.

## Зачем

1. **Дипломный проект** — необходим серьёзный, технически глубокий проект, с применением современных подходов RAG (hybrid search, Graph RAG, multi-tier guards), готовый защитить.
2. **Pet-проект** — реальный кейс, который можно положить в портфолио и потенциально показать работодателям как enterprise-уровень.

Не учебный туториал. Не "ещё один чат-бот". Это качественная система с проработанной архитектурой, паттернами, evaluation-методологией.

## Ключевые отличия от обычного RAG-чата

| Отличие | Что даёт |
|---|---|
| Гибридный поиск (dense + sparse + RRF + reranker) | Не теряем ни семантику, ни точные термины |
| Графовая БЗ (Neo4j, entity extraction) | Multi-hop вопросы и агрегации работают |
| Agentic routing | Разные типы запросов идут в разные retriever'ы |
| Многоуровневая защита от prompt injection | Tier-0 regex + Tier-1 LLM + XML-разделение контекста |
| RBAC на уровне векторной БД | Пользователь не получает чанк, к которому нет доступа |
| Evaluation с первого дня | RAGAS + retrieval metrics + injection probes |

## Ограничения

- **Solo-разработчик** — никакой команды.
- **~12 недель** на MVP (курсовая), потом ещё на расширения для диплома.
- **Бесплатные/условно-бесплатные LLM** — OpenRouter для DeepSeek и других open-source моделей.
- **Деплой во внутреннем контуре** — Docker Compose, можно on-premise (то есть в дипломе должна быть возможность переключить LLM на локальный через Ollama/vLLM).

## Архитектурное решение

**Три сервиса:**

1. **Java Spring Backend** (port 8080) — auth, RBAC, пользователи, метаданные документов, история чатов, аудит. Владеет PostgreSQL.
2. **Python AI Service** (port 8000) — весь RAG-пайплайн: парсинг, чанкинг, эмбеддинги, retrieval, reranker, генерация, guards. Владеет Qdrant и Neo4j.
3. **Frontend SPA** (port 80, через nginx) — vanilla HTML/CSS/JS, общается **только** с Java.

**Связь:**
- **Frontend ↔ Java** — REST/JSON, JWT в httpOnly cookie.
- **Java ↔ Python** — REST sync для запросов (пользователь ждёт ответ), RabbitMQ async для индексации (длится минуты, может падать, нуждается в retry/DLQ).

**Файлы документов** — в MinIO (S3-compatible).

**Обоснование разделения языков:**
- Java выигрывает в enterprise-фичах (Spring Security, JPA, AMQP).
- Python выигрывает в ML-экосистеме (bge-m3, LangGraph, RAGAS).
- Каждый язык — на своей сильной стороне.

См. также `decisions/ADR-003-java-python-split.md`.

## Ключевой стек по конкретным выборам

| Решение | Почему | ADR |
|---|---|---|
| **bge-m3** для эмбеддингов | Multilingual (ru+en), dense+sparse в одной модели, MIT | ADR-001 |
| **Qdrant** как vector DB | Native hybrid (dense+sparse), фильтры по payload, простой Docker-сетап | ADR-002 |
| **Neo4j Community** для графа | Стандарт индустрии, визуализация из коробки, Cypher | — |
| **DeepSeek V4 Flash via OpenRouter** для генерации | Open-source, 1M контекст, единый OpenAI-compatible API | — |
| **LangGraph** для оркестрации | StateGraph с условным роутингом, нативная визуализация | — |
| **RabbitMQ** для async | Зрелый, проверенный, легко с DLX/DLQ | — |
| **Java + Python** разделение | Каждый на своей экспертизе | ADR-003 |

## Что делает систему "сильной" на защите

1. **Архитектурная зрелость:** Contract-First, DTO Separation, Outbox Pattern, Idempotent Consumer, RFC 7807, HATEOAS — не "учебная архитектура", а enterprise-стандарты.
2. **Ablation-таблица в отчёте:** сравнение BM25 vs Dense vs Sparse vs Hybrid vs Hybrid+Reranker на golden dataset.
3. **Graph RAG:** редко встречается в курсовых, отличает работу от "ещё одного чата".
4. **Многоуровневая защита от prompt injection** с конкретными цифрами на injection probes.
5. **Evaluation с первого дня:** RAGAS + retrieval metrics + injection block rate.
6. **CI с регрессией:** GitHub Actions запускает eval на каждый PR.
7. **Langfuse traces** на защите — реальные трассировки LLM-цепочек.

## Объём в цифрах

- **Сервисов:** 3 + инфраструктура (PostgreSQL, MinIO, RabbitMQ, Qdrant, Neo4j, Langfuse) = 9 Docker-контейнеров.
- **Эпиков:** 22.
- **Атомарных задач:** ~85.
- **Milestone'ов:** 5.
- **Документов в корпусе для MVP:** 30–50 (15 GitLab Handbook + 15–20 синтетических русских + 5 с внедрёнными injection-паттернами для тестирования).
- **Golden dataset для evaluation:** 30–50 пар вопрос-ответ-источник.
- **Injection probes:** 20+ атак.

## Структура работы

См. `ROADMAP.md` для milestone-разбивки.
