from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from corp_rag_ai.domain.query import AccessFilter, QueryInput, RetrievalOptions
from corp_rag_ai.domain.retrieval import RetrievalFailureReason, RetrieverType
from corp_rag_ai.pipeline.indexing.embedding import EmbeddingVector
from corp_rag_ai.pipeline.retrieval.hybrid import HybridRetriever


USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CORRELATION_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
CONVERSATION_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
DOCUMENT_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
CHUNK_ID = UUID("11111111-1111-4111-8111-111111111042")
PARENT_CHUNK_ID = UUID("22222222-2222-4222-8222-222222222017")


async def test_hybrid_retriever_embeds_query_and_maps_qdrant_payload_candidates() -> None:
    embedder = _FakeEmbedder((EmbeddingVector(dense=(0.1, 0.2), sparse={7: 0.7}),))
    vector_index = _FakeVectorIndex([_point(score=0.81)])
    retriever = HybridRetriever(vector_index=vector_index, embedder=embedder)  # type: ignore[arg-type]

    result = await retriever.retrieve(_query("What is the vacation policy?", top_k=3), model_id="bge-m3")

    assert embedder.text_batches == [["What is the vacation policy?"]]
    assert len(vector_index.query_calls) == 1
    call = vector_index.query_calls[0]
    assert call["query_embedding"].dense == (0.1, 0.2)
    assert call["access_filter"].access_levels == ("PUBLIC", "INTERNAL")
    assert call["limit"] == 20
    assert call["prefetch_limit"] == 20

    assert result.failed is False
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.chunk_id == CHUNK_ID
    assert candidate.parent_chunk_id == PARENT_CHUNK_ID
    assert candidate.document_id == DOCUMENT_ID
    assert candidate.document_title == "Vacation Policy"
    assert candidate.section_path == ("HR", "Leave")
    assert candidate.content == "Employees receive annual vacation according to tenure."
    assert candidate.snippet == "Employees receive annual vacation according to tenure."
    assert candidate.score == 0.81
    assert candidate.retriever is RetrieverType.HYBRID
    assert result.metadata.retrievers_attempted == (RetrieverType.HYBRID,)
    assert result.metadata.retrievers_used == (RetrieverType.HYBRID,)
    assert result.metadata.chunks_considered == 1
    assert result.metadata.chunks_returned == 1
    assert result.metadata.reranker_used is False
    assert result.metadata.model_id == "bge-m3"


async def test_embedding_failure_returns_explicit_failure_without_qdrant_call() -> None:
    embedder = _FailingEmbedder()
    vector_index = _FakeVectorIndex([_point()])
    retriever = HybridRetriever(vector_index=vector_index, embedder=embedder)  # type: ignore[arg-type]

    result = await retriever.retrieve(_query("What is the vacation policy?"))

    assert result.failed is True
    assert result.failure_reason is RetrievalFailureReason.EMBEDDING_UNAVAILABLE
    assert result.candidates == ()
    assert result.metadata.retrievers_attempted == (RetrieverType.HYBRID,)
    assert result.metadata.retrievers_used == ()
    assert result.metadata.degradation_warnings == ("embedding_unavailable",)
    assert vector_index.query_calls == []


async def test_empty_qdrant_results_are_legitimate_no_evidence_result() -> None:
    retriever = HybridRetriever(
        vector_index=_FakeVectorIndex([]),  # type: ignore[arg-type]
        embedder=_FakeEmbedder((EmbeddingVector(dense=(0.1,), sparse={1: 0.1}),)),
    )

    result = await retriever.retrieve(_query("What is the vacation policy?"))

    assert result.failed is False
    assert result.candidates == ()
    assert result.metadata.retrievers_attempted == (RetrieverType.HYBRID,)
    assert result.metadata.retrievers_used == ()
    assert result.metadata.chunks_considered == 0
    assert result.metadata.chunks_returned == 0
    assert result.metadata.degradation_warnings == ()


