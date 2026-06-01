from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from corp_rag_ai.config import get_settings
from corp_rag_ai.contracts.generated import ai_service_v1 as contract
from corp_rag_ai.contracts.generated import error_codes
from corp_rag_ai.domain.guard import GuardTier, GuardVerdict
from corp_rag_ai.domain.query import (
    AccessFilter,
    ConversationMessage,
    QueryInput,
    QueryResult,
    QueryRoute,
    RetrievalOptions,
)
from corp_rag_ai.domain.retrieval import RetrievalMetadata, RetrieverType
from corp_rag_ai.observability import NoopQueryObservability


QUERY_TIMEOUT_WARNING = "query_timeout"
router = APIRouter(tags=["query"])


@router.post("/v1/query", response_model=None)
async def post_query(payload: contract.QueryRequest, request: Request) -> contract.QueryResponse | JSONResponse:
    settings = _settings(request)
    try:
        query = query_input_from_contract(
            payload,
            default_top_k=settings.query_default_top_k,
            max_top_k=settings.query_max_top_k,
            default_reranker_enabled=settings.reranker_enabled,
        )
    except ValueError as exc:
        return _problem(
            status_code=400,
            error_code=error_codes.INVALID_QUERY,
            title="Invalid query",
            detail=str(exc),
            correlation_id=getattr(payload, "correlationId", None),
        )

    service = getattr(request.app.state, "query_service", None)
    if service is None:
        return _problem(
            status_code=503,
            error_code=error_codes.AI_SERVICE_UNAVAILABLE,
            title="AI service unavailable",
            detail="query service is not configured",
            correlation_id=query.correlation_id,
        )

    observability = getattr(request.app.state, "observability", NoopQueryObservability())
    async with observability.trace(name="query", metadata=_trace_request_metadata(query), tags=["query"]) as trace:
        try:
            result = await asyncio.wait_for(service.answer(query), timeout=settings.query_timeout_seconds)
        except TimeoutError:
            result = QueryResult.refused(
                query=query,
                reason=QUERY_TIMEOUT_WARNING,
                answer="Query processing timed out before an answer could be produced.",
                retrieval_meta=RetrievalMetadata(
                    route=QueryRoute.UNSUPPORTED,
                    retrievers_attempted=(),
                    retrievers_used=(),
                    degradation_warnings=(QUERY_TIMEOUT_WARNING,),
                    latency_ms=int(settings.query_timeout_seconds * 1000),
                    chunks_considered=0,
                    chunks_returned=0,
                    reranker_used=False,
                    model_id=settings.deepseek_model_id,
                ),
            )
        except Exception:
            trace.update(metadata={"error": "query_service_failed"})
            return _problem(
                status_code=503,
                error_code=error_codes.AI_SERVICE_UNAVAILABLE,
                title="AI service unavailable",
                detail="query service failed before producing a safe response",
                correlation_id=query.correlation_id,
            )
        trace.update(metadata=_trace_result_metadata(result))
        _record_query_metrics(request.app.state, result)
    return query_result_to_contract(result)


def query_input_from_contract(
    request: contract.QueryRequest,
    *,
    default_top_k: int = 10,
    max_top_k: int = 20,
    default_reranker_enabled: bool = True,
) -> QueryInput:
    if request.accessFilter is None:
        raise ValueError("query request requires accessFilter resolved by Java")

    options = request.retrievalOptions
    return QueryInput(
        user_id=request.userId,
        correlation_id=request.correlationId,
        conversation_id=request.conversationId,
        message=request.message,
        conversation_history=tuple(
            ConversationMessage(role=item.role, content=item.content) for item in (request.conversationHistory or [])
        ),
        access_filter=AccessFilter(
            access_levels=tuple(request.accessFilter.accessLevels),
            departments=tuple(request.accessFilter.departments),
            doc_types=tuple(request.accessFilter.docTypes),
        ),
        retrieval_options=RetrievalOptions.from_values(
            top_k=options.topK if options is not None else None,
            reranker_enabled=options.rerankerEnabled if options is not None else None,
            force_route=options.forceRoute if options is not None else None,
            default_top_k=default_top_k,
            max_top_k=max_top_k,
            default_reranker_enabled=default_reranker_enabled,
        ),
    )


