from __future__ import annotations

import pytest

from corp_rag_ai.config import Settings
from corp_rag_ai.pipeline.indexing.embedding import BGE_M3_DENSE_DIMENSION
from corp_rag_ai.pipeline.indexing.graph_indexer import (
    VECTOR_INDEX_NAME,
    Neo4jGraphIndex,
    Neo4jGraphSchemaError,
)


class _FakeResult:
    def __init__(self, records=None) -> None:
        self.records = list(records or [])
        self.consumed = False

    async def consume(self) -> None:
        self.consumed = True

    async def data(self):
        return self.records


class _FakeSchemaSession:
    def __init__(self, vector_records) -> None:
        self.vector_records = vector_records
        self.queries: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def run(self, query: str):
        self.queries.append(query)
        if query.startswith("SHOW VECTOR INDEXES"):
            return _FakeResult(self.vector_records)
        return _FakeResult()


class _FakeDriver:
    def __init__(self, session: _FakeSchemaSession) -> None:
        self.session_instance = session

    def session(self, **_kwargs):
        return self.session_instance

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_ensure_graph_schema_creates_indexes_and_accepts_populating_vector_index() -> None:
    session = _FakeSchemaSession([{"name": VECTOR_INDEX_NAME, "state": "POPULATING"}])
    graph_index = Neo4jGraphIndex(_FakeDriver(session))

    await graph_index.ensure_graph_schema(timeout_seconds=0.1, poll_interval_seconds=0)

    joined_queries = "\n".join(session.queries)
    assert "CREATE INDEX entity_normalized_name_idx" in joined_queries
    assert "CREATE INDEX entity_type_idx" in joined_queries
    assert "CREATE INDEX document_id_idx" in joined_queries
    assert "CREATE INDEX document_access_level_idx" in joined_queries
    assert "CREATE INDEX relation_mention_type_idx" in joined_queries
    assert f"CREATE VECTOR INDEX {VECTOR_INDEX_NAME}" in joined_queries
    assert f"`vector.dimensions`: {BGE_M3_DENSE_DIMENSION}" in joined_queries
    assert "`vector.similarity_function`: 'cosine'" in joined_queries
    assert "SHOW VECTOR INDEXES" in joined_queries
    assert "VECTOR)" not in joined_queries
    assert ":Chunk" not in joined_queries


@pytest.mark.asyncio
async def test_ensure_graph_schema_raises_for_failed_vector_index() -> None:
    session = _FakeSchemaSession([{"name": VECTOR_INDEX_NAME, "state": "FAILED"}])
    graph_index = Neo4jGraphIndex(_FakeDriver(session))

    with pytest.raises(Neo4jGraphSchemaError, match="FAILED"):
        await graph_index.ensure_graph_schema(timeout_seconds=0.1, poll_interval_seconds=0)


@pytest.mark.asyncio
async def test_ensure_graph_schema_times_out_when_vector_index_is_absent() -> None:
    session = _FakeSchemaSession([])
    graph_index = Neo4jGraphIndex(_FakeDriver(session))

    with pytest.raises(Neo4jGraphSchemaError, match="Timed out waiting 0.0s"):
        await graph_index.ensure_graph_schema(timeout_seconds=0, poll_interval_seconds=0)


def test_neo4j_schema_initialization_is_startup_disabled_by_default() -> None:
    assert Settings().neo4j_initialize_schema is False
