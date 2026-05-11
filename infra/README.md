# infra/

Инфраструктурные манифесты: docker-compose, скрипты деплоя, конфиги observability.

Эта папка пустая — здесь появится содержимое в **EPIC 1** (Infrastructure & Setup).

## Целевая структура

```
infra/
├── docker-compose.yml               # PostgreSQL, MinIO, RabbitMQ, Qdrant, Neo4j, Java app, Python app, nginx
├── docker-compose.observability.yml # Langfuse + его Postgres + Prometheus + Grafana
├── .env.example                     # пример переменных окружения
├── postgres/
│   └── init.sql                     # создание БД для Java и Python (если нужно)
├── nginx/
│   └── default.conf                 # конфиг nginx для frontend + proxy
├── prometheus/
│   └── prometheus.yml
├── grafana/
│   └── dashboards/
└── scripts/
    ├── seed-corpus.sh               # загрузка корпуса в систему
    └── reset-data.sh                # очистка всех volumes
```

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
