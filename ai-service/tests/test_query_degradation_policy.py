from __future__ import annotations

from corp_rag_ai.domain.query import QueryRoute, RefusalReason
from corp_rag_ai.pipeline.generation.degradation_policy import DependencyState, EvidenceState, apply_degradation


def test_generation_unavailable_fails() -> None:
    outcome = apply_degradation(DependencyState(generation_unavailable=True), _evidence(), QueryRoute.FACTUAL)

    assert outcome.should_generate is False
    assert outcome.refusal_reason is RefusalReason.GENERATION_UNAVAILABLE


def test_vector_unavailable_fails_factual_and_comparison() -> None:
    for route in (QueryRoute.FACTUAL, QueryRoute.COMPARISON):
        outcome = apply_degradation(DependencyState(vector_unavailable=True), _evidence(), route)
        assert outcome.should_generate is False
        assert outcome.refusal_reason is RefusalReason.VECTOR_RETRIEVAL_UNAVAILABLE


def test_vector_unavailable_soft_degrades_aggregation_when_graph_evidence_exists() -> None:
    outcome = apply_degradation(
        DependencyState(vector_unavailable=True),
        EvidenceState(has_graph_evidence=True, top_score=0.7),
        QueryRoute.AGGREGATION,
    )

    assert outcome.should_generate is True
    assert outcome.warnings == ("vector_retrieval_unavailable",)


def test_graph_unavailable_does_not_block_factual() -> None:
    outcome = apply_degradation(DependencyState(graph_unavailable=True), _evidence(), QueryRoute.FACTUAL)

    assert outcome.should_generate is True
    assert outcome.warnings == ("graph_retrieval_unavailable",)


def test_graph_unavailable_fails_graph_first_routes() -> None:
    for route in (QueryRoute.AGGREGATION, QueryRoute.MULTI_HOP):
        outcome = apply_degradation(DependencyState(graph_unavailable=True), _evidence(), route)
        assert outcome.should_generate is False
        assert outcome.refusal_reason is RefusalReason.GRAPH_RETRIEVAL_UNAVAILABLE


def test_reranker_unavailable_soft_degrades_with_raw_confidence_source() -> None:
    outcome = apply_degradation(
        DependencyState(reranker_unavailable=True),
        EvidenceState(has_vector_evidence=True, top_score=0.7, reranker_used=False),
        QueryRoute.FACTUAL,
    )

    assert outcome.should_generate is True
    assert outcome.warnings == ("reranker_unavailable",)
    assert outcome.confidence_source == "raw_retrieval"


def test_embedding_unavailable_fails() -> None:
    outcome = apply_degradation(DependencyState(embedding_unavailable=True), _evidence(), QueryRoute.FACTUAL)

    assert outcome.should_generate is False
    assert outcome.refusal_reason is RefusalReason.EMBEDDING_UNAVAILABLE


def test_no_evidence_returns_actionable_refusal() -> None:
    outcome = apply_degradation(DependencyState(), EvidenceState(top_score=0.0), QueryRoute.FACTUAL)

    assert outcome.should_generate is False
    assert outcome.refusal_reason is RefusalReason.NO_EVIDENCE
    assert outcome.answer == "No accessible documents discuss this topic."


def test_weak_evidence_below_threshold_refuses() -> None:
    outcome = apply_degradation(
        DependencyState(),
        EvidenceState(has_vector_evidence=True, top_score=0.39, reranker_used=True),
        QueryRoute.FACTUAL,
    )

    assert outcome.should_generate is False
    assert outcome.refusal_reason is RefusalReason.WEAK_EVIDENCE
    assert outcome.confidence == 0.39
    assert "too weak" in outcome.answer


def _evidence() -> EvidenceState:
    return EvidenceState(has_vector_evidence=True, top_score=0.8, chunks_considered=3, chunks_returned=2)
