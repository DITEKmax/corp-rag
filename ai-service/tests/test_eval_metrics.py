from __future__ import annotations

import pytest

from eval.metrics import (
    RetrievalObservation,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
    score_observations,
    summarize_retrieval_metrics,
)


def test_recall_at_k_uses_document_ids_and_dedupes_retrieved_docs() -> None:
    score = recall_at_k(
        ["CORP-RU-AV-001", "CORP-RU-AV-002"],
        ["CORP-RU-AV-001", "CORP-RU-AV-001", "CORP-RU-AV-003", "CORP-RU-AV-002"],
        k=3,
    )

    assert score == 0.5


def test_mrr_returns_first_expected_document_rank() -> None:
    score = reciprocal_rank(
        ["CORP-RU-AV-002"],
        ["CORP-RU-AV-009", "CORP-RU-AV-002", "CORP-RU-AV-001"],
    )

    assert score == 0.5


def test_ndcg_at_k_uses_binary_document_relevance() -> None:
    score = ndcg_at_k(
        ["CORP-RU-AV-001", "CORP-RU-AV-002"],
        ["CORP-RU-AV-003", "CORP-RU-AV-002", "CORP-RU-AV-001"],
        k=3,
    )

    assert score == pytest.approx((1 / 1.584962500721156 + 1 / 2) / (1 + 1 / 1.584962500721156))


def test_score_observations_skips_records_without_expected_documents() -> None:
    scores = score_observations(
        [
            RetrievalObservation(
                record_id="answered",
                expected_doc_ids=("CORP-RU-AV-001",),
                retrieved_doc_ids=("CORP-RU-AV-001",),
            ),
            RetrievalObservation(
                record_id="refused",
                expected_doc_ids=(),
                retrieved_doc_ids=("CORP-RU-AV-001",),
            ),
        ],
        ks=(5, 10),
    )

    assert len(scores) == 1
    assert scores[0].record_id == "answered"
    assert scores[0].recall_by_k[5] == 1.0
    assert scores[0].reciprocal_rank == 1.0


def test_summarize_retrieval_metrics_reports_recall_and_mrr_means() -> None:
    metrics = summarize_retrieval_metrics(
        [
            RetrievalObservation(
                record_id="q1",
                expected_doc_ids=("A",),
                retrieved_doc_ids=("A", "B"),
            ),
            RetrievalObservation(
                record_id="q2",
                expected_doc_ids=("C",),
                retrieved_doc_ids=("B", "C"),
            ),
        ],
        ks=(1, 2),
    )

    values = {metric.name: metric.value for metric in metrics}
    assert values == {
        "recall@1": 0.5,
        "recall@2": 1.0,
        "mrr": 0.75,
    }


def test_metric_helpers_validate_positive_k() -> None:
    with pytest.raises(ValueError, match="positive"):
        recall_at_k(["A"], ["A"], k=0)
    with pytest.raises(ValueError, match="positive"):
        ndcg_at_k(["A"], ["A"], k=0)
    with pytest.raises(ValueError, match="positive"):
        summarize_retrieval_metrics([RetrievalObservation("q", ("A",), ("A",))], ks=(0,))
