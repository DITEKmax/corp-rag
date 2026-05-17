from __future__ import annotations

from uuid import UUID

import pytest

from corp_rag_ai.domain.chunks import ChildChunk
from corp_rag_ai.pipeline.indexing.embedding import EmbeddingVector
from corp_rag_ai.pipeline.indexing.vector_indexer import (
    COLLECTION_NAME,
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    QdrantVectorIndex,
    VectorIndexChunk,
    document_filter,
    sparse_vector_from_lexical_weights,
)


class _FakeEmbedder:
    def __init__(self, embeddings: tuple[EmbeddingVector, ...]) -> None:
        self.embeddings = embeddings
        self.text_batches: list[list[str]] = []

    def embed_texts(self, texts) -> tuple[EmbeddingVector, ...]:
        self.text_batches.append(list(texts))
        return self.embeddings


class _FakeQdrantClient:
    def __init__(self) -> None:
        self.operations: list[str] = []
        self.deletes: list[dict[str, object]] = []
        self.upserts: list[dict[str, object]] = []

    async def delete(self, **kwargs) -> None:
        self.operations.append("delete")
        self.deletes.append(kwargs)

    async def upsert(self, **kwargs) -> None:
        self.operations.append("upsert")
        self.upserts.append(kwargs)


@pytest.mark.asyncio
async def test_replace_document_chunks_deletes_before_upserting_locked_payload_points() -> None:
    document_id = UUID("11111111-1111-1111-1111-111111111111")
    child = _child_chunk(document_id=document_id)
    embedder = _FakeEmbedder(
        (
            EmbeddingVector(dense=(0.1, 0.2, 0.3), sparse={42: 0.8, 7: 0.4}),
        )
    )
    client = _FakeQdrantClient()
    index = QdrantVectorIndex(client, embedder=embedder)  # type: ignore[arg-type]
    chunk = VectorIndexChunk(
        child=child,
        document_title="HR Policy",
        language="en",
        doc_type="POLICY",
        department="HR",
        access_level="INTERNAL",
        is_sanitized=False,
        sanitizer_flags=("PROMPT_IGNORE_INSTRUCTIONS",),
        content_for_embedding="HR Policy\n\nsanitized body",
    )

    await index.replace_document_chunks(document_id, [chunk])

    assert client.operations == ["delete", "upsert"]
    assert embedder.text_batches == [["HR Policy\n\nsanitized body"]]
    delete_filter = client.deletes[0]["points_selector"]
    assert delete_filter.must[0].key == "documentId"
    assert delete_filter.must[0].match.value == str(document_id)

    upsert = client.upserts[0]
    assert upsert["collection_name"] == COLLECTION_NAME
    point = upsert["points"][0]
    assert point.id == str(child.chunk_id)
    assert point.vector[DENSE_VECTOR_NAME] == [0.1, 0.2, 0.3]
    assert point.vector[SPARSE_VECTOR_NAME].indices == [7, 42]
    assert point.vector[SPARSE_VECTOR_NAME].values == [0.4, 0.8]
    assert point.payload == {
        "chunkId": str(child.chunk_id),
        "parentChunkId": str(child.parent_chunk_id),
        "documentId": str(document_id),
        "documentTitle": "HR Policy",
        "sectionPath": ["Benefits"],
        "position": 3,
        "page": 5,
        "content": "Original display body",
        "language": "en",
        "docType": "POLICY",
        "department": "HR",
        "accessLevel": "INTERNAL",
        "isSanitized": False,
        "sanitizerFlags": ["PROMPT_IGNORE_INSTRUCTIONS"],
    }
    assert "content_for_embedding" not in point.payload


@pytest.mark.asyncio
async def test_delete_document_uses_idempotent_document_id_filter() -> None:
    document_id = UUID("22222222-2222-2222-2222-222222222222")
    client = _FakeQdrantClient()
    index = QdrantVectorIndex(client)  # type: ignore[arg-type]

    await index.delete_document(document_id)
    await index.delete_document(document_id)

    assert client.operations == ["delete", "delete"]
    assert [delete["collection_name"] for delete in client.deletes] == [COLLECTION_NAME, COLLECTION_NAME]
    assert all(delete["points_selector"].must[0].key == "documentId" for delete in client.deletes)
    assert all(delete["points_selector"].must[0].match.value == str(document_id) for delete in client.deletes)


def test_sparse_vector_from_lexical_weights_sorts_indices() -> None:
    sparse = sparse_vector_from_lexical_weights({"99": 0.9, 3: 0.3, "12": 0.12})

    assert sparse.indices == [3, 12, 99]
    assert sparse.values == [0.3, 0.12, 0.9]


def test_document_filter_uses_locked_document_id_selector() -> None:
    document_id = UUID("33333333-3333-3333-3333-333333333333")
    filter_selector = document_filter(document_id)

    assert filter_selector.must[0].key == "documentId"
    assert filter_selector.must[0].match.value == str(document_id)


def _child_chunk(*, document_id: UUID) -> ChildChunk:
    return ChildChunk(
        chunk_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        parent_chunk_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        document_id=document_id,
        section_path=("Benefits",),
        content="Original display body",
        content_for_embedding="HR Policy\n\nOriginal display body",
        position=3,
        position_in_parent=1,
        token_count=12,
        page=5,
    )
