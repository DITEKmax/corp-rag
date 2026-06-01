from __future__ import annotations

from pathlib import Path

from eval.ablation_runner import (
    AblationRunnerConfig,
    AblationScope,
    GraphRecordResult,
    RouteDetail,
    _graph_metric_summary,
    build_ablation_report,
    render_ablation_markdown,
)
from eval.schema import GoldenRecord


def _record(record_id: str, expected_doc_ids: list[str]) -> GoldenRecord:
    return GoldenRecord(
        id=record_id,
        type="multi_hop",
        question=f"{record_id}?",
        reference_answer="answer",
        expected_doc_ids=expected_doc_ids,
        expected_outcome="answered",
    )


def test_graph_report_rows_include_refusal_behavior_and_expected_overlap() -> None:
    result = GraphRecordResult(
        _record("graph-1", ["doc-a", "doc-b"]),
        RouteDetail(
            record_id="graph-1",
            route="MULTI_HOP",
            retrievers_attempted=("GRAPH",),
            actual_outcome="answered",
            citation_document_ids=("doc-b",),
        ),
    )

    row = result.to_detail_row()

    assert row["citeable_evidence_found"] is True
    assert row["no_evidence_refusal"] is False
    assert row["recall@5"] == 0.5
    assert row["mrr"] == 1.0


def test_graph_metrics_are_separate_from_vector_report() -> None:
    graph_result = GraphRecordResult(
        _record("graph-1", ["doc-a"]),
        RouteDetail(
            record_id="graph-1",
            route="MULTI_HOP",
            retrievers_attempted=("GRAPH",),
            actual_outcome="refused_no_evidence",
            citation_document_ids=(),
        ),
    )
    report = build_ablation_report(
        config=AblationRunnerConfig(reports_dir=Path(".")),
        corpus_version="corpus-v1",
        corpus_hash="hash",
        qdrant_point_count=16,
        scope=AblationScope(vector_records=(), graph_records=(_record("graph-1", ["doc-a"]),), excluded_records=(), route_discrepancies=()),
        mode_results={},
        graph_results=(graph_result,),
    )
    markdown = render_ablation_markdown(report)

    assert _graph_metric_summary((graph_result,))["no_evidence_refusal_count"] == 1
    assert report["graph_report"]["metrics"]["record_count"] == 1
    assert "not comparable to BM25/dense/sparse/hybrid vector modes" in markdown
