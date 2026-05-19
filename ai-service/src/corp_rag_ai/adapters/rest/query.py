from __future__ import annotations

from corp_rag_ai.contracts.generated import ai_service_v1 as contract
from corp_rag_ai.domain.guard import GuardTier, GuardVerdict
from corp_rag_ai.domain.query import (
    AccessFilter,
    ConversationMessage,
    QueryInput,
    QueryResult,
    QueryRoute,
    RetrievalOptions,
)
from corp_rag_ai.domain.retrieval import RetrieverType


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
