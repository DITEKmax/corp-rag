from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from corp_rag_ai.agent.state import QueryGraphState
from corp_rag_ai.domain.guard import GuardReason, GuardVerdict
from corp_rag_ai.domain.query import QueryInput, QueryResult, QueryRoute, RefusalReason, RouteDecision, RouteSource
from corp_rag_ai.domain.retrieval import CitationDraft, RetrievalFailureReason, RetrievalMetadata, RetrieverType
from corp_rag_ai.pipeline.generation.degradation_policy import DependencyState, EvidenceState, apply_degradation
from corp_rag_ai.pipeline.generation.synthesizer import SynthesisResult
from corp_rag_ai.pipeline.retrieval.context_packer import PackedContext
from corp_rag_ai.pipeline.retrieval.reranker import RERANKER_DISABLED_WARNING, RERANKER_UNAVAILABLE_WARNING, RerankOutcome


UNSUPPORTED_ANSWER = "I can answer supported questions about accessible corporate documents."
OUTPUT_GUARD_ANSWER = "I cannot return an answer that fails citation or safety checks."
GRAPH_DEPTH_ANSWER = "This graph question exceeds the supported multi-hop depth."


@dataclass(slots=True)
class QueryGraphComponents:
    input_guard: Any
    router: Any
    hybrid_retriever: Any
    graph_retriever: Any
    parent_resolver: Any
    reranker: Any
    context_packer: Any
    synthesizer: Any
    output_guard: Any
    model_id: str
    final_top_n: int = 5
    clock: Callable[[], float] = time.perf_counter


