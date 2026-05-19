from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol
from uuid import UUID

from corp_rag_ai.domain.exceptions import StageFailure
from corp_rag_ai.domain.query import QueryInput, QueryRoute
from corp_rag_ai.domain.retrieval import (
    RetrievalCandidate,
    RetrievalFailureReason,
    RetrievalMetadata,
    RetrievalResult,
    RetrieverType,
)
from corp_rag_ai.pipeline.indexing.embedding import EmbeddingVector
from corp_rag_ai.pipeline.indexing.vector_indexer import QdrantVectorIndex

DEFAULT_PREFETCH_LIMIT = 30
MIN_PREFETCH_LIMIT = 20
DEFAULT_FLAGGED_SCORE_MULTIPLIER = 0.5


class QueryEmbedder(Protocol):
    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingVector, ...]:
        ...


class HybridRetriever:
    def __init__(
        self,
        *,
        vector_index: QdrantVectorIndex,
        embedder: QueryEmbedder,
        prefetch_limit: int = DEFAULT_PREFETCH_LIMIT,
        flagged_score_multiplier: float = DEFAULT_FLAGGED_SCORE_MULTIPLIER,
    ) -> None:
        if prefetch_limit < 1:
            raise ValueError("prefetch_limit must be positive")
        if not 0.0 <= flagged_score_multiplier <= 1.0:
            raise ValueError("flagged score multiplier must be between 0.0 and 1.0")
        self._vector_index = vector_index
        self._embedder = embedder
        self._prefetch_limit = prefetch_limit
        self._flagged_score_multiplier = flagged_score_multiplier

    async def retrieve(self, query: QueryInput, *, model_id: str = "") -> RetrievalResult:
        top_k = query.retrieval_options.top_k
        prefetch_limit = min(self._prefetch_limit, max(MIN_PREFETCH_LIMIT, top_k * 2))
        try:
            embeddings = self._embedder.embed_texts([query.message])
            if len(embeddings) != 1:
                raise ValueError("query embedding count mismatch")
            query_embedding = embeddings[0]
        except Exception:
            return _failure_result(
                reason=RetrievalFailureReason.EMBEDDING_UNAVAILABLE,
                warning=RetrievalFailureReason.EMBEDDING_UNAVAILABLE.value,
                model_id=model_id,
            )

        try:
            response = await self._vector_index.query_hybrid(
                query_embedding=query_embedding,
                access_filter=query.access_filter,
                limit=prefetch_limit,
                prefetch_limit=prefetch_limit,
            )
        except StageFailure:
            return _failure_result(
                reason=RetrievalFailureReason.VECTOR_RETRIEVAL_UNAVAILABLE,
                warning=RetrievalFailureReason.VECTOR_RETRIEVAL_UNAVAILABLE.value,
                model_id=model_id,
            )
        except Exception:
            return _failure_result(
                reason=RetrievalFailureReason.VECTOR_RETRIEVAL_UNAVAILABLE,
                warning=RetrievalFailureReason.VECTOR_RETRIEVAL_UNAVAILABLE.value,
                model_id=model_id,
            )

        points = tuple(_response_points(response))
        candidates = tuple(
            sorted(
                (_candidate_from_point(point, self._flagged_score_multiplier) for point in points),
                key=lambda candidate: candidate.score,
                reverse=True,
            )
        )[:top_k]
        return RetrievalResult(
            candidates=candidates,
            metadata=RetrievalMetadata(
                route=QueryRoute.FACTUAL,
                retrievers_attempted=(RetrieverType.HYBRID,),
                retrievers_used=(RetrieverType.HYBRID,) if candidates else (),
                degradation_warnings=(),
                latency_ms=0,
                chunks_considered=len(points),
                chunks_returned=len(candidates),
                reranker_used=False,
                model_id=model_id,
            ),
        )


def _failure_result(
    *,
    reason: RetrievalFailureReason,
    warning: str,
    model_id: str,
) -> RetrievalResult:
    return RetrievalResult(
        candidates=(),
        metadata=RetrievalMetadata(
            route=QueryRoute.FACTUAL,
            retrievers_attempted=(RetrieverType.HYBRID,),
            retrievers_used=(),
            degradation_warnings=(warning,),
            latency_ms=0,
            chunks_considered=0,
            chunks_returned=0,
            reranker_used=False,
            model_id=model_id,
        ),
        failure_reason=reason,
    )


def _response_points(response: Any) -> Sequence[Any]:
    points = getattr(response, "points", response)
    return points if points is not None else ()


def _candidate_from_point(point: Any, flagged_score_multiplier: float) -> RetrievalCandidate:
    payload = dict(getattr(point, "payload", None) or {})
    raw_score = float(getattr(point, "score", 0.0) or 0.0)
    is_sanitized = bool(payload.get("isSanitized", True))
    score = raw_score if is_sanitized else raw_score * flagged_score_multiplier
    return RetrievalCandidate(
        chunk_id=UUID(str(payload["chunkId"])),
        parent_chunk_id=_optional_uuid(payload.get("parentChunkId")),
        document_id=UUID(str(payload["documentId"])),
        document_title=str(payload.get("documentTitle", "")),
        section_path=_section_path(payload.get("sectionPath")),
        content=str(payload.get("content", "")),
        snippet=_snippet(payload.get("content")),
        page_number=_optional_int(payload.get("page")),
        score=score,
        access_level=str(payload.get("accessLevel", "")),
        retriever=RetrieverType.HYBRID,
        sanitizer_flags=tuple(str(flag) for flag in payload.get("sanitizerFlags", []) or []),
    )


def _section_path(value: object) -> tuple[str, ...]:
    if isinstance(value, list | tuple):
        return tuple(str(part) for part in value if str(part).strip())
    if value is None:
        return ()
    return tuple(part.strip() for part in str(value).split(">") if part.strip())


def _snippet(value: object, *, max_length: int = 500) -> str:
    text = str(value or "").strip()
    return text[:max_length]


def _optional_uuid(value: object) -> UUID | None:
    return UUID(str(value)) if value else None


def _optional_int(value: object) -> int | None:
    return int(value) if value is not None else None