async def test_vector_dependency_failure_is_distinct_from_zero_results() -> None:
    retriever = HybridRetriever(
        vector_index=_FailingVectorIndex(),  # type: ignore[arg-type]
        embedder=_FakeEmbedder((EmbeddingVector(dense=(0.1,), sparse={1: 0.1}),)),
    )

    result = await retriever.retrieve(_query("What is the vacation policy?"))

    assert result.failed is True
    assert result.failure_reason is RetrievalFailureReason.VECTOR_RETRIEVAL_UNAVAILABLE
    assert result.candidates == ()
    assert result.metadata.degradation_warnings == ("vector_retrieval_unavailable",)
    assert result.metadata.chunks_considered == 0
    assert result.metadata.chunks_returned == 0


async def test_flagged_chunks_are_downranked_not_excluded_and_flags_are_preserved() -> None:
    clean = _point(chunk_id=UUID("33333333-3333-4333-8333-333333333333"), score=0.8, is_sanitized=True)
    flagged = _point(
        chunk_id=UUID("44444444-4444-4444-8444-444444444444"),
        score=0.8,
        is_sanitized=False,
        sanitizer_flags=("PROMPT_IGNORE_INSTRUCTIONS",),
    )
    retriever = HybridRetriever(
        vector_index=_FakeVectorIndex([flagged, clean]),  # type: ignore[arg-type]
        embedder=_FakeEmbedder((EmbeddingVector(dense=(0.1,), sparse={1: 0.1}),)),
        flagged_score_multiplier=0.5,
    )

    result = await retriever.retrieve(_query("What is the vacation policy?"))

    assert [candidate.chunk_id for candidate in result.candidates] == [
        UUID("33333333-3333-4333-8333-333333333333"),
        UUID("44444444-4444-4444-8444-444444444444"),
    ]
    assert result.candidates[0].score == 0.8
    assert result.candidates[1].score == 0.4
    assert result.candidates[1].sanitizer_flags == ("PROMPT_IGNORE_INSTRUCTIONS",)
    assert result.metadata.chunks_considered == 2
    assert result.metadata.chunks_returned == 2


class _FakeEmbedder:
    def __init__(self, embeddings: tuple[EmbeddingVector, ...]) -> None:
        self.embeddings = embeddings
        self.text_batches: list[list[str]] = []

    def embed_texts(self, texts) -> tuple[EmbeddingVector, ...]:
        self.text_batches.append(list(texts))
        return self.embeddings


class _FailingEmbedder:
    def embed_texts(self, _texts):
        raise RuntimeError("embedding unavailable")


class _FakeVectorIndex:
    def __init__(self, points: list[_Point]) -> None:
        self.points = points
        self.query_calls: list[dict[str, object]] = []

    async def query_hybrid(self, **kwargs):
        self.query_calls.append(kwargs)
        return _Response(tuple(self.points))


class _FailingVectorIndex:
    async def query_hybrid(self, **_kwargs):
        raise RuntimeError("qdrant unavailable")


@dataclass(frozen=True, slots=True)
class _Response:
    points: tuple["_Point", ...]


@dataclass(frozen=True, slots=True)
class _Point:
    payload: dict[str, object]
    score: float


def _query(message: str, *, top_k: int = 5) -> QueryInput:
    return QueryInput(
        user_id=USER_ID,
        correlation_id=CORRELATION_ID,
        conversation_id=CONVERSATION_ID,
        message=message,
        access_filter=AccessFilter(access_levels=("PUBLIC", "INTERNAL"), departments=("HR",), doc_types=("POLICY",)),
        retrieval_options=RetrievalOptions.from_values(top_k=top_k),
    )


def _point(
    *,
    chunk_id: UUID = CHUNK_ID,
    score: float = 0.8,
    is_sanitized: bool = True,
    sanitizer_flags: tuple[str, ...] = (),
) -> _Point:
    return _Point(
        score=score,
        payload={
            "chunkId": str(chunk_id),
            "parentChunkId": str(PARENT_CHUNK_ID),
            "documentId": str(DOCUMENT_ID),
            "documentTitle": "Vacation Policy",
            "sectionPath": ["HR", "Leave"],
            "content": "Employees receive annual vacation according to tenure.",
            "page": 4,
            "docType": "POLICY",
            "department": "HR",
            "accessLevel": "INTERNAL",
            "isSanitized": is_sanitized,
            "sanitizerFlags": list(sanitizer_flags),
        },
    )
