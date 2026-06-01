from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any

from neo4j import AsyncGraphDatabase

from corp_rag_ai.agent import QueryGraphComponents, build_query_graph
from corp_rag_ai.config import Settings
from corp_rag_ai.pipeline.generation.synthesizer import DeepSeekAnswerSynthesizer
from corp_rag_ai.pipeline.guards.input_guard import InputGuard
from corp_rag_ai.pipeline.guards.output_guard import OutputGuard
from corp_rag_ai.pipeline.indexing.embedding import LocalBgeM3Embedder
from corp_rag_ai.pipeline.indexing.vector_indexer import QdrantVectorIndex
from corp_rag_ai.observability import NoopQueryObservability, QueryObservability
from corp_rag_ai.pipeline.retrieval.context_packer import ContextPacker
from corp_rag_ai.pipeline.retrieval.graph import GraphRetriever
from corp_rag_ai.pipeline.retrieval.hybrid import HybridRetriever
from corp_rag_ai.pipeline.retrieval.parent_resolver import ParentResolver
from corp_rag_ai.pipeline.retrieval.reranker import LocalReranker
from corp_rag_ai.pipeline.routing.query_router import DeepSeekQueryRouteClassifier, QueryRouter
from corp_rag_ai.repositories.database import create_engine, create_session_factory, session_scope
from corp_rag_ai.repositories.ingestion_state import ParentChunkRepository
from corp_rag_ai.service.query.service import QueryService


@dataclass(slots=True)
class QueryPrewarmResult:
    embedding_ready: bool
    reranker_ready: bool
    warnings: tuple[str, ...] = ()


@dataclass(slots=True)
class QueryRuntime:
    service: QueryService
    database_engine: Any
    qdrant_index: QdrantVectorIndex
    graph_driver: Any
    embedder: LocalBgeM3Embedder
    reranker: LocalReranker

    async def prewarm_local_models(self, *, timeout_seconds: float) -> QueryPrewarmResult:
        embedding_ready, embedding_warning = await _prewarm_component(
            "embedding",
            asyncio.wait_for(asyncio.to_thread(self.embedder.preflight), timeout=timeout_seconds),
        )
        reranker_ready, reranker_warning = await _prewarm_component(
            "reranker",
            asyncio.wait_for(self.reranker.prewarm(), timeout=timeout_seconds),
        )
        warnings = tuple(warning for warning in (embedding_warning, reranker_warning) if warning)
        return QueryPrewarmResult(
            embedding_ready=embedding_ready,
            reranker_ready=reranker_ready,
            warnings=warnings,
        )

    async def close(self) -> None:
        await self.qdrant_index.close()
        await self.graph_driver.close()
        await self.database_engine.dispose()


class SessionParentChunkReader:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def get_by_parent_ids(self, parent_ids) -> dict:
        async with session_scope(self._session_factory) as session:
            return await ParentChunkRepository(session).get_by_parent_ids(parent_ids)


def build_query_runtime(settings: Settings, *, observability: QueryObservability | NoopQueryObservability | None = None) -> QueryRuntime:
    observability = observability or NoopQueryObservability()
    database_engine = create_engine(settings)
    session_factory = create_session_factory(database_engine)
    qdrant_index = QdrantVectorIndex.from_url(str(settings.qdrant_url))
    graph_driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )

    api_key = _secret_value(settings.openrouter_api_key)
    classifier = (
        DeepSeekQueryRouteClassifier(
            api_key=api_key,
            base_url=str(settings.openrouter_base_url),
            model=settings.deepseek_model_id,
        )
        if api_key
        else None
    )
    embedder = LocalBgeM3Embedder(
        model_name=settings.embedding_model_name,
        batch_size=settings.embedding_batch_size,
    )
    reranker = LocalReranker(
        enabled=settings.reranker_enabled,
        model_name=settings.reranker_model,
        concurrency=settings.reranker_concurrency,
        timeout_seconds=settings.reranker_timeout_seconds,
        load_timeout_seconds=settings.reranker_load_timeout_seconds,
    )
    components = QueryGraphComponents(
        input_guard=InputGuard(model_id=settings.deepseek_model_id),
        router=QueryRouter(
            classifier=classifier,
            confidence_threshold=settings.router_confidence_threshold,
        ),
        hybrid_retriever=HybridRetriever(
            vector_index=qdrant_index,
            embedder=embedder,
            flagged_score_multiplier=settings.flagged_chunk_score_multiplier,
        ),
        graph_retriever=GraphRetriever(graph_driver),
        parent_resolver=ParentResolver(SessionParentChunkReader(session_factory)),
        reranker=reranker,
        context_packer=ContextPacker(token_cap=settings.context_token_cap),
        synthesizer=DeepSeekAnswerSynthesizer(
            api_key=api_key,
            base_url=str(settings.openrouter_base_url),
            model=settings.deepseek_model_id,
            observability=observability,
        ),
        output_guard=OutputGuard(),
        model_id=settings.deepseek_model_id,
        final_top_n=settings.query_final_top_n,
        observability=observability,
    )
    return QueryRuntime(
        service=QueryService(build_query_graph(components)),
        database_engine=database_engine,
        qdrant_index=qdrant_index,
        graph_driver=graph_driver,
        embedder=embedder,
        reranker=reranker,
    )


def _secret_value(value) -> str | None:
    return value.get_secret_value() if value is not None else None


async def _prewarm_component(name: str, awaitable: Awaitable[object]) -> tuple[bool, str | None]:
    try:
        ready = await awaitable
    except Exception as exc:  # pragma: no cover - dependency exceptions vary by host
        return False, f"{name}_prewarm_failed:{exc.__class__.__name__}"
    return bool(ready), None
