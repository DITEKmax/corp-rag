from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from corp_rag_ai.adapters.amqp.connection import AmqpConnectionManager
from corp_rag_ai.adapters.amqp.consumer import DocumentEventConsumerRuntime, InfrastructureRetry
from corp_rag_ai.adapters.amqp.messages import InboundEvent
from corp_rag_ai.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    amqp_connection: AmqpConnectionManager | None = None
    amqp_runtime: DocumentEventConsumerRuntime | None = None
    if settings.amqp_consumers_enabled:
        amqp_connection = AmqpConnectionManager(
            settings.rabbitmq_url,
            prefetch_count=settings.amqp_prefetch_count,
        )
        channel = await amqp_connection.connect()
        amqp_runtime = DocumentEventConsumerRuntime(
            channel,
            uploaded_handler=_ingestion_handler_not_wired,
            deleted_handler=_ingestion_handler_not_wired,
        )
        await amqp_runtime.start()
        app.state.amqp_connection = amqp_connection
        app.state.amqp_runtime = amqp_runtime
    try:
        yield
    finally:
        if amqp_runtime is not None:
            await amqp_runtime.close()
        if amqp_connection is not None:
            await amqp_connection.close()


async def _ingestion_handler_not_wired(_event: InboundEvent) -> None:
    raise InfrastructureRetry("ingestion orchestration is not wired yet")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["platform"])
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/ready", tags=["platform"])
async def ready() -> dict[str, str]:
    return {"status": "ready"}
