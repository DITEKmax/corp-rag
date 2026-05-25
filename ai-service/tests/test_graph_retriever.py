from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest

from corp_rag_ai.domain.query import AccessFilter, QueryInput, QueryRoute
from corp_rag_ai.domain.retrieval import RetrievalFailureReason, RetrieverType
from corp_rag_ai.pipeline.retrieval.graph import GraphRetriever
from corp_rag_ai.pipeline.retrieval.graph_query_helpers import graph_access_params


USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CORRELATION_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
CONVERSATION_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
DOCUMENT_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
CHUNK_ID = UUID("11111111-1111-4111-8111-111111111042")
PARENT_CHUNK_ID = UUID("22222222-2222-4222-8222-222222222017")


async def test_aggregation_query_filters_through_accessible_document_evidence() -> None:
    session = _FakeGraphSession([_record(entityName="Vacation Policy")])
    retriever = GraphRetriever(_FakeDriver(session))

    result = await retriever.retrieve(_query("Count HR policies."), route=QueryRoute.AGGREGATION)

    cypher, params = session.runs[0]
    assert "MATCH (e:Entity)-[mention:MENTIONED_IN]->(d:Document)" in cypher
    assert "d.accessLevel IN $accessLevels" in cypher
    assert "d.docType IN $docTypes" in cypher
    assert "($departmentWildcard = true OR d.department IN $departments)" in cypher
    assert params["accessLevels"] == ["PUBLIC", "INTERNAL"]
    assert params["docTypes"] == ["POLICY"]
    assert params["departments"] == ["HR"]
    assert params["departmentWildcard"] is False

    assert result.failed is False
    assert result.metadata.retrievers_attempted == (RetrieverType.GRAPH,)
    assert result.metadata.retrievers_used == (RetrieverType.GRAPH,)
    assert result.metadata.chunks_considered == 1
    candidate = result.candidates[0]
    assert candidate.chunk_id == CHUNK_ID
    assert candidate.parent_chunk_id == PARENT_CHUNK_ID
    assert candidate.document_id == DOCUMENT_ID
    assert candidate.retriever is RetrieverType.GRAPH
    assert candidate.metadata["graphPath"] == "entity:Vacation Policy"
    assert candidate.metadata["candidateGroup"] == "Vacation Policy"


async def test_graph_candidate_keeps_graph_path_internal_and_prefers_document_text_when_returned() -> None:
    session = _FakeGraphSession(
        [
            _record(
                entityName="CloudSec Inc",
                graphPath="entity:CloudSec Inc",
                documentText="CloudSec Inc is approved for endpoint monitoring.",
            )
        ]
    )
    retriever = GraphRetriever(_FakeDriver(session))

    result = await retriever.retrieve(_query("How many vendors are approved?"), route=QueryRoute.AGGREGATION)

    candidate = result.candidates[0]
    assert candidate.content == "CloudSec Inc is approved for endpoint monitoring."
    assert candidate.snippet == "CloudSec Inc is approved for endpoint monitoring."
    assert candidate.metadata["graphPath"] == "entity:CloudSec Inc"
    assert not candidate.snippet.startswith("entity:")


async def test_empty_departments_are_wildcard_only_for_department() -> None:
    access_filter = AccessFilter(access_levels=("PUBLIC",), departments=(), doc_types=("REPORT",))
    params = graph_access_params(access_filter)

    assert params["accessLevels"] == ["PUBLIC"]
    assert params["docTypes"] == ["REPORT"]
    assert params["departments"] == []
    assert params["departmentWildcard"] is True


async def test_multi_hop_query_is_capped_and_returns_document_backed_relation_evidence() -> None:
    session = _FakeGraphSession([_record(relationType="REQUIRES", graphPath="Employee Role REQUIRES Access Policy")])
    retriever = GraphRetriever(_FakeDriver(session), max_hops=3)

    result = await retriever.retrieve(_query("Which approvals are needed within 3 hops?"), route=QueryRoute.MULTI_HOP)

    cypher, _params = session.runs[0]
    assert "*1..3" in cypher
    assert "(relation:RelationMention)-[evidence:EVIDENCE]->(d:Document)" in cypher
    assert "d.accessLevel IN $accessLevels" in cypher
    assert result.failed is False
    assert result.candidates[0].metadata["relationType"] == "REQUIRES"
    assert result.candidates[0].metadata["graphPath"] == "Employee Role REQUIRES Access Policy"


async def test_deeper_multi_hop_request_short_circuits_without_neo4j_call() -> None:
    session = _FakeGraphSession([_record()])
    retriever = GraphRetriever(_FakeDriver(session), max_hops=3)

    result = await retriever.retrieve(_query("Find the approval chain across 4 hops."), route=QueryRoute.MULTI_HOP)

    assert session.runs == []
    assert result.failed is True
    assert result.failure_reason is RetrievalFailureReason.UNSUPPORTED_GRAPH_DEPTH
    assert result.metadata.retrievers_attempted == ()
    assert result.metadata.degradation_warnings == ("unsupported_graph_depth",)


