from __future__ import annotations

from eval.ablation_runner import RouteDetail, select_ablation_scope
from eval.schema import GoldenRecord


def _record(record_id: str, question_type: str, expected_doc_ids: list[str] | None = None) -> GoldenRecord:
    docs = ["doc-1"] if expected_doc_ids is None else expected_doc_ids
    return GoldenRecord(
        id=record_id,
        type=question_type,
        question=f"{record_id}?",
        reference_answer="answer",
        expected_doc_ids=docs,
        expected_outcome="answered" if docs else "refused_no_evidence",
    )


def test_select_ablation_scope_uses_actual_retrieval_metadata() -> None:
    records = (
        _record("factual-vector", "factual"),
        _record("factual-unsupported", "factual"),
        _record("aggregation-graph", "aggregation"),
        _record("multi-hop-routed-vector", "multi_hop"),
        _record("out-of-scope", "out_of_scope", []),
    )
    route_details = {
        "factual-vector": RouteDetail(record_id="factual-vector", route="FACTUAL", retrievers_attempted=("HYBRID",)),
        "factual-unsupported": RouteDetail(record_id="factual-unsupported", route="UNSUPPORTED"),
        "aggregation-graph": RouteDetail(record_id="aggregation-graph", route="AGGREGATION", retrievers_attempted=("GRAPH",)),
        "multi-hop-routed-vector": RouteDetail(
            record_id="multi-hop-routed-vector",
            route="COMPARISON",
            retrievers_attempted=("HYBRID",),
        ),
        "out-of-scope": RouteDetail(record_id="out-of-scope", route="UNSUPPORTED"),
    }

    scope = select_ablation_scope(records, route_details)

    assert scope.vector_ids == ("factual-vector", "multi-hop-routed-vector")
    assert scope.graph_ids == ("aggregation-graph",)
    assert [(item.record_id, item.reason) for item in scope.excluded_records] == [
        ("factual-unsupported", "non_retrieval_route"),
        ("out-of-scope", "no_expected_doc_ids"),
    ]
    assert [(item.record_id, item.golden_type, item.route, item.retrieval_family) for item in scope.route_discrepancies] == [
        ("factual-unsupported", "factual", "UNSUPPORTED", "excluded"),
        ("multi-hop-routed-vector", "multi_hop", "COMPARISON", "vector")
    ]
