import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from corp_rag_ai.adapters.amqp.connection import AmqpConnectionManager
from corp_rag_ai.adapters.amqp.consumer import DocumentEventConsumerRuntime, IdempotentEventDispatcher
from corp_rag_ai.adapters.amqp.messages import InboundEvent
from corp_rag_ai.adapters.amqp.publisher import DocumentResultPublisher
from corp_rag_ai.adapters.minio import MinioDocumentStore
from corp_rag_ai.adapters.rest.chunks import router as chunk_detail_router
from corp_rag_ai.adapters.rest.query import router as query_router
from corp_rag_ai.config import get_settings
from corp_rag_ai.observability import QueryMetrics, QueryMetricsSnapshot, QueryObservability
from corp_rag_ai.pipeline.indexing.embedding import LocalBgeM3Embedder
from corp_rag_ai.pipeline.indexing.entity_extractor import DeepSeekEntityExtractor
from corp_rag_ai.pipeline.indexing.graph_indexer import Neo4jGraphIndex
from corp_rag_ai.pipeline.indexing.vector_indexer import QdrantVectorIndex
from corp_rag_ai.pipeline.ingestion.chunker import DocumentChunker
from corp_rag_ai.pipeline.ingestion.corpus_sanitizer import CorpusSanitizer
from corp_rag_ai.pipeline.ingestion.orchestrator import DocumentIngestionService
from corp_rag_ai.pipeline.ingestion.parsers import build_default_parser_dispatcher
from corp_rag_ai.repositories.database import create_engine, create_session_factory, session_scope
from corp_rag_ai.repositories.ingestion_state import (
    DocumentIndexStateRepository,
    ParentChunkRepository,
    ProcessedEventRepository,
)
from corp_rag_ai.service.query import QueryRuntime, build_query_runtime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    amqp_connection: AmqpConnectionManager | None = None
    amqp_runtime: DocumentEventConsumerRuntime | None = None
    graph_index: Neo4jGraphIndex | None = None
    qdrant_index: QdrantVectorIndex | None = None
    database_engine = None
    query_runtime: QueryRuntime | None = None

    try:
        try:
            app.state.settings = settings
            observability = QueryObservability.from_settings(settings)
            app.state.observability = observability
            app.state.query_metrics = QueryMetrics()
            query_runtime = build_query_runtime(settings, observability=observability)
            app.state.query_service = query_runtime.service
            app.state.query_router_configured = True
            app.state.reranker_configured = settings.reranker_enabled
            app.state.llm_configured = settings.openrouter_api_key is not None
            app.state.query_prewarm_enabled = settings.query_prewarm_enabled

            if settings.query_prewarm_enabled:
                logger.info("LIFESPAN: query_prewarm begin")
                result = await query_runtime.prewarm_local_models(
                    timeout_seconds=settings.query_prewarm_timeout_seconds,
                )
                app.state.query_prewarm_embedding_ready = result.embedding_ready
                app.state.query_prewarm_reranker_ready = result.reranker_ready
                app.state.query_prewarm_warnings = result.warnings
                if result.warnings:
                    logger.warning("LIFESPAN: query_prewarm soft-degraded warnings=%s", result.warnings)
                else:
                    logger.info("LIFESPAN: query_prewarm done")
            else:
                app.state.query_prewarm_embedding_ready = False
                app.state.query_prewarm_reranker_ready = False
                app.state.query_prewarm_warnings = ()

            if settings.neo4j_initialize_schema:
                logger.info("LIFESPAN: neo4j_init begin")
                try:
                    graph_index = Neo4jGraphIndex.from_uri(
                        settings.neo4j_uri,
                        user=settings.neo4j_user,
                        password=settings.neo4j_password.get_secret_value(),
                    )
                    await graph_index.ensure_graph_schema()
                    app.state.graph_index = graph_index
                except Exception:
                    logger.exception("LIFESPAN: neo4j_init failed")
                    raise
                logger.info("LIFESPAN: neo4j_init done")
            else:
                logger.info("LIFESPAN: neo4j_init skipped")

            if settings.qdrant_initialize_collection:
                logger.info("LIFESPAN: qdrant_init begin")
                try:
                    qdrant_index = QdrantVectorIndex.from_url(str(settings.qdrant_url))
                    await qdrant_index.ensure_collection_exists()
                    app.state.qdrant_index = qdrant_index
                except Exception:
                    logger.exception("LIFESPAN: qdrant_init failed")
                    raise
                logger.info("LIFESPAN: qdrant_init done")
            else:
                logger.info("LIFESPAN: qdrant_init skipped")

            if settings.amqp_consumers_enabled:
                logger.info("LIFESPAN: amqp begin")
                try:
                    embedder = LocalBgeM3Embedder(
                        model_name=settings.embedding_model_name,
                        batch_size=settings.embedding_batch_size,
                    )
                    logger.info("LIFESPAN: amqp embedder created")

                    if qdrant_index is not None:
                        await qdrant_index.close()
                    qdrant_index = QdrantVectorIndex.from_url(
                        str(settings.qdrant_url),
                        embedder=embedder,
                    )
                    app.state.qdrant_index = qdrant_index
                    logger.info("LIFESPAN: amqp qdrant closed and rerecreated")

                    if graph_index is None:
                        graph_index = Neo4jGraphIndex.from_uri(
                            settings.neo4j_uri,
                            user=settings.neo4j_user,
                            password=settings.neo4j_password.get_secret_value(),
                        )
                        app.state.graph_index = graph_index

                    database_engine = create_engine(settings)
                    session_factory = create_session_factory(database_engine)
                    amqp_connection = AmqpConnectionManager(
                        settings.rabbitmq_url,
                        prefetch_count=settings.amqp_prefetch_count,
                    )
                    channel = await amqp_connection.connect()
                    logger.info(
                        "LIFESPAN: amqp connect done channel=%s",
                        _channel_number(channel),
                    )

                    publisher = DocumentResultPublisher(
                        channel,
                        event_version=settings.amqp_event_version,
                        source_service=settings.amqp_source_service,
                    )
                    logger.info("LIFESPAN: amqp publisher created")

                    object_store = MinioDocumentStore.from_settings(
                        endpoint=settings.minio_endpoint,
                        access_key=settings.minio_access_key,
                        secret_key=settings.minio_secret_key.get_secret_value(),
                        secure=settings.minio_secure,
                        fetch_timeout_seconds=settings.minio_fetch_timeout_seconds,
                    )
                    logger.info("LIFESPAN: amqp minio store created")

                    parser = build_default_parser_dispatcher()
                    chunker = DocumentChunker()
                    sanitizer = CorpusSanitizer()
                    entity_extractor = DeepSeekEntityExtractor(
                        api_key=_secret_value(settings.openrouter_api_key),
                        base_url=str(settings.openrouter_base_url),
                        model=settings.deepseek_model_id,
                    )
                    logger.info("LIFESPAN: amqp entity_extractor created")

                    async def uploaded_handler(event: InboundEvent) -> None:
                        await _handle_uploaded_idempotently(
                            event,
                            session_factory=session_factory,
                            object_store=object_store,
                            parser=parser,
                            chunker=chunker,
                            sanitizer=sanitizer,
                            vector_index=qdrant_index,
                            entity_extractor=entity_extractor,
                            embedder=embedder,
                            graph_index=graph_index,
                            publisher=publisher,
                        )

                    async def deleted_handler(event: InboundEvent) -> None:
                        await _handle_deleted_idempotently(
                            event,
                            session_factory=session_factory,
                            object_store=object_store,
                            parser=parser,
                            chunker=chunker,
                            sanitizer=sanitizer,
                            vector_index=qdrant_index,
                            entity_extractor=entity_extractor,
                            embedder=embedder,
                            graph_index=graph_index,
                            publisher=publisher,
                        )

                    logger.info("LIFESPAN: amqp handlers defined")

                    amqp_runtime = DocumentEventConsumerRuntime(
                        channel,
                        uploaded_handler=uploaded_handler,
                        deleted_handler=deleted_handler,
                    )
                    logger.info("LIFESPAN: amqp runtime created")

                    await amqp_runtime.start()
                    logger.info("LIFESPAN: amqp runtime started")

                    app.state.amqp_connection = amqp_connection
                    app.state.amqp_runtime = amqp_runtime
                except Exception:
                    logger.exception("LIFESPAN: amqp failed")
                    raise
                logger.info("LIFESPAN: amqp done")
            else:
                logger.info("LIFESPAN: amqp skipped")

            yield
        finally:
            if amqp_runtime is not None:
                await amqp_runtime.close()
            if amqp_connection is not None:
                await amqp_connection.close()
            if qdrant_index is not None:
                await qdrant_index.close()
            if graph_index is not None:
                await graph_index.close()
            if database_engine is not None:
                await database_engine.dispose()
            if query_runtime is not None:
                await query_runtime.close()
    except Exception:
        logger.exception("LIFESPAN: failed")
        raise


