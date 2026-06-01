from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from corp_rag_ai.domain.query import AccessFilter
from corp_rag_ai.pipeline.indexing.embedding import EmbeddingVector
from corp_rag_ai.pipeline.retrieval.reranker import RerankOutcome
from eval.ablation_runner import (
    AblationRunnerConfig,
    AblationScope,
    ModeRecordResult,
    RetrievalHit,
    RetrievalMode,
    _bm25_result,
    _hybrid_reranker_result,
    build_ablation_report,
    indexed_document_id_map,
)
from eval.schema import GoldenRecord


def _record(record_id: str = "q1", expected_doc_ids: list[str] | None = None) -> GoldenRecord:
    return GoldenRecord(
        id=record_id,
        type="factual",
        question="question?",
        reference_answer="answer",
        expected_doc_ids=expected_doc_ids or ["indexed-1"],
        expected_outcome="answered",
    )


class _FakeBm25Index:
    def search(self, _query: str, *, k: int):
        assert k == 10
        return (
            SimpleNamespace(
                rank=1,
                document_id="CORP-RU-AV-001",
                score=3.5,
                document=SimpleNamespace(title="Manifest title"),
            ),
        )


def test_bm25_result_maps_manifest_ids_to_indexed_document_ids() -> None:
    result = _bm25_result(
        _FakeBm25Index(),
        _record(),
        manifest_to_indexed_doc_id={"CORP-RU-AV-001": "indexed-1"},
        limit=10,
    )

    assert result.mode is RetrievalMode.BM25
    assert result.retrieved_doc_ids == ("indexed-1",)
    assert result.to_detail_row()["recall@5"] == 1.0


def test_build_ablation_report_keeps_all_five_vector_modes_distinct() -> None:
    record = _record()
    mode_results = {
        mode: (ModeRecordResult(mode=mode, record=record, hits=(RetrievalHit(rank=1, document_id="indexed-1"),)),)
        for mode in (
            RetrievalMode.BM25,
            RetrievalMode.DENSE,
            RetrievalMode.SPARSE,
            RetrievalMode.HYBRID,
            RetrievalMode.HYBRID_RERANKER,
        )
    }
    report = build_ablation_report(
        config=AblationRunnerConfig(reports_dir=Path(".")),
        corpus_version="corpus-v1",
        corpus_hash="hash",
        qdrant_point_count=16,
        scope=AblationScope(vector_records=(record,), graph_records=(), excluded_records=(), route_discrepancies=()),
        mode_results=mode_results,
        graph_results=(),
    )

    assert list(report["vector_metrics"]) == ["bm25", "dense", "sparse", "hybrid", "hybrid+reranker"]
    assert all(metrics["recall@10"] == 1.0 for metrics in report["vector_metrics"].values())
    assert report["external_judge_used"] is False


def test_indexed_document_id_map_reads_extra_metadata_entries() -> None:
    metadata = SimpleNamespace(
        indexed_document_map=[
            {"manifest_doc_id": "CORP-RU-AV-001", "indexed_document_id": "uuid-1"},
            {"manifest_doc_id": "", "indexed_document_id": "ignored"},
        ]
    )

    assert indexed_document_id_map(metadata) == {"CORP-RU-AV-001": "uuid-1"}


async def test_hybrid_reranker_result_reranks_hybrid_candidates_not_source_citations() -> None:
    doc_a = uuid4()
    doc_b = uuid4()
    chunk_a = uuid4()
    chunk_b = uuid4()

    class _FakeVectorIndex:
        async def query_hybrid(self, **kwargs):
            assert kwargs["mode"] is RetrievalMode.HYBRID.vector_query_mode()
            return SimpleNamespace(
                points=(
                    SimpleNamespace(
                        score=0.4,
                        payload={
                            "chunkId": str(chunk_a),
                            "documentId": str(doc_a),
                            "documentTitle": "A",
                            "content": "less relevant",
                            "accessLevel": "PUBLIC",
                        },
                    ),
                    SimpleNamespace(
                        score=0.3,
                        payload={
                            "chunkId": str(chunk_b),
                            "documentId": str(doc_b),
                            "documentTitle": "B",
                            "content": "more relevant",
                            "accessLevel": "PUBLIC",
                        },
                    ),
                )
            )

    class _FakeEmbedder:
        def embed_texts(self, texts):
            assert texts == ["question?"]
            return (EmbeddingVector(dense=(0.1, 0.2), sparse={1: 0.5}),)

    class _FakeReranker:
        async def rerank(self, *, query, candidates, top_n):
            assert query == "question?"
            assert top_n == 2
            return RerankOutcome(candidates=tuple(reversed(candidates)), reranker_used=True)

    result = await _hybrid_reranker_result(
        _FakeVectorIndex(),
        _FakeEmbedder(),
        _FakeReranker(),
        _record(expected_doc_ids=[str(doc_b)]),
        access_filter=AccessFilter(access_levels=("PUBLIC",), departments=(), doc_types=("POLICY",)),
        limit=2,
        prefetch_limit=2,
    )

    assert result.mode is RetrievalMode.HYBRID_RERANKER
    assert result.retrieved_doc_ids == (str(doc_b), str(doc_a))
    assert result.to_detail_row()["mrr"] == 1.0
