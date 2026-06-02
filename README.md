# corp-rag

Корпоративная RAG-система для внутреннего поиска по документам с grounded answers,
цитированием источников, RBAC-фильтрацией и защитой от prompt injection.

> **Статус:** demo-ready local MVP для Phase 8. Запуск и проверка идут через
> единственный local Docker Compose stack: `infra/docker-compose.yml`.

## Что демо показывает честно

Система хорошо отвечает там, где найдено достаточное evidence, и безопасно
отказывается вместо выдумки там, где evidence слабое или маршрут уходит в
известное ограничение multi-hop graph retrieval.

Финальная Phase 8 регрессия на корпусе `ru-aviation-logistics-v1`:

| Метрика | Значение | Интерпретация |
|---|---:|---|
| `faithfulness` | `0.991` | Ответы почти полностью опираются на найденные источники. |
| `answer_relevancy` | `0.865` | Ответы релевантны вопросам, когда система отвечает. |
| `context_precision` | `1.0` | Retrieved context точный на scored rows. |
| `context_recall` | `1.0` | Retrieved context достаточный на scored rows. |
| `answered` | `16/30 answerable` | Coverage ограничен известными отказами. |
| `outcome_accuracy` | `0.575` | Не проходит threshold из-за coverage/refusal gaps. |
| `citation_doc_recall` | `0.533` | Refused rows не дают citation docs, что ограничивает recall. |

Сильная сторона демо: система не галлюцинирует, цитирует источники и
предпочитает безопасный отказ unsupported answers. Known limitations и waiver
зафиксированы в
[08-KNOWN-LIMITATIONS.md](.planning/phases/08-delivery-polish-demo-readiness/08-KNOWN-LIMITATIONS.md).

## Стек MVP

| Слой | Технология |
|---|---|
| Frontend | Vanilla HTML5 + CSS3 + ES2022+, nginx |
| Java backend | Java 21 + Spring Boot 3.3 |
| Python AI service | Python 3.12 + FastAPI + LangGraph |
| Хранилища | PostgreSQL, MinIO, Qdrant, Neo4j |
| Брокер | RabbitMQ |
| Embeddings | `BAAI/bge-m3` dense + learned sparse |
| Reranker | `BAAI/bge-reranker-v2-m3` |
| Synthesis/router/guards | `deepseek/deepseek-v4-flash` via OpenRouter |
| RAGAS judge | `deepseek/deepseek-chat` |
| Observability | Langfuse |

## Локальный demo quickstart

Требования:

- Docker Desktop с WSL memory `12GB`.
- Ignored `infra/.env`, созданный из `infra/.env.example`.
- В `infra/.env` заданы `ADMIN_USERNAME`, `ADMIN_EMAIL`,
  `ADMIN_PASSWORD` для admin bootstrap и seed reset.
- В `infra/.env` задан `OPENROUTER_API_KEY` для live DeepSeek/OpenRouter path.
- Для Python AI оставлены Phase 8 memory settings:
  `PYTHON_AI_MEMORY_LIMIT=10g` и `PYTHON_AI_MEMORY_RESERVATION=8g`.

Секреты не коммитятся. В документации фиксируются только имена переменных и
пути к ignored env files.

Запуск из корня репозитория:

```powershell
if (!(Test-Path infra/.env)) { Copy-Item infra/.env.example infra/.env }
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build
docker compose --env-file infra/.env -f infra/docker-compose.yml ps
```

Ожидаемый локальный stack:

- Frontend: `http://localhost`
- Java API: `http://localhost:8080`
- Python AI: `http://localhost:8000`
- Langfuse: `http://localhost:3000`
- Qdrant: `http://localhost:6333`
- Neo4j Browser: `http://localhost:7474`
- RabbitMQ Management: `http://localhost:15672`
- MinIO Console: `http://localhost:9001`

Frontend вызывает только Java API. Python AI остается внутренним сервисом для
Java REST/AMQP path.

## Health checks

Детерминированная проверка demo stack:

```powershell
python scripts/check_demo_stack.py --compose-file infra/docker-compose.yml --env-file infra/.env --output .planning/phases/08-delivery-polish-demo-readiness/08-COMPOSE-EVIDENCE.md
```

