from __future__ import annotations

from dataclasses import dataclass

import pytest
from qdrant_client import models

from corp_rag_ai.config import Settings
from corp_rag_ai.pipeline.indexing.embedding import BGE_M3_DENSE_DIMENSION
from corp_rag_ai.pipeline.indexing.vector_indexer import (
    COLLECTION_NAME,
    DENSE_VECTOR_NAME,
    PAYLOAD_INDEX_FIELDS,
    SPARSE_VECTOR_NAME,
    QdrantSchemaError,
    QdrantVectorIndex,
)


class _NotFound(Exception):
    status_code = 404


class _FakeQdrantClient:
    def __init__(self, collection) -> None:
        self.collection = collection
        self.created_collections: list[dict[str, object]] = []
        self.payload_indexes: list[dict[str, object]] = []

    async def get_collection(self, _collection_name: str):
        if isinstance(self.collection, Exception):
            raise self.collection
        return self.collection

    async def create_collection(self, **kwargs) -> None:
        self.created_collections.append(kwargs)

    async def create_payload_index(self, **kwargs) -> None:
        self.payload_indexes.append(kwargs)

    async def close(self) -> None:
        return None


@dataclass(slots=True)
class _Params:
    vectors: object
    sparse_vectors: object


@dataclass(slots=True)
class _Config:
    params: _Params


@dataclass(slots=True)
class _Collection:
    config: _Config


@pytest.mark.asyncio
async def test_ensure_collection_creates_named_dense_sparse_vectors_and_payload_indexes() -> None:
    client = _FakeQdrantClient(_NotFound())
    index = QdrantVectorIndex(client)  # type: ignore[arg-type]

    await index.ensure_collection_exists()

    assert len(client.created_collections) == 1
    created = client.created_collections[0]
    assert created["collection_name"] == COLLECTION_NAME
    vectors_config = created["vectors_config"]
    assert set(vectors_config) == {DENSE_VECTOR_NAME}
    assert vectors_config[DENSE_VECTOR_NAME].size == BGE_M3_DENSE_DIMENSION
    assert vectors_config[DENSE_VECTOR_NAME].distance == models.Distance.COSINE
    assert set(created["sparse_vectors_config"]) == {SPARSE_VECTOR_NAME}
    assert [index["field_name"] for index in client.payload_indexes] == list(PAYLOAD_INDEX_FIELDS)
    assert "parentChunkId" not in PAYLOAD_INDEX_FIELDS
    assert "isSanitized" not in PAYLOAD_INDEX_FIELDS


@pytest.mark.asyncio
async def test_ensure_collection_noops_for_matching_existing_schema_but_keeps_indexes() -> None:
    client = _FakeQdrantClient(_collection())
    index = QdrantVectorIndex(client)  # type: ignore[arg-type]

    await index.ensure_collection_exists()

    assert client.created_collections == []
    assert [index["field_name"] for index in client.payload_indexes] == list(PAYLOAD_INDEX_FIELDS)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("collection_kwargs", "message"),
    [
        ({"dense_size": 768}, "dense vector size"),
        ({"distance": models.Distance.DOT}, "dense distance"),
        ({"include_sparse": False}, "sparse vector"),
    ],
)
async def test_ensure_collection_raises_on_incompatible_existing_schema(
    collection_kwargs: dict[str, object],
    message: str,
) -> None:
    client = _FakeQdrantClient(_collection(**collection_kwargs))
    index = QdrantVectorIndex(client)  # type: ignore[arg-type]

    with pytest.raises(QdrantSchemaError, match=message):
        await index.ensure_collection_exists()

    assert client.created_collections == []
    assert client.payload_indexes == []


def test_qdrant_collection_initialization_is_startup_disabled_by_default() -> None:
    assert Settings().qdrant_initialize_collection is False


def _collection(
    *,
    dense_size: int = BGE_M3_DENSE_DIMENSION,
    distance: models.Distance = models.Distance.COSINE,
    include_sparse: bool = True,
) -> _Collection:
    return _Collection(
        config=_Config(
            params=_Params(
                vectors={DENSE_VECTOR_NAME: models.VectorParams(size=dense_size, distance=distance)},
                sparse_vectors={SPARSE_VECTOR_NAME: models.SparseVectorParams()} if include_sparse else {},
            )
        )
    )
