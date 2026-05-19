from __future__ import annotations

from qdrant_client import models

from corp_rag_ai.domain.query import AccessFilter
from corp_rag_ai.pipeline.indexing.embedding import EmbeddingVector
from corp_rag_ai.pipeline.indexing.vector_indexer import (
    COLLECTION_NAME,
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    QdrantVectorIndex,
)


class _FakeQdrantClient:
    def __init__(self) -> None:
        self.query_calls: list[dict[str, object]] = []

    async def query_points(self, **kwargs):
        self.query_calls.append(kwargs)
        return []


async def test_hybrid_query_pushes_access_doc_type_and_department_filters_to_qdrant() -> None:
    client = _FakeQdrantClient()
    index = QdrantVectorIndex(client)  # type: ignore[arg-type]

    await index.query_hybrid(
        query_embedding=EmbeddingVector(dense=(0.1, 0.2), sparse={7: 0.7}),
        access_filter=AccessFilter(
            access_levels=("PUBLIC", "INTERNAL"),
            departments=("HR", "IT"),
            doc_types=("POLICY", "GUIDE"),
        ),
        limit=5,
        prefetch_limit=25,
    )

    call = client.query_calls[0]
    assert call["collection_name"] == COLLECTION_NAME
    assert call["with_payload"] is True
    assert call["with_vectors"] is False
    assert call["limit"] == 5
    assert call["query"].fusion == models.Fusion.RRF

    query_filter = call["query_filter"]
    conditions = _conditions_by_key(query_filter)
    assert conditions["accessLevel"].match.any == ["PUBLIC", "INTERNAL"]
    assert conditions["docType"].match.any == ["POLICY", "GUIDE"]
    assert conditions["department"].match.any == ["HR", "IT"]

    dense_prefetch, sparse_prefetch = call["prefetch"]
    assert dense_prefetch.using == DENSE_VECTOR_NAME
    assert dense_prefetch.query == [0.1, 0.2]
    assert dense_prefetch.filter is query_filter
    assert dense_prefetch.limit == 25
    assert sparse_prefetch.using == SPARSE_VECTOR_NAME
    assert sparse_prefetch.query.indices == [7]
    assert sparse_prefetch.query.values == [0.7]
    assert sparse_prefetch.filter is query_filter
    assert sparse_prefetch.limit == 25


async def test_empty_departments_omit_only_department_condition() -> None:
    client = _FakeQdrantClient()
    index = QdrantVectorIndex(client)  # type: ignore[arg-type]

    await index.query_hybrid(
        query_embedding=EmbeddingVector(dense=(0.1,), sparse={3: 0.3}),
        access_filter=AccessFilter(access_levels=("PUBLIC",), departments=(), doc_types=("REPORT",)),
        limit=3,
        prefetch_limit=20,
    )

    conditions = _conditions_by_key(client.query_calls[0]["query_filter"])

    assert set(conditions) == {"accessLevel", "docType"}
    assert conditions["accessLevel"].match.any == ["PUBLIC"]
    assert conditions["docType"].match.any == ["REPORT"]


def _conditions_by_key(query_filter) -> dict[str, object]:
    return {condition.key: condition for condition in query_filter.must}
