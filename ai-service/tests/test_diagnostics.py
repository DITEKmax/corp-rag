from __future__ import annotations

from corp_rag_ai.main import app, diagnostics


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


def _clear_state(*names: str) -> None:
    for name in names:
        if hasattr(app.state, name):
            delattr(app.state, name)