async def _handle_uploaded_idempotently(
    event: InboundEvent,
    *,
    session_factory,
    object_store,
    parser,
    chunker,
    sanitizer,
    vector_index,
    entity_extractor,
    embedder,
    graph_index,
    publisher,
) -> None:
    async with session_scope(session_factory) as session:
        processed_events = ProcessedEventRepository(session)

        async def business_handler(inner_event: InboundEvent) -> None:
            service = _build_ingestion_service(
                object_store=object_store,
                parser=parser,
                chunker=chunker,
                sanitizer=sanitizer,
                vector_index=vector_index,
                entity_extractor=entity_extractor,
                embedder=embedder,
                graph_index=graph_index,
                publisher=publisher,
                processed_events=processed_events,
                session=session,
            )
            await service.handle_uploaded(inner_event)

        await IdempotentEventDispatcher(processed_events, business_handler)(event)


async def _handle_deleted_idempotently(
    event: InboundEvent,
    *,
    session_factory,
    object_store,
    parser,
    chunker,
    sanitizer,
    vector_index,
    entity_extractor,
    embedder,
    graph_index,
    publisher,
) -> None:
    async with session_scope(session_factory) as session:
        processed_events = ProcessedEventRepository(session)

        async def business_handler(inner_event: InboundEvent) -> None:
            service = _build_ingestion_service(
                object_store=object_store,
                parser=parser,
                chunker=chunker,
                sanitizer=sanitizer,
                vector_index=vector_index,
                entity_extractor=entity_extractor,
                embedder=embedder,
                graph_index=graph_index,
                publisher=publisher,
                processed_events=processed_events,
                session=session,
            )
            await service.handle_deleted(inner_event)

        await IdempotentEventDispatcher(processed_events, business_handler)(event)


