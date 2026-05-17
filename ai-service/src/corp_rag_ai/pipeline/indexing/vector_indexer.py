from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from qdrant_client import AsyncQdrantClient, models

from corp_rag_ai.domain.chunks import ChildChunk
from corp_rag_ai.domain.exceptions import (
    DEPENDENCY_UNAVAILABLE,
    INDEXING_PIPELINE_ERROR,
    IndexingStage,
    StageFailure,
    stage_failure,
)
from corp_rag_ai.pipeline.indexing.embedding import BGE_M3_DENSE_DIMENSION
from corp_rag_ai.pipeline.indexing.embedding import EmbeddingVector

COLLECTION_NAME = "documents_chunks"
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
PAYLOAD_INDEX_FIELDS = ("documentId", "language", "docType", "department", "accessLevel")


class QdrantSchemaError(RuntimeError):
    """Raised when an existing Qdrant collection violates the locked schema."""


class EmbeddingProvider(Protocol):
    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingVector, ...]:
        ...


@dataclass(frozen=True, slots=True)
class VectorIndexChunk:
    child: ChildChunk
    document_title: str
    language: str
    doc_type: str
    department: str
    access_level: str
    is_sanitized: bool = True
    sanitizer_flags: tuple[str, ...] = ()
    content_for_embedding: str | None = None
    payload_content: str | None = None

    @property
    def embedding_text(self) -> str:
        if self.content_for_embedding is not None:
            return self.content_for_embedding
        return self.child.content_for_embedding

    def to_payload(self) -> dict[str, object]:
        payload = self.child.to_qdrant_payload(
            document_title=self.document_title,
            language=self.language,
            doc_type=self.doc_type,
            department=self.department,
            access_level=self.access_level,
            is_sanitized=self.is_sanitized,
            sanitizer_flags=self.sanitizer_flags,
        )
        if self.payload_content is not None:
            payload["content"] = self.payload_content
        return payload


class QdrantVectorIndex:
    def __init__(
        self,
        client: AsyncQdrantClient,
        embedder: EmbeddingProvider | None = None,
        *,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        self._client = client
        self._embedder = embedder
        self._collection_name = collection_name

    @classmethod
    def from_url(cls, url: str, embedder: EmbeddingProvider | None = None) -> QdrantVectorIndex:
        return cls(AsyncQdrantClient(url=url), embedder=embedder)

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

    async def replace_document_chunks(self, document_id: UUID | str, chunks: Sequence[VectorIndexChunk]) -> None:
        if self._embedder is None:
            raise ValueError("embedder is required to replace document chunks")

        await self.delete_document(document_id)
        if not chunks:
            return

        embeddings = self._embedder.embed_texts([chunk.embedding_text for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise ValueError("embedding count must match chunk count")

        points = [
            point_struct(
                point_id=chunk.child.chunk_id,
                dense=embedding.dense,
                sparse=embedding.sparse,
                payload=chunk.to_payload(),
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        try:
            await self._client.upsert(
                collection_name=self._collection_name,
                points=points,
            )
        except StageFailure:
            raise
        except Exception as exc:  # pragma: no cover - exact Qdrant exceptions vary
            raise _vector_failure(exc) from exc

    async def delete_document(self, document_id: UUID | str) -> None:
        try:
            await self._client.delete(
                collection_name=self._collection_name,
                points_selector=document_filter(document_id),
            )
        except StageFailure:
            raise
        except Exception as exc:  # pragma: no cover - exact Qdrant exceptions vary
            raise _vector_failure(exc) from exc


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


def _vector_failure(exc: Exception) -> StageFailure:
    status_code = _status_code(exc)
    client_error = status_code is not None and 400 <= status_code < 500 and status_code != 429
    return stage_failure(
        stage=IndexingStage.VECTOR_UPSERT,
        error_code=INDEXING_PIPELINE_ERROR if client_error else DEPENDENCY_UNAVAILABLE,
        retryable=not client_error,
        detail=f"status_{status_code}" if status_code is not None else exc.__class__.__name__,
    )


def _status_code(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status if isinstance(response_status, int) else None
