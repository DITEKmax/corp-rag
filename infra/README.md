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
docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml ps
```

Do not run `docker compose down -v` or data reset scripts before Scenario 1 in `.planning/phases/04-python-ingestion-indexing/04-UAT.md`. Retained RabbitMQ messages from Phase 3 are intentionally consumed by `python-ai` as the first end-to-end smoke.

`python-ai` mounts the named `bge-m3-cache` volume at `/root/.cache/huggingface` so local `BAAI/bge-m3` model weights survive container recreation. Docker Desktop should have enough memory for the whole stack plus the `python-ai` 3 GB reservation and 4 GB limit.

Live graph extraction requires `GEMINI_API_KEY` in the environment used by Compose:

```powershell
$env:GEMINI_API_KEY = "your-google-ai-studio-key"
docker compose -f infra/docker-compose.yml up -d --build python-ai
```

Core live checks:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
Invoke-RestMethod http://localhost:8080/actuator/health
Invoke-RestMethod http://localhost:6333/collections/documents_chunks
docker compose -f infra/docker-compose.yml exec neo4j cypher-shell -u neo4j -p local-neo4j-password "RETURN 1;"
```
