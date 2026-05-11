# ADR-002: Vector database — Qdrant

- **Статус:** Accepted
- **Дата:** 2026-05-11
- **Затронутые компоненты:** Python AI Service (indexing + retrieval)

## Контекст

Нужна векторная БД для хранения dense + sparse эмбеддингов чанков с возможностью:
- Hybrid search (dense + sparse одновременно с RRF fusion на стороне БД)
- Фильтрация по payload (RBAC: `accessLevel`, `department`, `docType`, `language`)
- Локальный запуск в Docker
- Бесплатно

Корпус: 30–50 документов в MVP, ~200–400 чанков. С перспективой до 500+ документов в дипломе.

Кандидаты:
- **Qdrant** (Docker self-hosted)
- **Weaviate** (Docker self-hosted)
- **Milvus** (Docker self-hosted)
- **pgvector** (Postgres extension)
- **Chroma** (Python lib + локальный сервер)

## Решение

**Используется Qdrant**, поднимается через Docker (`qdrant/qdrant:latest`), порты 6333 (REST) / 6334 (gRPC).

Одна коллекция `documents_chunks`:
- Dense vector: 1024 measurements, Cosine distance
- Sparse vector: bge-m3 learned sparse
- Payload-индексы: `documentId`, `language`, `docType`, `department`, `accessLevel`

Почему именно это:
1. **Native hybrid query** — Qdrant поддерживает запрос с двумя векторами + RRF/DBSF fusion на стороне БД. Не нужно делать fusion в коде.
2. **Payload-фильтры** — мощный язык фильтров (must/should/must_not + match_any). Идеально ложится на RBAC.
3. **Простой Docker-сетап** — один контейнер, dashboard UI на порту.
4. **Хороший Python SDK** — async поддержка, типизированные модели.
5. **Apache 2.0** — без коммерческих ограничений.
6. **Bilingual community** — есть ru-сообщество, что иногда помогает при отладке.

## Альтернативы

### Альтернатива A: Weaviate
- За: мощный hybrid из коробки, GraphQL API, классы и схемы напоминают полноценную БД.
- Против: тяжелее в setup (требует больше памяти), более "enterprise"-ориентирован, для пет-проекта оверкилл.
- **Вердикт:** отвергнуто — Qdrant покрывает потребности при меньшей сложности.

### Альтернатива B: Milvus
- За: масштабируемость на миллиарды векторов, серьёзная экосистема (Zilliz).
- Против: тяжёлый Docker-сетап (требует etcd, MinIO, Pulsar или Kafka), оверкилл для 500 документов.
- **Вердикт:** отвергнуто — сложность инфраструктуры не оправдана размером корпуса.

### Альтернатива C: pgvector (расширение Postgres)
- За: всё в одной БД, не нужен отдельный контейнер.
- Против:
  - Sparse vector в pgvector сейчас слабо поддерживается (нативный hybrid — это плюс Qdrant).
  - "Database per service" нарушается: Java и Python оба ходят в одну Postgres → coupling.
  - Производительность hybrid + filters на больших корпусах хуже, чем у специализированной БД.
- **Вердикт:** отвергнуто — нарушает архитектурный принцип и слабее по hybrid.

### Альтернатива D: Chroma
- За: простота, "RAG hello world".
- Против: учебная игрушка, нет нативного hybrid, нет серьёзных payload-фильтров, в production не идёт.
- **Вердикт:** отвергнуто — недостаточно зрело для архитектурно-сильного проекта.

## Последствия

### Что получаем
- Hybrid search "из коробки" — не пишем свой RRF.
- Чистое разделение: Python владеет своей БД, Java — своей. Архитектурно корректно.
- Простой docker-compose сетап (один контейнер + том).
- Dashboard для отладки на http://localhost:6333/dashboard.
- Performance — хватит на корпус в десятки тысяч документов.

### Чем платим
- Ещё один сервис в инфраструктуре (но это не критично — у нас и так 8+ контейнеров).
- Vendor-specific API (если когда-то решим мигрировать — придётся переписывать слой `qdrant_repository.py`). Митигируется тем, что весь Qdrant-специфичный код изолирован в одном модуле через `Retriever` protocol.

### Что должно произойти если выбор окажется неправильным
Сигналы:
- Hybrid query даёт неожиданно плохое качество (но это скорее проблема embeddings, чем БД).
- Латенси на корпусе 500+ документов превышает 1 сек.
- Появляются специфичные фичи, нужные нам, которых нет в Qdrant (например, multi-tenancy или native graph-структуры).

Стоимость переключения:
- Средняя. Слой `qdrant_repository.py` инкапсулирует API. Переписать его на другой backend — 1–2 дня + переиндексация корпуса.
- Метаданные документов лежат в Java/Postgres, в Qdrant только их копия в payload — потеря не страшна.

## Ссылки

- Qdrant docs: https://qdrant.tech/documentation/
- Hybrid queries: https://qdrant.tech/documentation/concepts/hybrid-queries/
- Filtering: https://qdrant.tech/documentation/concepts/filtering/
- Python client: https://github.com/qdrant/qdrant-client