def build_query_graph(components: QueryGraphComponents) -> Any:
    graph = StateGraph(QueryGraphState)
    nodes = _QueryGraphNodes(components)

    graph.add_node("input_guard", nodes.input_guard)
    graph.add_node("route", nodes.route)
    graph.add_node("hybrid_retrieval", nodes.hybrid_retrieval)
    graph.add_node("graph_retrieval", nodes.graph_retrieval)
    graph.add_node("parent_resolve", nodes.parent_resolve)
    graph.add_node("rerank", nodes.rerank)
    graph.add_node("pack_context", nodes.pack_context)
    graph.add_node("synthesize", nodes.synthesize)
    graph.add_node("output_guard", nodes.output_guard)
    graph.add_node("finalize", nodes.finalize)

    graph.add_edge(START, "input_guard")
    graph.add_conditional_edges("input_guard", _after_input_guard, {"reject": "finalize", "continue": "route"})
    graph.add_conditional_edges(
        "route",
        _after_route,
        {
            "unsupported": "finalize",
            "hybrid": "hybrid_retrieval",
            "graph": "graph_retrieval",
        },
    )
    graph.add_edge("hybrid_retrieval", "parent_resolve")
    graph.add_edge("graph_retrieval", "parent_resolve")
    graph.add_edge("parent_resolve", "rerank")
    graph.add_edge("rerank", "pack_context")
    graph.add_conditional_edges("pack_context", _after_pack_context, {"refuse": "finalize", "generate": "synthesize"})
    graph.add_edge("synthesize", "output_guard")
    graph.add_edge("output_guard", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


class _QueryGraphNodes:
    def __init__(self, components: QueryGraphComponents) -> None:
        self._components = components

    async def input_guard(self, state: QueryGraphState) -> QueryGraphState:
        query = state["query"]
        outcome = self._components.input_guard.guard(query)
        update: QueryGraphState = {"guard_outcome": outcome}
        if outcome.refusal_result is not None:
            update["final_result"] = outcome.refusal_result
        return update

    async def route(self, state: QueryGraphState) -> QueryGraphState:
        query = state["query"]
        decision = await self._components.router.route(query)
        return {"route_decision": decision}

    async def hybrid_retrieval(self, state: QueryGraphState) -> QueryGraphState:
        result = await self._components.hybrid_retriever.retrieve(state["query"], model_id=self._components.model_id)
        return {"retrieval_result": result}

    async def graph_retrieval(self, state: QueryGraphState) -> QueryGraphState:
        route = state["route_decision"].route
        result = await self._components.graph_retriever.retrieve(
            state["query"],
            route=route,
            model_id=self._components.model_id,
        )
        return {"retrieval_result": result}

    async def parent_resolve(self, state: QueryGraphState) -> QueryGraphState:
        result = state["retrieval_result"]
        if result.failure_reason == RetrievalFailureReason.UNSUPPORTED_GRAPH_DEPTH:
            return {
                "final_result": self._refusal(
                    state,
                    reason=RefusalReason.UNSUPPORTED,
                    answer=GRAPH_DEPTH_ANSWER,
                    warnings=(RetrievalFailureReason.UNSUPPORTED_GRAPH_DEPTH.value,),
                )
            }
        resolution = await self._components.parent_resolver.resolve(result.candidates)
        return {"parent_resolution": resolution}

    async def rerank(self, state: QueryGraphState) -> QueryGraphState:
        query = state["query"]
        resolution = state["parent_resolution"]
        candidates = resolution.citation_candidates
        if not query.retrieval_options.reranker_enabled:
            outcome = RerankOutcome(
                candidates=candidates[: self._components.final_top_n],
                reranker_used=False,
                warnings=(RERANKER_DISABLED_WARNING,),
            )
        else:
            outcome = await self._components.reranker.rerank(
                query=query.message,
                candidates=candidates,
                top_n=self._components.final_top_n,
            )
        return {"rerank_outcome": outcome}

    async def pack_context(self, state: QueryGraphState) -> QueryGraphState:
        dependency_state = _dependency_state(state)
        evidence_state = _evidence_state(state)
        route = _route(state)
        degradation = apply_degradation(dependency_state, evidence_state, route)
        update: QueryGraphState = {
            "dependency_state": dependency_state,
            "evidence_state": evidence_state,
            "degradation_outcome": degradation,
        }
        if not degradation.should_generate:
            update["final_result"] = self._refusal(
                state,
                reason=degradation.refusal_reason or RefusalReason.NO_EVIDENCE,
                answer=degradation.answer,
                confidence=degradation.confidence,
                warnings=degradation.warnings,
            )
            return update

        packed = self._components.context_packer.pack(state["parent_resolution"], state["rerank_outcome"].candidates)
        update["packed_context"] = packed
        return update

    async def synthesize(self, state: QueryGraphState) -> QueryGraphState:
        result = await self._components.synthesizer.synthesize(state["query"], state["packed_context"])
        if result.failure_reason is not None:
            dependency_state = replace(state["dependency_state"], generation_unavailable=True)
            degradation = apply_degradation(dependency_state, state["evidence_state"], _route(state))
            return {
                "dependency_state": dependency_state,
                "degradation_outcome": degradation,
                "synthesis_result": result,
                "final_result": self._refusal(
                    state,
                    reason=degradation.refusal_reason or result.failure_reason,
                    answer=degradation.answer or result.answer,
                    confidence=degradation.confidence,
                    warnings=(*state.get("warnings", ()), RefusalReason.GENERATION_UNAVAILABLE.value),
                ),
            }
        return {"synthesis_result": result}

    async def output_guard(self, state: QueryGraphState) -> QueryGraphState:
        synthesis = state["synthesis_result"]
        if not synthesis.answered:
            return {
                "final_result": self._refusal(
                    state,
                    reason=RefusalReason.NO_EVIDENCE,
                    answer=synthesis.answer or "The provided evidence does not support an answer.",
                    confidence=synthesis.confidence_hint,
                )
            }

        packed = state["packed_context"]
        reranked = state["rerank_outcome"]
        verdict = self._components.output_guard.validate(
            synthesis,
            citations=packed.citations,
            evidence=reranked.candidates,
        )
        if verdict.blocked:
            return {
                "output_guard_verdict": verdict,
                "final_result": self._refusal(
                    state,
                    reason=_output_refusal_reason(verdict),
                    answer=OUTPUT_GUARD_ANSWER,
                    guard_verdict=verdict,
                    warnings=(_enum_value(verdict.reason),),
                ),
            }

        citations = packed.citations
        final_result = QueryResult(
            answered=True,
            answer=synthesis.answer,
            citations=citations,
            confidence=_final_confidence(state, synthesis),
            conversation_id=state["query"].conversation_id,
            message_id=uuid4(),
            retrieval_meta=self._metadata(state),
            guard_verdict=None,
        )
        if not _answer_refs_are_valid(final_result.answer, citation_count=len(final_result.citations)):
            final_verdict = GuardVerdict.rejected(reason=GuardReason.INVALID_CITATIONS, tier=GuardTier.OUTPUT_CHECK)
            return {
                "output_guard_verdict": final_verdict,
                "final_result": self._refusal(
                    state,
                    reason=_output_refusal_reason(final_verdict),
                    answer=OUTPUT_GUARD_ANSWER,
                    guard_verdict=final_verdict,
                    warnings=(_enum_value(final_verdict.reason),),
                ),
            }
        return {
            "output_guard_verdict": verdict,
            "final_result": final_result,
        }

    async def finalize(self, state: QueryGraphState) -> QueryGraphState:
        result = state.get("final_result")
        if result is None:
            result = self._refusal(
                state,
                reason=RefusalReason.UNSUPPORTED,
                answer=UNSUPPORTED_ANSWER,
            )
        return {"final_result": replace(result, retrieval_meta=self._metadata(state))}

    def _refusal(
        self,
        state: QueryGraphState,
        *,
        reason: RefusalReason | str,
        answer: str,
        confidence: float = 0.0,
        guard_verdict: GuardVerdict | None = None,
        warnings: tuple[str, ...] = (),
    ) -> QueryResult:
        query = state["query"]
        return QueryResult(
            answered=False,
            answer=answer,
            citations=(),
            confidence=confidence,
            conversation_id=query.conversation_id,
            message_id=query.correlation_id,
            retrieval_meta=self._metadata(state, extra_warnings=warnings),
            guard_verdict=guard_verdict,
            refusal_reason=reason,
        )

    def _metadata(self, state: QueryGraphState, *, extra_warnings: tuple[str, ...] = ()) -> RetrievalMetadata:
        result = state.get("retrieval_result")
        reranked = state.get("rerank_outcome")
        packed = state.get("packed_context")
        degradation = state.get("degradation_outcome")
        attempted = result.metadata.retrievers_attempted if result is not None else ()
        used = result.metadata.retrievers_used if result is not None else ()
        chunks_considered = result.metadata.chunks_considered if result is not None else 0
        chunks_returned = len(reranked.candidates) if reranked is not None else (result.metadata.chunks_returned if result is not None else 0)
        warnings = _dedupe(
            *(
                (result.metadata.degradation_warnings if result is not None else ()),
                (state.get("parent_resolution").warnings if state.get("parent_resolution") is not None else ()),
                (reranked.warnings if reranked is not None else ()),
                (packed.warnings if packed is not None else ()),
                (degradation.warnings if degradation is not None else ()),
                extra_warnings,
            )
        )
        return RetrievalMetadata(
            route=_route(state),
            retrievers_attempted=attempted,
            retrievers_used=used,
            degradation_warnings=warnings,
            latency_ms=self._latency_ms(state),
            chunks_considered=chunks_considered,
            chunks_returned=chunks_returned,
            reranker_used=reranked.reranker_used if reranked is not None else False,
            model_id=self._components.model_id,
        )

    def _latency_ms(self, state: QueryGraphState) -> int:
        started_at = state.get("started_at")
        if started_at is None:
            return 0
        return max(0, int((self._components.clock() - float(started_at)) * 1000))


def _after_input_guard(state: QueryGraphState) -> str:
    return "reject" if state.get("final_result") is not None else "continue"


def _after_route(state: QueryGraphState) -> str:
    route = state["route_decision"].route
    if route is QueryRoute.UNSUPPORTED:
        return "unsupported"
    if route in {QueryRoute.FACTUAL, QueryRoute.COMPARISON}:
        return "hybrid"
    return "graph"


def _after_pack_context(state: QueryGraphState) -> str:
    return "refuse" if state.get("final_result") is not None else "generate"


def _route(state: QueryGraphState) -> QueryRoute:
    decision = state.get("route_decision")
    return decision.route if decision is not None else QueryRoute.UNSUPPORTED


def _dependency_state(state: QueryGraphState) -> DependencyState:
    result = state.get("retrieval_result")
    reranked = state.get("rerank_outcome")
    failure = result.failure_reason if result is not None else None
    warnings = reranked.warnings if reranked is not None else ()
    return DependencyState(
        vector_unavailable=failure == RetrievalFailureReason.VECTOR_RETRIEVAL_UNAVAILABLE,
        graph_unavailable=failure == RetrievalFailureReason.GRAPH_RETRIEVAL_UNAVAILABLE,
        embedding_unavailable=failure == RetrievalFailureReason.EMBEDDING_UNAVAILABLE,
        reranker_unavailable=RERANKER_UNAVAILABLE_WARNING in warnings,
    )


def _evidence_state(state: QueryGraphState) -> EvidenceState:
    reranked = state.get("rerank_outcome")
    retrieval = state.get("retrieval_result")
    candidates = reranked.candidates if reranked is not None else ()
    return EvidenceState(
        has_vector_evidence=any(candidate.retriever is RetrieverType.HYBRID for candidate in candidates),
        has_graph_evidence=any(candidate.retriever is RetrieverType.GRAPH for candidate in candidates),
        top_score=max((candidate.score for candidate in candidates), default=0.0),
        reranker_used=reranked.reranker_used if reranked is not None else False,
        chunks_considered=retrieval.metadata.chunks_considered if retrieval is not None else 0,
        chunks_returned=len(candidates),
    )


def _select_citations(result: SynthesisResult, citations: tuple[CitationDraft, ...]) -> tuple[CitationDraft, ...]:
    indexes = result.citation_indexes or tuple(int(match) for match in re.findall(r"\[(\d+)\]", result.answer))
    selected: list[CitationDraft] = []
    for index in indexes:
        if 1 <= index <= len(citations):
            citation = citations[index - 1]
            if citation not in selected:
                selected.append(citation)
    return tuple(selected)


def _answer_refs_are_valid(answer: str, *, citation_count: int) -> bool:
    return all(1 <= int(match) <= citation_count for match in re.findall(r"\[(\d+)\]", answer))


def _final_confidence(state: QueryGraphState, synthesis: SynthesisResult) -> float:
    degradation = state.get("degradation_outcome")
    evidence_confidence = degradation.confidence if degradation is not None else 0.0
    return min(evidence_confidence, synthesis.confidence_hint) if synthesis.confidence_hint > 0 else evidence_confidence


def _output_refusal_reason(verdict: GuardVerdict) -> RefusalReason | str:
    if verdict.reason == GuardReason.UNSAFE_EVIDENCE_ONLY:
        return RefusalReason.UNSAFE_EVIDENCE_ONLY
    return _enum_value(verdict.reason) or "output_guard_failed"


def _dedupe(*groups: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for group in groups:
        for item in group:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
    return tuple(result)


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return "" if raw is None else str(raw)
