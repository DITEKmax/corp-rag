# ai-service/

Python AI Service (FastAPI + LangGraph). Весь RAG-пайплайн.

Эта папка пустая — здесь появится содержимое в **EPIC 9** (Python Skeleton).

## Целевая структура (после EPIC 9)

```
ai-service/
├── pyproject.toml                   # управление через uv
├── Dockerfile
├── .env.example
├── src/corp_rag_ai/
│   ├── main.py
│   ├── config.py
│   ├── contracts/
│   │   ├── __init__.py
│   │   └── generated/
│   │       ├── api_v1.py
│   │       ├── ai_service_v1.py
│   │       ├── events_v1.py
│   │       ├── routing_keys.py
│   │       ├── queue_names.py
│   │       ├── exchange_names.py
│   │       └── error_codes.py
│   ├── adapter/
│   ├── service/
│   ├── pipeline/
│   ├── agent/
│   ├── repository/
│   ├── domain/
│   └── shared/
├── data/
├── eval/
└── tests/
```

Исходные OpenAPI/AsyncAPI YAML и `constants.yaml` живут в корневом `contracts/`; Python генерирует локальные Pydantic-модели и контрактные константы из этого общего источника.

Полная структура — см. `docs/ARCHITECTURE.md` раздел 5.1.

## Команды (появятся когда будет pyproject.toml)

```bash
# cd ai-service
# uv sync
# uv run uvicorn corp_rag_ai.main:app --reload
# uv run pytest
```
