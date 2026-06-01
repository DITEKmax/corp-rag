from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from corp_rag_ai.adapters.rest.query import query_input_from_contract, query_result_to_contract
from corp_rag_ai.contracts.generated import ai_service_v1 as contract
from corp_rag_ai.domain.guard import GuardReason, GuardTier, GuardVerdict
from corp_rag_ai.domain.query import (
    AccessFilter,
    QueryInput,
    QueryResult,
    QueryRoute,
    RefusalReason,
    RetrievalOptions,
)
from corp_rag_ai.domain.retrieval import CitationDraft, RetrievalMetadata, RetrieverType


USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CORRELATION_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
CONVERSATION_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
MESSAGE_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
DOCUMENT_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
CHUNK_ID = UUID("11111111-1111-4111-8111-111111111042")


def test_contract_request_maps_to_internal_query_input_with_defaults() -> None:
    request = _contract_request(retrieval_options=None)

    query = query_input_from_contract(request)

    assert isinstance(query, QueryInput)
    assert query.message == "How many vacation days do employees get?"
    assert query.access_filter.access_levels == ("PUBLIC", "INTERNAL")
    assert query.access_filter.doc_types == ("POLICY",)
    assert query.access_filter.department_wildcard is True
    assert query.retrieval_options.top_k == 10
    assert query.retrieval_options.reranker_enabled is True
    assert query.retrieval_options.force_route is None


def test_retrieval_options_clamp_top_k_to_contract_limits() -> None:
    high = RetrievalOptions.from_values(top_k=50, max_top_k=20)
    low = RetrievalOptions.from_values(top_k=0, max_top_k=20)

    assert high.top_k == 20
    assert low.top_k == 1


def test_contract_request_options_map_force_route_and_configurable_limits() -> None:
    request = _contract_request(
        retrieval_options=contract.RetrievalOptions(
            topK=50,
            rerankerEnabled=False,
            forceRoute=contract.QueryRoute.COMPARISON,
        )
    )

    query = query_input_from_contract(request, default_top_k=8, max_top_k=12)

    assert query.retrieval_options.top_k == 12
    assert query.retrieval_options.reranker_enabled is False
    assert query.retrieval_options.force_route is QueryRoute.COMPARISON


def test_access_filter_requires_java_resolved_rbac_context() -> None:
    request = contract.QueryRequest.model_construct(
        userId=USER_ID,
        correlationId=CORRELATION_ID,
        conversationId=CONVERSATION_ID,
        message="What is the leave policy?",
        conversationHistory=[],
        accessFilter=None,
        retrievalOptions=None,
    )

    with pytest.raises(ValueError, match="accessFilter"):
        query_input_from_contract(request)


def test_query_input_enforces_contract_message_length() -> None:
    with pytest.raises(ValueError, match="maximum length"):
        QueryInput(
            user_id=USER_ID,
            correlation_id=CORRELATION_ID,
            conversation_id=CONVERSATION_ID,
            message="x" * 2001,
            access_filter=AccessFilter(access_levels=("PUBLIC",), departments=(), doc_types=("POLICY",)),
        )


def test_domain_result_maps_to_contract_query_response() -> None:
    result = QueryResult(
        answered=True,
        answer="Employees receive vacation according to the HR policy [1].",
        citations=(
            CitationDraft(
                document_id=DOCUMENT_ID,
                document_title="Vacation Policy",
                chunk_id=CHUNK_ID,
                section_path=("HR", "Leave"),
                quote="Employees receive annual vacation according to tenure.",
                snippet="annual vacation according to tenure",
                page_number=4,
                score=0.91,
                access_level="INTERNAL",
            ),
        ),
        confidence=0.84,
        conversation_id=CONVERSATION_ID,
        message_id=MESSAGE_ID,
        retrieval_meta=RetrievalMetadata(
            route=QueryRoute.FACTUAL,
            retrievers_attempted=(RetrieverType.HYBRID,),
            retrievers_used=(RetrieverType.HYBRID,),
            latency_ms=123,
            chunks_considered=8,
            chunks_returned=1,
            reranker_used=True,
            model_id="deepseek/deepseek-v4-flash:free",
        ),
    )

    response = query_result_to_contract(result)

    assert response.answered is True
    assert response.citations[0].chunkId == CHUNK_ID
    assert response.citations[0].sectionPath == "HR > Leave"
    assert response.citations[0].accessLevel is contract.AccessLevel.INTERNAL
    assert response.retrievalMeta.route is contract.QueryRoute.FACTUAL
    assert response.retrievalMeta.retrieversAttempted == [contract.RetrieverType.HYBRID]


def test_domain_result_maps_empty_citation_section_path_to_display_label() -> None:
    result = QueryResult(
        answered=True,
        answer="Use the policy [1].",
        citations=(
            CitationDraft(
                document_id=DOCUMENT_ID,
                document_title="Vacation Policy",
                chunk_id=CHUNK_ID,
                section_path=(),
                quote="Use the policy.",
                score=0.9,
                access_level="INTERNAL",
            ),
        ),
        confidence=0.8,
        conversation_id=CONVERSATION_ID,
        message_id=MESSAGE_ID,
        retrieval_meta=RetrievalMetadata(route=QueryRoute.FACTUAL, retrievers_used=(RetrieverType.HYBRID,)),
    )

    response = query_result_to_contract(result)

    assert response.citations[0].sectionPath == "Document"


def test_refusal_result_maps_guard_verdict_and_empty_citations() -> None:
    query = query_input_from_contract(_contract_request(retrieval_options=None))
    result = QueryResult.refused(
        query=query,
        reason=RefusalReason.PROMPT_INJECTION,
        answer="I cannot process that request.",
        retrieval_meta=RetrievalMetadata(
            route=QueryRoute.UNSUPPORTED,
            latency_ms=4,
            model_id="deepseek/deepseek-v4-flash:free",
        ),
        guard_verdict=GuardVerdict.rejected(
            reason=GuardReason.PROMPT_INJECTION,
            tier=GuardTier.TIER_0_REGEX,
        ),
        message_id=MESSAGE_ID,
    )

    response = query_result_to_contract(result)

    assert response.answered is False
    assert response.citations == []
    assert response.confidence == 0.0
    assert response.guardVerdict is not None
    assert response.guardVerdict.safe is False
    assert response.guardVerdict.reason == "prompt_injection"
    assert response.retrievalMeta.route is contract.QueryRoute.UNSUPPORTED


def test_domain_and_pipeline_modules_do_not_import_generated_contracts() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "corp_rag_ai"
    checked = [
        root / "domain" / "query.py",
        root / "domain" / "guard.py",
        root / "domain" / "retrieval.py",
    ]

    for path in checked:
        assert "contracts.generated" not in path.read_text(encoding="utf-8")


def _contract_request(retrieval_options: contract.RetrievalOptions | None) -> contract.QueryRequest:
    return contract.QueryRequest(
        userId=USER_ID,
        correlationId=CORRELATION_ID,
        conversationId=CONVERSATION_ID,
        message="How many vacation days do employees get?",
        conversationHistory=[
            contract.ConversationMessage(role=contract.ConversationRole.USER, content="Tell me about vacation."),
            contract.ConversationMessage(role=contract.ConversationRole.ASSISTANT, content="Which policy should I use?"),
        ],
        accessFilter=contract.AccessFilter(
            accessLevels=[contract.AccessLevel.PUBLIC, contract.AccessLevel.INTERNAL],
            departments=[],
            docTypes=[contract.DocType.POLICY],
        ),
        retrievalOptions=retrieval_options,
    )
