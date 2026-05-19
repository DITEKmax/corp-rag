# Architecture Decision Records

> Каждое важное архитектурное решение фиксируется здесь как отдельный файл. Это история мышления — почему выбрано именно так, а не иначе.

## Что такое ADR

ADR (Architecture Decision Record) — короткий документ (~1 страница), описывающий:
- **Контекст** — что случилось, какая проблема стоит
- **Решение** — что мы выбрали
- **Альтернативы** — что рассматривалось и почему отвергнуто
- **Последствия** — что мы получаем (хорошее) и чем платим (плохое)

ADR нужны для **будущего тебя через 3 месяца** (и для защиты дипломки). Они отвечают на вопрос "почему здесь именно так?".

## Когда создавать новый ADR

Создавай ADR, когда принимаешь решение, которое:
- Затрагивает несколько компонентов системы
- Имеет нетривиальные альтернативы (это не "выбрал HashMap вместо LinkedHashMap")
- Имеет необратимые последствия (миграция в другую БД, смена контракта)
- Будет нужно объяснять кому-то ещё (научнику, комиссии, будущему себе)
- Принимается в моменте, и через месяц забудешь почему

Не создавай ADR для:
- Стиля кода (это в линтере и `PATTERNS.md`)
- Очевидных выборов ("используем git")
- Микро-решений внутри одного класса

## Как создать новый ADR

1. Скопируй `ADR-template.md`.
2. Назови: `ADR-NNN-short-slug.md`, где `NNN` — следующий номер (см. ниже).
3. Заполни все разделы.
4. Закоммить отдельным коммитом: `docs(adr): ADR-NNN <название решения>`.

ADR не редактируются после "принятия", только дополняются разделом **Update / Superseded by** если решение изменилось.

## Статусы ADR

- **Proposed** — обсуждается, ещё не принято
- **Accepted** — принято, действует
- **Superseded by ADR-XXX** — заменено более новым решением
- **Deprecated** — больше не актуально, но не заменено

## Принятые ADR

| # | Название | Статус |
|---|---|---|
| 001 | [Embedding model: bge-m3](ADR-001-embedding-model.md) | Accepted |
| 002 | [Vector database: Qdrant](ADR-002-vector-database.md) | Accepted |
| 003 | [Разделение Java и Python: два сервиса](ADR-003-java-python-split.md) | Accepted |
| 004 | [LLM provider decision: DeepSeek V4 Flash via OpenRouter](ADR-004-llm-provider-deepseek-openrouter.md) | Accepted |
| 005 | [Query routing model](ADR-005-query-routing-model.md) | Accepted |
| 006 | [Degraded mode policy](ADR-006-degraded-mode-policy.md) | Accepted |
| 007 | [Citation contract and refusal rules](ADR-007-citation-contract-and-refusal-rules.md) | Accepted |
| 008 | [Guard architecture](ADR-008-guard-architecture.md) | Accepted |

## Будущие ADR, которые скорее всего понадобятся

По ходу реализации появятся:

- ADR-009 — Outbox: scheduled poller vs CDC (если придётся выбирать)
- ADR-010 — JWT vs sessions
- ADR-011 — Embedding hosting: local vs HF Inference vs DeepInfra
- ADR-012 — Reranker: bge-reranker локально vs Jina API