Ожидаемый результат Phase 8: `services_healthy=9/9`, `/diagnostics` доступен,
`langfuse_configured=true`, `langfuse_reachable=true`,
`reranker_degraded_count=0`.

Быстрые direct checks:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
Invoke-RestMethod http://localhost:8000/diagnostics
Invoke-RestMethod http://localhost:8080/actuator/health
Invoke-RestMethod http://localhost:6333/collections/documents_chunks
```

## Seed reset

Демо-корпус сбрасывается через нормальный Java document lifecycle: логин,
delete старых seed documents, upload 16 RU-документов, ожидание индексации,
проверка Java/Qdrant/Neo4j.

```powershell
.\scripts\seed-demo-corpus.ps1
```

Ожидаемое evidence:

- Java documents: `16/16`
- Qdrant document ids: `16/16`
- Neo4j document nodes: `16/16`
- non-seed Java documents: `0`

Файлы evidence:

- [08-SEED-EVIDENCE.md](.planning/phases/08-delivery-polish-demo-readiness/08-SEED-EVIDENCE.md)
- [08-COMPOSE-EVIDENCE.md](.planning/phases/08-delivery-polish-demo-readiness/08-COMPOSE-EVIDENCE.md)
- [08-FINAL-REGRESSION.md](.planning/phases/08-delivery-polish-demo-readiness/08-FINAL-REGRESSION.md)

## Demo path

Review-ready материалы лежат в [docs/demo/](docs/demo/):

- [docs/demo/README.md](docs/demo/README.md) - индекс демо-ассетов и evidence.
- [docs/demo/demo-script.md](docs/demo/demo-script.md) - сценарий показа.
- [docs/demo/video-checklist.md](docs/demo/video-checklist.md) - short-video checklist и ready-to-record waiver.

Основной сценарий:

1. Показать factual query на русском корпусе с citation chips/source view.
2. Открыть live Langfuse trace и latency breakdown; rerank - ожидаемый dominant span.
3. Показать injection/refusal сцену: `ru-out-007` блокируется как
   `TIER_0_REGEX`, confidence `1.0`.
4. Явно показать multi-hop limitation: отказ безопасен и измерен, а не скрыт.

## Final regression command

Не запускай eval без явной необходимости: финальные Phase 8 цифры уже
зафиксированы. Команда ниже оставлена как runbook для воспроизводимости:

```powershell
cd ai-service
.\.venv\Scripts\python.exe eval/ragas_runner.py --service-base-url http://localhost:8000 --top-k 10 --timeout-seconds 60 --qdrant-url http://localhost:6333 --judge-base-url https://openrouter.ai/api/v1 --judge-model-id deepseek/deepseek-chat --embedding-model-id BAAI/bge-m3 --reports-dir eval\reports --ragas-max-retries 1 --ragas-max-wait 5
```

Зафиксированные отчеты:

- [ragas_ru.md](ai-service/eval/reports/ragas_ru.md)
- [injection_ru.md](ai-service/eval/reports/injection_ru.md)
- [08-KNOWN-LIMITATIONS.md](.planning/phases/08-delivery-polish-demo-readiness/08-KNOWN-LIMITATIONS.md)

## Troubleshooting

- Если `python-ai` не healthy, смотри startup/prewarm:
  `docker logs corp-rag-python-ai-1 --tail 120`.
- Не используй `docker compose down -v` для обычного reset: это удалит volume
  evidence и model cache. Для seed reset используй `.\scripts\seed-demo-corpus.ps1`.
- Если model loading медленный, сохрани volume `bge-m3-cache` и перезапусти
  compose без очистки volumes.
- Если memory pressure возвращается, проверь WSL `12GB` и Python AI
  `10g/8g`; снижение лимита воспроизводит старую 8g проблему.
- Если seed evidence показывает Java/Qdrant success, но Neo4j missing docs,
  сначала смотри `python-ai` logs по entity extraction, затем rerun seed.

## Документация

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - архитектура и реальные service boundaries.
- [infra/README.md](infra/README.md) - подробный local demo stack runbook.
- [docs/decisions/](docs/decisions/) - ADR.
- [.planning/phases/08-delivery-polish-demo-readiness/](.planning/phases/08-delivery-polish-demo-readiness/) - Phase 8 evidence.

## Лицензия

MIT (будет добавлено).
