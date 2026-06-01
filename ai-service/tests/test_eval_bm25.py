from __future__ import annotations

import pytest

from eval.bm25 import BM25Document, BM25Index
from eval.retrieval_modes import RetrievalMode
from corp_rag_ai.pipeline.indexing.vector_indexer import VectorQueryMode


def test_bm25_index_returns_ranked_classical_lexical_hits() -> None:
    index = BM25Index(
        [
            BM25Document(
                document_id="CORP-RU-AV-001",
                title="Регламент багажа",
                text="Исключение по багажу оформляет сменный супервайзер.",
            ),
            BM25Document(
                document_id="CORP-RU-AV-002",
                title="Топливо",
                text="Резерв топлива рассчитывает диспетчер.",
            ),
        ]
    )

    hits = index.search("кто оформляет исключение по багажу", k=2)

    assert [hit.document_id for hit in hits] == ["CORP-RU-AV-001"]
    assert hits[0].rank == 1
    assert hits[0].score > 0
    assert hits[0].document.title == "Регламент багажа"


def test_bm25_index_rejects_empty_corpus_and_non_positive_k() -> None:
    with pytest.raises(ValueError, match="at least one document"):
        BM25Index([])

    index = BM25Index([BM25Document(document_id="D1", text="text")])
    with pytest.raises(ValueError, match="k must be positive"):
        index.search("text", k=0)


def test_retrieval_modes_keep_bm25_distinct_from_learned_sparse() -> None:
    assert RetrievalMode.BM25.is_vector_mode is False
    assert RetrievalMode.SPARSE.vector_query_mode() is VectorQueryMode.SPARSE
    assert RetrievalMode.DENSE.vector_query_mode() is VectorQueryMode.DENSE
    assert RetrievalMode.HYBRID_RERANKER.vector_query_mode() is VectorQueryMode.HYBRID
    assert RetrievalMode.HYBRID_RERANKER.uses_reranker is True

    with pytest.raises(ValueError, match="classical lexical"):
        RetrievalMode.BM25.vector_query_mode()
