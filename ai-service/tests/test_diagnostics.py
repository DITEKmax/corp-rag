from __future__ import annotations

from corp_rag_ai.main import app, diagnostics
from corp_rag_ai.observability import NoopQueryObservability, QueryMetrics


async def test_diagnostics_reports_query_readiness_without_live_checks() -> None:
    _clear_state(
        "amqp_connection",
        "amqp_runtime",
        "qdrant_index",
        "graph_index",
        "query_service",
        "query_router_configured",
        "reranker_configured",
        "llm_configured",
        "query_prewarm_enabled",
        "query_prewarm_embedding_ready",
        "query_prewarm_reranker_ready",
        "observability",
        "query_metrics",
    )
    app.state.query_service = object()
    app.state.query_router_configured = True
    app.state.reranker_configured = True
    app.state.llm_configured = False

    result = await diagnostics()

    assert result["amqp_connection"] is False
    assert result["amqp_runtime"] is False
    assert result["qdrant_index"] is False
    assert result["graph_index"] is False
    assert result["query_service"] is True
    assert result["query_router"] is True
    assert result["reranker_configured"] is True
    assert result["llm_reachable"] is False
    assert result["query_prewarm_enabled"] is False
    assert result["query_prewarm_embedding_ready"] is False
    assert result["query_prewarm_reranker_ready"] is False
    assert result["langfuse_configured"] is False
    assert result["langfuse_reachable"] is False
    assert result["query_count"] == 0
    assert result["answered_rate"] == 0.0


async def test_diagnostics_reports_process_local_query_metrics() -> None:
    _clear_state("query_metrics", "observability")
    app.state.query_metrics = QueryMetrics()
    app.state.observability = NoopQueryObservability()

    from corp_rag_ai.domain.query import QueryResult, QueryRoute
    from corp_rag_ai.domain.retrieval import RetrievalMetadata

    app.state.query_metrics.record(
        QueryResult(
            answered=True,
            answer="ok",
            citations=(),
            confidence=1.0,
            conversation_id="00000000-0000-4000-8000-000000000001",
            message_id="00000000-0000-4000-8000-000000000002",
            retrieval_meta=RetrievalMetadata(route=QueryRoute.FACTUAL, latency_ms=20, model_id="test"),
        )
    )

    result = await diagnostics()

    assert result["query_count"] == 1
    assert result["answered_count"] == 1
    assert result["answered_rate"] == 1.0
    assert result["mean_latency_ms"] == 20


def _clear_state(*names: str) -> None:
    for name in names:
        if hasattr(app.state, name):
            delattr(app.state, name)
