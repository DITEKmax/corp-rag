from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from corp_rag_ai import main as app_main
from corp_rag_ai.adapters.amqp.messages import EventMetadata, InboundEvent
from corp_rag_ai.config import Settings


class _ProcessedEvents:
    def __init__(self, calls: list[str], *, processed: bool) -> None:
        self._calls = calls
        self._processed = processed

    async def has_processed(self, _event_id) -> bool:
        self._calls.append("processed.has")
        return self._processed


class _ServiceShouldNotBuild:
    def __init__(self, *args, **kwargs) -> None:
        raise AssertionError("business service should not be built for duplicate events")


class _ExplodingDependency:
    def __getattr__(self, name: str):
        raise AssertionError(f"duplicate dispatch touched dependency: {name}")


@pytest.mark.asyncio
async def test_duplicate_upload_event_short_circuits_before_business_service_construction(monkeypatch) -> None:
    calls: list[str] = []

    @asynccontextmanager
    async def fake_session_scope(_session_factory):
        calls.append("session.open")
        yield object()
        calls.append("session.close")

    monkeypatch.setattr(app_main, "session_scope", fake_session_scope)
    monkeypatch.setattr(app_main, "ProcessedEventRepository", lambda _session: _ProcessedEvents(calls, processed=True))
    monkeypatch.setattr(app_main, "DocumentIngestionService", _ServiceShouldNotBuild)

    dependency = _ExplodingDependency()

    await app_main._handle_uploaded_idempotently(
        _uploaded_event(),
        session_factory=object(),
        object_store=dependency,
        parser=dependency,
        chunker=dependency,
        sanitizer=dependency,
        vector_index=dependency,
        entity_extractor=dependency,
        embedder=dependency,
        graph_index=dependency,
        publisher=dependency,
    )

    assert calls == ["session.open", "processed.has", "session.close"]


def test_query_runtime_settings_defaults() -> None:
    settings = Settings()

    assert settings.query_timeout_seconds == 30
    assert settings.router_confidence_threshold == 0.65
    assert settings.reranker_enabled is True
    assert settings.reranker_model == "BAAI/bge-reranker-v2-m3"
    assert settings.reranker_timeout_seconds == 25.0
    assert settings.reranker_load_timeout_seconds == 28.0
    assert settings.context_token_cap == 4000
    assert settings.weak_evidence_threshold == 0.4
    assert settings.flagged_chunk_score_multiplier == 0.5


def _uploaded_event() -> InboundEvent:
    metadata = EventMetadata(
        event_id=uuid4(),
        event_type="document.uploaded",
        event_version="1.0.0",
        occurred_at=datetime(2026, 5, 17, tzinfo=UTC),
        correlation_id=uuid4(),
        source_service="corp-rag-backend",
    )
    return InboundEvent(
        metadata=metadata,
        payload={"documentId": str(uuid4())},
        headers={"x-correlation-id": str(metadata.correlation_id)},
    )
