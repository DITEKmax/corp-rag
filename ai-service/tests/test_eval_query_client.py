from __future__ import annotations

import json
from uuid import UUID

import httpx
import pytest

from eval.query_client import (
    ActualOutcome,
    EvalAccessFilter,
    ProductionQueryClient,
    QueryClientConfig,
    QueryClientError,
    access_filter_from_manifest,
)
from eval.schema import CorpusManifest, ExpectedOutcome, GoldenQuestionType, GoldenRecord


DOC_ID = "87b81f3b-357b-4599-9aea-36920cffccc9"
CHUNK_ID = "00000000-0000-0000-0000-000000000111"


def _record(*, expected_outcome: ExpectedOutcome = ExpectedOutcome.ANSWERED) -> GoldenRecord:
    return GoldenRecord(
        id="ru-factual-001",
        type=GoldenQuestionType.FACTUAL,
        question="Когда закрывается передача рейса?",
        reference_answer="Передача рейса закрывается не позднее чем за 45 минут до вылета.",
        expected_doc_ids=[DOC_ID] if expected_outcome is ExpectedOutcome.ANSWERED else [],
        expected_outcome=expected_outcome,
    )


def _config() -> QueryClientConfig:
    return QueryClientConfig(
        base_url="http://testserver",
        top_k=7,
        reranker_enabled=True,
        user_id=UUID("00000000-0000-0000-0000-00000000abcd"),
        access_filter=EvalAccessFilter(
            access_levels=("INTERNAL", "RESTRICTED"),
            departments=("OPS", "SECURITY"),
            doc_types=("POLICY", "REPORT"),
        ),
    )


def _query_response(*, answered: bool = True, guard_reason: str | None = None) -> dict:
    return {
        "answered": answered,
        "answer": "Передача рейса закрывается не позднее чем за 45 минут до вылета.",
        "citations": [
            {
                "documentId": DOC_ID,
                "documentTitle": "Регламент передачи рейса",
                "chunkId": CHUNK_ID,
                "sectionPath": "Регламент передачи рейса",
                "quote": "Передача рейса должна быть закрыта не позднее чем за 45 минут.",
                "snippet": None,
                "pageNumber": None,
                "score": 0.91,
                "accessLevel": "INTERNAL",
            }
        ]
        if answered
        else [],
        "confidence": 0.86,
        "conversationId": "00000000-0000-0000-0000-000000000222",
        "messageId": "00000000-0000-0000-0000-000000000333",
        "guardVerdict": {
            "safe": guard_reason is None,
            "reason": guard_reason,
            "tier": "TIER_0_REGEX" if guard_reason else None,
            "confidence": 0.99 if guard_reason else None,
        }
        if guard_reason
        else None,
        "retrievalMeta": {
            "route": "FACTUAL",
            "routeSource": "rules",
            "routeReason": "rules_factual",
            "retrieversAttempted": ["HYBRID"],
            "retrieversUsed": ["HYBRID"] if answered else [],
            "degradationWarnings": [],
            "latencyMs": 1234,
            "chunksConsidered": 7,
            "chunksReturned": 1 if answered else 0,
            "rerankerUsed": True,
            "modelId": "deepseek/deepseek-chat",
        },
    }


@pytest.mark.asyncio
async def test_client_posts_normal_production_query_shape_and_parses_answer() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json=_query_response(),
            headers={"x-langfuse-trace-id": "trace-123"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://testserver") as http_client:
        client = ProductionQueryClient(_config(), http_client=http_client)
        result = await client.query_golden(_record())

    payload = captured["payload"]
    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/query"
    assert payload["message"] == "Когда закрывается передача рейса?"
    assert payload["accessFilter"] == {
        "accessLevels": ["INTERNAL", "RESTRICTED"],
        "departments": ["OPS", "SECURITY"],
        "docTypes": ["POLICY", "REPORT"],
    }
    assert payload["retrievalOptions"] == {"topK": 7, "rerankerEnabled": True}
    assert "forceRoute" not in payload["retrievalOptions"]

    assert result.actual_outcome is ActualOutcome.ANSWERED
    assert result.citation_document_ids == (DOC_ID,)
    assert result.retrieved_contexts == (
        "Регламент передачи рейса / Регламент передачи рейса\n"
        "Передача рейса должна быть закрыта не позднее чем за 45 минут.",
    )
    assert result.trace_id == "trace-123"
    assert result.route == "FACTUAL"
    assert result.route_source == "rules"
    assert result.route_reason == "rules_factual"
    assert result.reranker_used is True


@pytest.mark.asyncio
async def test_client_prefers_resolved_parent_contexts_for_ragas_rows() -> None:
    class FakeParentContextResolver:
        async def resolve_contexts(self, citations):
            assert len(citations) == 1
            assert str(citations[0].chunkId) == CHUNK_ID
            return (
                "Регламент передачи рейса / Document\n"
                "Полный parent-контекст, который видел синтезатор, длиннее цитаты.",
            )

        async def aclose(self) -> None:
            raise AssertionError("injected resolver must not be closed by the client")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_query_response())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://testserver") as http_client:
        client = ProductionQueryClient(
            _config(),
            http_client=http_client,
            parent_context_resolver=FakeParentContextResolver(),
        )
        result = await client.query_golden(_record())

    assert result.retrieved_contexts == (
        "Регламент передачи рейса / Document\n"
        "Полный parent-контекст, который видел синтезатор, длиннее цитаты.",
    )


@pytest.mark.asyncio
async def test_client_preserves_guard_refusals_without_citations() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_query_response(answered=False, guard_reason="SECRET_EXFILTRATION"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://testserver") as http_client:
        client = ProductionQueryClient(_config(), http_client=http_client)
        result = await client.query_golden(_record(expected_outcome=ExpectedOutcome.REFUSED_GUARD))

    assert result.answered is False
    assert result.actual_outcome is ActualOutcome.REFUSED_GUARD
    assert result.retrieved_contexts == ()
    assert result.guard_verdict == {
        "safe": False,
        "reason": "SECRET_EXFILTRATION",
        "tier": "TIER_0_REGEX",
        "confidence": 0.99,
    }


@pytest.mark.asyncio
async def test_client_raises_problem_detail_on_non_2xx() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json={"title": "AI service unavailable", "detail": "query service is not configured", "errorCode": "AI_DOWN"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://testserver") as http_client:
        client = ProductionQueryClient(_config(), http_client=http_client)
        with pytest.raises(QueryClientError, match="HTTP 503.*AI_DOWN.*query service is not configured"):
            await client.query_golden(_record())


def test_access_filter_from_manifest_uses_manifest_values() -> None:
    manifest = CorpusManifest.model_validate(
        {
            "corpus_version": "test",
            "language": "ru",
            "documents": [
                {
                    "doc_id": "A",
                    "title": "A",
                    "path": "a.md",
                    "language": "ru",
                    "department": "OPS",
                    "doc_type": "POLICY",
                    "access_level": "INTERNAL",
                    "summary": "A",
                },
                {
                    "doc_id": "B",
                    "title": "B",
                    "path": "b.md",
                    "language": "ru",
                    "department": "SECURITY",
                    "doc_type": "REPORT",
                    "access_level": "RESTRICTED",
                    "summary": "B",
                },
            ],
        }
    )

    assert access_filter_from_manifest(manifest).to_payload() == {
        "accessLevels": ["INTERNAL", "RESTRICTED"],
        "departments": ["OPS", "SECURITY"],
        "docTypes": ["POLICY", "REPORT"],
    }
