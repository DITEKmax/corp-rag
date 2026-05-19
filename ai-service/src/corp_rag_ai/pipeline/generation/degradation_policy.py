from __future__ import annotations

from dataclasses import dataclass

from corp_rag_ai.domain.query import QueryRoute, RefusalReason

WEAK_EVIDENCE_THRESHOLD = 0.4


@dataclass(frozen=True, slots=True)
class DependencyState:
    generation_unavailable: bool = False
    vector_unavailable: bool = False
    graph_unavailable: bool = False
    reranker_unavailable: bool = False
    embedding_unavailable: bool = False


@dataclass(frozen=True, slots=True)
class EvidenceState:
    has_vector_evidence: bool = False
    has_graph_evidence: bool = False
    top_score: float = 0.0
    reranker_used: bool = True
    chunks_considered: int = 0
    chunks_returned: int = 0


@dataclass(frozen=True, slots=True)
class DegradationOutcome:
    should_generate: bool
    refusal_reason: RefusalReason | None = None
    answer: str = ""
    confidence: float = 0.0
    warnings: tuple[str, ...] = ()
    confidence_source: str = "reranker"


def apply_degradation(
    dependency_state: DependencyState,
    evidence_state: EvidenceState,
    route: QueryRoute,
) -> DegradationOutcome:
    warnings: list[str] = []
    if dependency_state.embedding_unavailable:
        return _failure(RefusalReason.EMBEDDING_UNAVAILABLE, "Query embedding is temporarily unavailable.")
    if dependency_state.generation_unavailable:
        return _failure(RefusalReason.GENERATION_UNAVAILABLE, "Answer generation is temporarily unavailable.")
    if dependency_state.vector_unavailable and route in {QueryRoute.FACTUAL, QueryRoute.COMPARISON}:
        return _failure(RefusalReason.VECTOR_RETRIEVAL_UNAVAILABLE, "Vector retrieval is temporarily unavailable.")
    if dependency_state.graph_unavailable and route in {QueryRoute.AGGREGATION, QueryRoute.MULTI_HOP}:
        return _failure(RefusalReason.GRAPH_RETRIEVAL_UNAVAILABLE, "Graph retrieval is temporarily unavailable.")
    if dependency_state.vector_unavailable and route in {QueryRoute.AGGREGATION, QueryRoute.MULTI_HOP}:
        if not evidence_state.has_graph_evidence:
            return _failure(RefusalReason.VECTOR_RETRIEVAL_UNAVAILABLE, "No accessible graph evidence is available.")
        warnings.append("vector_retrieval_unavailable")
    if dependency_state.graph_unavailable and route is QueryRoute.FACTUAL:
        warnings.append("graph_retrieval_unavailable")
    if dependency_state.reranker_unavailable:
        warnings.append("reranker_unavailable")

    confidence = _clamp(evidence_state.top_score)
    confidence_source = "reranker" if evidence_state.reranker_used and not dependency_state.reranker_unavailable else "raw_retrieval"
    if not evidence_state.has_vector_evidence and not evidence_state.has_graph_evidence:
        return _failure(RefusalReason.NO_EVIDENCE, "No accessible documents discuss this topic.", warnings=tuple(warnings))
    if confidence < WEAK_EVIDENCE_THRESHOLD:
        return _failure(
            RefusalReason.WEAK_EVIDENCE,
            "Accessible evidence is too weak to answer this question reliably.",
            confidence=confidence,
            warnings=tuple(warnings),
            confidence_source=confidence_source,
        )
    return DegradationOutcome(
        should_generate=True,
        confidence=confidence,
        warnings=tuple(warnings),
        confidence_source=confidence_source,
    )


def _failure(
    reason: RefusalReason,
    answer: str,
    *,
    confidence: float = 0.0,
    warnings: tuple[str, ...] = (),
    confidence_source: str = "none",
) -> DegradationOutcome:
    return DegradationOutcome(
        should_generate=False,
        refusal_reason=reason,
        answer=answer,
        confidence=confidence,
        warnings=warnings,
        confidence_source=confidence_source,
    )


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, float(value)))
