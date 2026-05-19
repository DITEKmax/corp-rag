from __future__ import annotations

from typing import TypedDict

from corp_rag_ai.domain.guard import GuardVerdict
from corp_rag_ai.domain.query import QueryInput, QueryResult, RouteDecision
from corp_rag_ai.domain.retrieval import RetrievalResult
from corp_rag_ai.pipeline.generation.degradation_policy import DegradationOutcome, DependencyState, EvidenceState
from corp_rag_ai.pipeline.generation.synthesizer import SynthesisResult
from corp_rag_ai.pipeline.guards.input_guard import GuardOutcome
from corp_rag_ai.pipeline.retrieval.context_packer import PackedContext
from corp_rag_ai.pipeline.retrieval.parent_resolver import ParentResolution
from corp_rag_ai.pipeline.retrieval.reranker import RerankOutcome


class QueryGraphState(TypedDict, total=False):
    query: QueryInput
    started_at: float
    guard_outcome: GuardOutcome
    route_decision: RouteDecision
    retrieval_result: RetrievalResult
    parent_resolution: ParentResolution
    rerank_outcome: RerankOutcome
    dependency_state: DependencyState
    evidence_state: EvidenceState
    degradation_outcome: DegradationOutcome
    packed_context: PackedContext
    synthesis_result: SynthesisResult
    output_guard_verdict: GuardVerdict
    final_result: QueryResult
    warnings: tuple[str, ...]
