from fastapi import FastAPI

from corp_rag_ai.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)


@app.get("/health", tags=["platform"])
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/ready", tags=["platform"])
async def ready() -> dict[str, str]:
    return {"status": "ready"}