def query_result_to_contract(result: QueryResult) -> contract.QueryResponse:
    return contract.QueryResponse(
        answered=result.answered,
        answer=result.answer,
        citations=[
            contract.Citation(
                documentId=citation.document_id,
                documentTitle=citation.document_title,
                chunkId=citation.chunk_id,
                sectionPath=citation.section_path_label,
                quote=citation.quote,
                snippet=citation.snippet,
                pageNumber=citation.page_number,
                score=citation.score,
                accessLevel=contract.AccessLevel(citation.access_level),
            )
            for citation in result.citations
        ],
        confidence=result.confidence,
        conversationId=result.conversation_id,
        messageId=result.message_id,
        guardVerdict=_guard_verdict_to_contract(result.guard_verdict),
        retrievalMeta=contract.RetrievalMeta(
            route=contract.QueryRoute(result.retrieval_meta.route),
            retrieversAttempted=[
                contract.RetrieverType(_enum_value(retriever)) for retriever in result.retrieval_meta.retrievers_attempted
            ],
            retrieversUsed=[
                contract.RetrieverType(_enum_value(retriever)) for retriever in result.retrieval_meta.retrievers_used
            ],
            degradationWarnings=list(result.retrieval_meta.degradation_warnings),
            latencyMs=result.retrieval_meta.latency_ms,
            chunksConsidered=result.retrieval_meta.chunks_considered,
            chunksReturned=result.retrieval_meta.chunks_returned,
            rerankerUsed=result.retrieval_meta.reranker_used,
            modelId=result.retrieval_meta.model_id,
        ),
    )


def _guard_verdict_to_contract(verdict: GuardVerdict | None) -> contract.GuardVerdict | None:
    if verdict is None:
        return None
    tier = None if verdict.tier is None else contract.GuardTier(_enum_value(verdict.tier))
    reason = None if verdict.reason is None else _enum_value(verdict.reason)
    return contract.GuardVerdict(
        safe=verdict.safe,
        reason=reason,
        tier=tier,
        confidence=verdict.confidence,
    )


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _settings(request: Request):
    return getattr(request.app.state, "settings", get_settings())


def _record_query_metrics(state, result: QueryResult) -> None:
    metrics = getattr(state, "query_metrics", None)
    if metrics is not None:
        metrics.record(result)


def _trace_request_metadata(query: QueryInput) -> dict[str, object]:
    return {
        "correlation_id": str(query.correlation_id),
        "conversation_id": str(query.conversation_id),
        "user_id": str(query.user_id),
        "requested_top_k": query.retrieval_options.top_k,
        "reranker_requested": query.retrieval_options.reranker_enabled,
        "forced_route": _enum_value(query.retrieval_options.force_route) if query.retrieval_options.force_route else None,
    }


def _trace_result_metadata(result: QueryResult) -> dict[str, object]:
    meta = result.retrieval_meta
    return {
        "answered": result.answered,
        "refusal_reason": _enum_value(result.refusal_reason) if result.refusal_reason is not None else None,
        "confidence": result.confidence,
        "route": _enum_value(meta.route),
        "retrievers_attempted": [_enum_value(retriever) for retriever in meta.retrievers_attempted],
        "retrievers_used": [_enum_value(retriever) for retriever in meta.retrievers_used],
        "degradation_warnings": list(meta.degradation_warnings or ()),
        "latency_ms": meta.latency_ms,
        "chunks_considered": meta.chunks_considered,
        "chunks_returned": meta.chunks_returned,
        "reranker_used": meta.reranker_used,
        "model_id": meta.model_id,
        "guard_blocked": result.guard_verdict.blocked if result.guard_verdict is not None else False,
    }


def _problem(
    *,
    status_code: int,
    error_code: str,
    title: str,
    detail: str,
    correlation_id,
) -> JSONResponse:
    problem = contract.ProblemDetail(
        type=f"https://corp-rag.local/problems/{error_code.lower().replace('_', '-')}",
        title=title,
        status=status_code,
        detail=detail,
        errorCode=error_code,
        correlationId=correlation_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(mode="json", exclude_none=True),
        media_type="application/problem+json",
    )
