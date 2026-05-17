from __future__ import annotations

import os
from uuid import uuid4

import pytest
from openai import AsyncOpenAI

from corp_rag_ai.pipeline.indexing.embedding import BGE_M3_DENSE_DIMENSION, LocalBgeM3Embedder
from corp_rag_ai.pipeline.indexing.graph_indexer import Neo4jGraphIndex
from corp_rag_ai.pipeline.indexing.vector_indexer import (
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    QdrantVectorIndex,
)


def _requires_enabled_flag(name: str) -> None:
    if os.environ.get(name, "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip(f"{name}=true is required for this live integration smoke")


def _requires_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(f"{name} is required for this live integration smoke")
    return value


@pytest.mark.integration
def test_live_flagembedding_bge_m3_dense_sparse_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    _requires_enabled_flag("AI_EMBEDDING_LIVE_SMOKE_ENABLED")
    cache_dir = os.environ.get("AI_EMBEDDING_MODEL_CACHE_DIR")
    if cache_dir:
        monkeypatch.setenv("HF_HOME", cache_dir)

    embedder = LocalBgeM3Embedder(
        model_name=os.environ.get("AI_EMBEDDING_MODEL", "BAAI/bge-m3"),
        batch_size=int(os.environ.get("AI_EMBEDDING_BATCH_SIZE", "32")),
    )

    vector = embedder.preflight()

    assert len(vector.dense) == BGE_M3_DENSE_DIMENSION
    assert vector.sparse


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_qdrant_named_dense_sparse_collection_smoke() -> None:
    _requires_enabled_flag("AI_QDRANT_LIVE_SMOKE_ENABLED")
    from qdrant_client import AsyncQdrantClient

    collection_name = f"documents_chunks_live_smoke_{uuid4().hex}"
    client = AsyncQdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"))
    index = QdrantVectorIndex(client, collection_name=collection_name)

    try:
        await index.ensure_collection_exists()
        collection = await client.get_collection(collection_name)
        vectors = collection.config.params.vectors
        sparse_vectors = collection.config.params.sparse_vectors or {}

        assert DENSE_VECTOR_NAME in vectors
        assert vectors[DENSE_VECTOR_NAME].size == BGE_M3_DENSE_DIMENSION
        assert SPARSE_VECTOR_NAME in sparse_vectors
    finally:
        try:
            await client.delete_collection(collection_name=collection_name)
        finally:
            await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_neo4j_schema_initialization_smoke() -> None:
    _requires_enabled_flag("AI_NEO4J_LIVE_SMOKE_ENABLED")
    index = Neo4jGraphIndex.from_uri(
        os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", "local-neo4j-password"),
    )

    try:
        await index.ensure_graph_schema(timeout_seconds=30.0, poll_interval_seconds=0.25)
    finally:
        await index.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_deepseek_smoke() -> None:
    api_key = _requires_env("OPENROUTER_API_KEY")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    )

    response = await client.chat.completions.create(
        model=os.environ.get("DEEPSEEK_MODEL_ID", "deepseek/deepseek-v4-flash"),
        messages=[{"role": "user", "content": "Return only: ok"}],
        temperature=0,
        max_tokens=8,
    )

    content = response.choices[0].message.content or ""
    assert "ok" in content.lower()
