from __future__ import annotations

from enum import Enum

from corp_rag_ai.pipeline.indexing.vector_indexer import VectorQueryMode


class RetrievalMode(str, Enum):
    BM25 = "bm25"
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"
    HYBRID_RERANKER = "hybrid+reranker"

    @property
    def uses_reranker(self) -> bool:
        return self is RetrievalMode.HYBRID_RERANKER

    @property
    def is_vector_mode(self) -> bool:
        return self is not RetrievalMode.BM25

    def vector_query_mode(self) -> VectorQueryMode:
        if self is RetrievalMode.DENSE:
            return VectorQueryMode.DENSE
        if self is RetrievalMode.SPARSE:
            return VectorQueryMode.SPARSE
        if self in {RetrievalMode.HYBRID, RetrievalMode.HYBRID_RERANKER}:
            return VectorQueryMode.HYBRID
        raise ValueError("bm25 is a classical lexical eval baseline, not a Qdrant vector mode")
