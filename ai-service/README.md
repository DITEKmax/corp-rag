# ai-service/

Python AI Service (FastAPI + LangGraph). Весь RAG-пайплайн.

Эта папка пустая — здесь появится содержимое в **EPIC 9** (Python Skeleton).

## Целевая структура (после EPIC 9)

```
ai-service/
├── pyproject.toml                   # управление через uv
├── Dockerfile
├── .env.example
├── contracts/
│   ├── openapi/
│   ├── asyncapi/
│   └── generated/pydantic_models.py
├── src/corp_rag_ai/
│   ├── main.py
│   ├── config.py
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

Полная структура — см. `docs/ARCHITECTURE.md` раздел 5.1.

## Команды (появятся когда будет pyproject.toml)

```bash
# cd ai-service
# uv sync
# uv run uvicorn corp_rag_ai.main:app --reload
# uv run pytest
```
