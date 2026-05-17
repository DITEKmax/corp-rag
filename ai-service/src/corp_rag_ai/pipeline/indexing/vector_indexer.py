from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from qdrant_client import AsyncQdrantClient, models

from corp_rag_ai.pipeline.indexing.embedding import BGE_M3_DENSE_DIMENSION

COLLECTION_NAME = "documents_chunks"
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
PAYLOAD_INDEX_FIELDS = ("documentId", "language", "docType", "department", "accessLevel")


class QdrantSchemaError(RuntimeError):
    """Raised when an existing Qdrant collection violates the locked schema."""


class QdrantVectorIndex:
    def __init__(
        self,
        client: AsyncQdrantClient,
        *,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        self._client = client
        self._collection_name = collection_name

    @classmethod
    def from_url(cls, url: str) -> QdrantVectorIndex:
        return cls(AsyncQdrantClient(url=url))

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            await close()

    async def ensure_collection_exists(self) -> None:
        collection = await self._get_collection_or_none()
        if collection is None:
            await self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config={
                    DENSE_VECTOR_NAME: models.VectorParams(
                        size=BGE_M3_DENSE_DIMENSION,
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={SPARSE_VECTOR_NAME: models.SparseVectorParams()},
            )
        else:
            _validate_collection_schema(collection)
        await self._ensure_payload_indexes()

    async def _get_collection_or_none(self) -> Any | None:
        try:
            return await self._client.get_collection(self._collection_name)
        except Exception as exc:
            if _is_not_found(exc):
                return None
            raise

    async def _ensure_payload_indexes(self) -> None:
        for field in PAYLOAD_INDEX_FIELDS:
            await self._client.create_payload_index(
                collection_name=self._collection_name,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )


def document_filter(document_id: UUID | str) -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key="documentId",
                match=models.MatchValue(value=str(document_id)),
            )
        ]
    )


def sparse_vector_from_lexical_weights(weights: Mapping[int | str, float]) -> models.SparseVector:
    items = sorted((int(index), float(weight)) for index, weight in weights.items() if float(weight) != 0.0)
    return models.SparseVector(
        indices=[index for index, _weight in items],
        values=[weight for _index, weight in items],
    )


def point_struct(
    *,
    point_id: UUID | str,
    dense: Sequence[float],
    sparse: Mapping[int | str, float],
    payload: Mapping[str, object],
) -> models.PointStruct:
    return models.PointStruct(
        id=str(point_id),
        vector={
            DENSE_VECTOR_NAME: list(dense),
            SPARSE_VECTOR_NAME: sparse_vector_from_lexical_weights(sparse),
        },
        payload=dict(payload),
    )


def _validate_collection_schema(collection: Any) -> None:
    params = collection.config.params
    vectors = params.vectors
    if not isinstance(vectors, Mapping) or DENSE_VECTOR_NAME not in vectors:
        raise QdrantSchemaError(f"dense vector '{DENSE_VECTOR_NAME}' is missing")

    dense = vectors[DENSE_VECTOR_NAME]
    if dense.size != BGE_M3_DENSE_DIMENSION:
        raise QdrantSchemaError(
            f"dense vector size must be {BGE_M3_DENSE_DIMENSION}; found {dense.size}"
        )
    if str(dense.distance).lower() != str(models.Distance.COSINE).lower():
        raise QdrantSchemaError(f"dense distance must be COSINE; found {dense.distance}")

    sparse_vectors = params.sparse_vectors or {}
    if SPARSE_VECTOR_NAME not in sparse_vectors:
        raise QdrantSchemaError(f"sparse vector '{SPARSE_VECTOR_NAME}' is missing")


def _is_not_found(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 404:
        return True
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None) == 404
