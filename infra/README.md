# infra/

Инфраструктурные манифесты: docker-compose, скрипты деплоя, базовая observability.

Эта папка пустая — здесь появится содержимое в **EPIC 1** (Infrastructure & Setup).

## Целевая структура

```
infra/
├── docker-compose.yml               # PostgreSQL, MinIO, RabbitMQ, Qdrant, Neo4j, Langfuse, Java app, Python app, nginx
├── .env.example                     # пример переменных окружения
├── postgres/
│   └── init.sql                     # создание БД для Java и Python (если нужно)
├── nginx/
│   └── default.conf                 # конфиг nginx для frontend + proxy
└── scripts/
    ├── seed-corpus.sh               # загрузка корпуса в систему
    └── reset-data.sh                # очистка всех volumes
```

Prometheus/Grafana добавляются в Phase 7 (Evaluation & Observability). В Phase 1 вся базовая инфраструктура живёт в одном `docker-compose.yml`; отдельного `docker-compose.observability.yml` нет.

## Команды (появятся когда будет docker-compose.yml)

```bash
# cd infra
# cp .env.example .env  # потом заполнить реальными ключами
# docker compose up -d
# docker compose ps     # проверить здоровье
# docker compose logs -f app
```

## Что должно подняться

| Сервис | URL |
|---|---|
| PostgreSQL (Java) | localhost:5432 |
| MinIO API | http://localhost:9000 |
| MinIO Console | http://localhost:9001 |
| RabbitMQ AMQP | localhost:5672 |
| RabbitMQ Management | http://localhost:15672 |
| Qdrant REST | http://localhost:6333 |
| Qdrant Dashboard | http://localhost:6333/dashboard |
| Neo4j Browser | http://localhost:7474 |
| Neo4j Bolt | localhost:7687 |
| Langfuse | http://localhost:3000 |
| Java backend | http://localhost:8080 |
| Python AI | http://localhost:8000 |
| Frontend | http://localhost:80 |

## Phase 4 Retained-Volume UAT Notes

For Phase 4 ingestion UAT, start the stack from the repository root and keep existing Docker volumes:

```powershell
if (!(Test-Path infra/.env)) { Copy-Item infra/.env.example infra/.env }
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build
docker compose --env-file infra/.env -f infra/docker-compose.yml ps
```

Do not run `docker compose down -v` or data reset scripts before Scenario 1 in `.planning/phases/04-python-ingestion-indexing/04-UAT.md`. Retained RabbitMQ messages from Phase 3 are intentionally consumed by `python-ai` as the first end-to-end smoke.

`python-ai` mounts the named `bge-m3-cache` volume at `/root/.cache/huggingface` so local `BAAI/bge-m3` and reranker model weights survive container recreation. Docker Desktop should have enough memory for the whole stack plus the `python-ai` 4 GB reservation and 6 GB limit.

Phase 5 query defaults are surfaced through Compose and both env examples:

| Setting | Default |
|---|---|
| `AI_QUERY_TIMEOUT_SECONDS` | `30` |
| `AI_ROUTER_CONFIDENCE_THRESHOLD` | `0.65` |
| `AI_RERANKER_ENABLED` | `true` |
| `AI_RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` |
| `AI_CONTEXT_TOKEN_CAP` | `4000` |
| `AI_WEAK_EVIDENCE_THRESHOLD` | `0.4` |
| `AI_FLAGGED_CHUNK_SCORE_MULTIPLIER` | `0.5` |

Live graph extraction requires `OPENROUTER_API_KEY` in the environment used by Compose:

```powershell
# Put OPENROUTER_API_KEY in ignored infra/.env first.
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build python-ai
```

Core live checks:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
Invoke-RestMethod http://localhost:8080/actuator/health
Invoke-RestMethod http://localhost:6333/collections/documents_chunks
docker compose --env-file infra/.env -f infra/docker-compose.yml exec neo4j cypher-shell -u neo4j -p local-neo4j-password "RETURN 1;"
```

## Phase 5 Query UAT Notes

Phase 5 validates Python `POST /v1/query`. Before live query UAT, upload a fresh indexed corpus as described in `.planning/phases/05-retrieval-guards-query-api/05-USER-SETUP.md`; the Phase 4 TechCorp happy-path document was deleted during cleanup.

Do not run `docker compose down -v` before collecting evidence. Keep the `bge-m3-cache` volume because the query path may load both `BAAI/bge-m3` and `BAAI/bge-reranker-v2-m3`.

Record `python-ai` memory before and after the first successful factual query:

```powershell
docker stats python-ai --no-stream --format "{{.MemUsage}}"
```

The Phase 5 contour is still the local 4 GiB reservation and 6 GiB limit. Alarm if observed peak memory exceeds 5.5 GiB; defer any 8 GiB bump to Phase 7+ unless Phase 5 cannot run.

Optional live query smokes:

```powershell
cd ai-service
$env:AI_QUERY_LIVE_SMOKE_ENABLED = "true"
$env:AI_QUERY_LIVE_CORPUS_READY = "true"
$env:AI_QUERY_LIVE_BASE_URL = "http://localhost:8000"
$env:AI_QUERY_LIVE_DEPARTMENTS = "HR"
$env:AI_QUERY_LIVE_DOC_TYPES = "POLICY"
$env:OPENROUTER_API_KEY = "<openrouter-key>"
uv run pytest tests/test_query_live_smokes.py -m integration -q -s
```