async def test_graph_dependency_failure_is_explicit_for_graph_first_routes() -> None:
    retriever = GraphRetriever(_FakeDriver(_FailingGraphSession()))

    result = await retriever.retrieve(_query("Count HR policies."), route=QueryRoute.AGGREGATION)

    assert result.failed is True
    assert result.failure_reason is RetrievalFailureReason.GRAPH_RETRIEVAL_UNAVAILABLE
    assert result.metadata.retrievers_attempted == (RetrieverType.GRAPH,)
    assert result.metadata.retrievers_used == ()
    assert result.metadata.degradation_warnings == ("graph_retrieval_unavailable",)


async def test_factual_route_does_not_depend_on_graph() -> None:
    session = _FailingGraphSession()
    retriever = GraphRetriever(_FakeDriver(session))

    result = await retriever.retrieve(_query("What is the vacation policy?"), route=QueryRoute.FACTUAL)

    assert result.failed is False
    assert result.candidates == ()
    assert result.metadata.retrievers_attempted == ()
    assert session.runs == []


async def test_comparison_route_passes_entity_names_for_disambiguation() -> None:
    session = _FakeGraphSession([_record(entityName="Alpha Policy", graphPath="comparison:Alpha Policy")])
    retriever = GraphRetriever(_FakeDriver(session))

    result = await retriever.retrieve(_query("Compare Alpha Policy and Beta Policy."), route=QueryRoute.COMPARISON)

    cypher, params = session.runs[0]
    assert "any(name IN $entityNames WHERE e.normalizedName CONTAINS name)" in cypher
    assert params["entityNames"] == ["alpha", "beta"]
    assert result.failed is False
    assert result.candidates[0].metadata["candidateGroup"] == "Alpha Policy"


async def test_comparison_empty_accessible_graph_evidence_is_legitimate_no_answer_outcome() -> None:
    session = _FakeGraphSession([])
    retriever = GraphRetriever(_FakeDriver(session))

    result = await retriever.retrieve(_query("Compare ambiguous access policies."), route=QueryRoute.COMPARISON)

    assert result.failed is False
    assert result.candidates == ()
    assert result.metadata.retrievers_attempted == (RetrieverType.GRAPH,)
    assert result.metadata.retrievers_used == ()
    assert result.metadata.chunks_considered == 0


def test_graph_queries_do_not_return_entity_only_evidence() -> None:
    session = _FakeGraphSession([])
    retriever = GraphRetriever(_FakeDriver(session))

    cypher, params = retriever._query_and_params(_query("Count HR policies."), QueryRoute.AGGREGATION)

    assert "->(d:Document)" in cypher
    assert "d.accessLevel IN $accessLevels" in cypher
    assert params["accessLevels"] == ["PUBLIC", "INTERNAL"]


class _FakeGraphSession:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self.records = records
        self.runs: list[tuple[str, dict[str, object]]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def run(self, cypher: str, **params):
        self.runs.append((cypher, params))
        return _FakeResult(self.records)


class _FailingGraphSession:
    def __init__(self) -> None:
        self.runs: list[tuple[str, dict[str, object]]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None

    async def run(self, cypher: str, **params):
        self.runs.append((cypher, params))
        raise RuntimeError("neo4j unavailable")


class _FakeDriver:
    def __init__(self, session) -> None:
        self.session_instance = session

    def session(self, **_kwargs):
        return self.session_instance


@dataclass(frozen=True, slots=True)
class _FakeResult:
    records: list[dict[str, object]]

    async def data(self):
        return self.records


def _query(message: str) -> QueryInput:
    return QueryInput(
        user_id=USER_ID,
        correlation_id=CORRELATION_ID,
        conversation_id=CONVERSATION_ID,
        message=message,
        access_filter=AccessFilter(access_levels=("PUBLIC", "INTERNAL"), departments=("HR",), doc_types=("POLICY",)),
    )


def _record(
    *,
    entityName: str = "Vacation Policy",
    relationType: str | None = None,
    graphPath: str = "entity:Vacation Policy",
    documentText: str | None = None,
) -> dict[str, object]:
    return {
        "chunkId": str(CHUNK_ID),
        "parentChunkId": str(PARENT_CHUNK_ID),
        "sectionPath": ["HR", "Leave"],
        "documentId": str(DOCUMENT_ID),
        "documentTitle": "Vacation Policy",
        "accessLevel": "INTERNAL",
        "entityName": entityName,
        "relationType": relationType,
        "graphPath": graphPath,
        "documentText": documentText,
        "score": 0.75,
    }
