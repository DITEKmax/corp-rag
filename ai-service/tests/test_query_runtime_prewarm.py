from __future__ import annotations

from corp_rag_ai.service.query.factory import QueryRuntime


async def test_query_runtime_prewarm_soft_fails_local_model_errors() -> None:
    runtime = QueryRuntime(
        service=object(),
        database_engine=object(),
        qdrant_index=object(),
        graph_driver=object(),
        embedder=_FailingEmbedder(),
        reranker=_FailingReranker(),
    )

    result = await runtime.prewarm_local_models(timeout_seconds=0.1)

    assert result.embedding_ready is False
    assert result.reranker_ready is False
    assert result.warnings == (
        "embedding_prewarm_failed:RuntimeError",
        "reranker_prewarm_failed:RuntimeError",
    )


class _FailingEmbedder:
    def preflight(self):
        raise RuntimeError("embedding unavailable")


class _FailingReranker:
    async def prewarm(self) -> bool:
        raise RuntimeError("reranker unavailable")