def _build_ingestion_service(
    *,
    object_store,
    parser,
    chunker,
    sanitizer,
    vector_index,
    entity_extractor,
    embedder,
    graph_index,
    publisher,
    processed_events,
    session,
) -> DocumentIngestionService:
    return DocumentIngestionService(
        object_store=object_store,
        parser=parser,
        chunker=chunker,
        sanitizer=sanitizer,
        vector_index=vector_index,
        entity_extractor=entity_extractor,
        entity_embedder=embedder,
        graph_index=graph_index,
        publisher=publisher,
        processed_events=processed_events,
        document_states=DocumentIndexStateRepository(session),
        parent_chunks=ParentChunkRepository(session),
    )


def _channel_number(channel) -> object:
    return getattr(channel, "number", getattr(channel, "channel_number", "unknown"))


def _secret_value(value) -> str | None:
    return value.get_secret_value() if value is not None else None


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(chunk_detail_router)
app.include_router(query_router)


@app.get("/health", tags=["platform"])
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/ready", tags=["platform"])
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/diagnostics", tags=["platform"])
async def diagnostics() -> dict[str, object]:
    metrics = getattr(app.state, "query_metrics", None)
    snapshot = metrics.snapshot() if metrics is not None else QueryMetricsSnapshot()
    observability = getattr(app.state, "observability", None)
    return {
        "amqp_connection": getattr(app.state, "amqp_connection", None) is not None,
        "amqp_runtime": getattr(app.state, "amqp_runtime", None) is not None,
        "qdrant_index": getattr(app.state, "qdrant_index", None) is not None,
        "graph_index": getattr(app.state, "graph_index", None) is not None,
        "query_service": getattr(app.state, "query_service", None) is not None,
        "query_router": bool(getattr(app.state, "query_router_configured", False)),
        "reranker_configured": bool(getattr(app.state, "reranker_configured", False)),
        "llm_reachable": bool(getattr(app.state, "llm_configured", False)),
        "query_prewarm_enabled": bool(getattr(app.state, "query_prewarm_enabled", False)),
        "query_prewarm_embedding_ready": bool(getattr(app.state, "query_prewarm_embedding_ready", False)),
        "query_prewarm_reranker_ready": bool(getattr(app.state, "query_prewarm_reranker_ready", False)),
        "langfuse_configured": bool(getattr(observability, "configured", False)),
        "langfuse_reachable": bool(getattr(observability, "reachable", False)),
        **snapshot.as_dict(),
    }
