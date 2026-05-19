from __future__ import annotations

from uuid import UUID

import pytest

from corp_rag_ai.domain.query import AccessFilter, QueryInput, QueryRoute, RetrievalOptions, RouteDecision, RouteSource
from corp_rag_ai.pipeline.routing.query_router import (
    DEFAULT_DEEPSEEK_MODEL,
    DEFAULT_DEPENDENCY_ATTEMPTS,
    DeepSeekQueryRouteClassifier,
    QueryRouter,
    _structured_response_format,
)


USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CORRELATION_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
CONVERSATION_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected_route"),
    [
        ("What is the vacation policy?", QueryRoute.FACTUAL),
        ("How many policies mention payroll?", QueryRoute.AGGREGATION),
        ("Which approvals are needed before onboarding a contractor?", QueryRoute.MULTI_HOP),
        ("Compare vacation and sick leave policies.", QueryRoute.COMPARISON),
        ("Who won the football game?", QueryRoute.UNSUPPORTED),
    ],
)
async def test_rules_based_routes_skip_classifier(message: str, expected_route: QueryRoute) -> None:
    classifier = _FakeClassifier(RouteDecision(route=QueryRoute.FACTUAL, confidence=0.9, source=RouteSource.LLM))
    decision = await QueryRouter(classifier=classifier).route(_query(message))

    assert decision.route is expected_route
    assert decision.confidence == 1.0
    assert decision.source is RouteSource.RULES
    assert classifier.calls == 0


@pytest.mark.asyncio
async def test_force_route_bypasses_rules_and_classifier() -> None:
    classifier = _FakeClassifier(RouteDecision(route=QueryRoute.FACTUAL, confidence=0.9, source=RouteSource.LLM))
    query = _query("What is the vacation policy?", force_route=QueryRoute.COMPARISON)

    decision = await QueryRouter(classifier=classifier).route(query)

    assert decision.route is QueryRoute.COMPARISON
    assert decision.source is RouteSource.FORCED
    assert decision.confidence == 1.0
    assert classifier.calls == 0


@pytest.mark.asyncio
async def test_ambiguous_corporate_question_uses_llm_classifier() -> None:
    classifier = _FakeClassifier(RouteDecision(route=QueryRoute.MULTI_HOP, confidence=0.82, source=RouteSource.LLM))

    decision = await QueryRouter(classifier=classifier).route(_query("Tell me about onboarding and related approvals."))

    assert decision.route is QueryRoute.MULTI_HOP
    assert decision.confidence == 0.82
    assert decision.source is RouteSource.LLM
    assert classifier.calls == 1


@pytest.mark.asyncio
async def test_low_confidence_classifier_result_short_circuits_as_unsupported() -> None:
    classifier = _FakeClassifier(RouteDecision(route=QueryRoute.FACTUAL, confidence=0.44, source=RouteSource.LLM))

    decision = await QueryRouter(classifier=classifier, confidence_threshold=0.65).route(
        _query("Tell me about onboarding and related approvals.")
    )

    assert decision.route is QueryRoute.UNSUPPORTED
    assert decision.source is RouteSource.LLM
    assert decision.reason == "low_confidence"
    assert decision.allows_retrieval is False
    assert classifier.calls == 1


@pytest.mark.asyncio
async def test_classifier_dependency_failure_short_circuits_without_retrieval() -> None:
    classifier = _FailingClassifier()

    decision = await QueryRouter(classifier=classifier).route(_query("Tell me about onboarding and related approvals."))

    assert decision.route is QueryRoute.UNSUPPORTED
    assert decision.source is RouteSource.FALLBACK
    assert decision.reason == "classifier_dependency_unavailable"
    assert decision.allows_retrieval is False


@pytest.mark.asyncio
async def test_fixture_suite_keeps_llm_fallback_rate_under_thirty_percent() -> None:
    classifier = _FakeClassifier(RouteDecision(route=QueryRoute.FACTUAL, confidence=0.9, source=RouteSource.LLM))
    router = QueryRouter(classifier=classifier)
    messages = [
        "What is the vacation policy?",
        "How do employees request remote work?",
        "How many policies mention payroll?",
        "Count HR regulations updated in 2026.",
        "Compare vacation and sick leave policies.",
        "What is the difference between internal and confidential access?",
        "Which approvals are needed before onboarding a contractor?",
        "What dependencies connect payroll approval to finance reporting?",
        "Who won the football game?",
        "Tell me about onboarding and related approvals.",
    ]

    decisions = [await router.route(_query(message)) for message in messages]
    fallback_rate = classifier.calls / len(messages)

    assert fallback_rate <= 0.30
    assert classifier.calls == 1
    assert decisions[-1].source is RouteSource.LLM


@pytest.mark.asyncio
async def test_deepseek_classifier_uses_strict_json_schema() -> None:
    client = _FakeClient([_FakeResponse('{"query_type": "COMPARISON", "confidence": 0.74}')])
    classifier = DeepSeekQueryRouteClassifier(client=client, sleep=_no_sleep)

    decision = await classifier.classify(_query("Tell me about onboarding and related approvals."))

    assert decision.route is QueryRoute.COMPARISON
    assert decision.confidence == 0.74
    call = client.chat.completions.calls[0]
    assert call["model"] == DEFAULT_DEEPSEEK_MODEL
    assert call["messages"][0]["role"] == "user"
    assert "Question:" in call["messages"][0]["content"]
    assert call["response_format"]["type"] == "json_schema"
    assert call["response_format"]["json_schema"]["strict"] is True
    assert call["extra_body"] == {"plugins": [{"id": "response-healing"}]}
    assert call["temperature"] == 0.0
    assert call["max_tokens"] == 120


@pytest.mark.asyncio
async def test_deepseek_classifier_retries_malformed_output_once() -> None:
    client = _FakeClient([
        _FakeResponse("not json"),
        _FakeResponse('{"query_type": "FACTUAL", "confidence": 0.83}'),
    ])
    classifier = DeepSeekQueryRouteClassifier(client=client, sleep=_no_sleep)

    decision = await classifier.classify(_query("Tell me about onboarding and related approvals."))

    assert decision.route is QueryRoute.FACTUAL
    assert decision.confidence == 0.83
    assert len(client.chat.completions.calls) == DEFAULT_DEPENDENCY_ATTEMPTS


@pytest.mark.asyncio
async def test_malformed_classifier_output_degrades_to_unsupported_without_retrieval() -> None:
    client = _FakeClient([_FakeResponse("not json"), _FakeResponse("still not json")])
    classifier = DeepSeekQueryRouteClassifier(client=client, sleep=_no_sleep)

    decision = await QueryRouter(classifier=classifier).route(_query("Tell me about onboarding and related approvals."))

    assert decision.route is QueryRoute.UNSUPPORTED
    assert decision.reason == "classifier_dependency_unavailable"
    assert decision.allows_retrieval is False
    assert len(client.chat.completions.calls) == DEFAULT_DEPENDENCY_ATTEMPTS


def test_route_classifier_schema_strips_openrouter_unsupported_keys() -> None:
    schema = _structured_response_format()["json_schema"]["schema"]

    assert "query_type" in schema["properties"]
    assert not _contains_schema_key(schema, "additionalProperties")
    assert not _contains_schema_key(schema, "additional_properties")


class _FakeClassifier:
    def __init__(self, decision: RouteDecision) -> None:
        self.decision = decision
        self.calls = 0

    async def classify(self, _query: QueryInput) -> RouteDecision:
        self.calls += 1
        return self.decision


class _FailingClassifier:
    async def classify(self, _query: QueryInput) -> RouteDecision:
        raise RuntimeError("dependency unavailable")


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.choices = [_FakeChoice(text)]


class _FakeCompletions:
    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeChat:
    def __init__(self, outcomes) -> None:
        self.completions = _FakeCompletions(outcomes)


class _FakeClient:
    def __init__(self, outcomes) -> None:
        self.chat = _FakeChat(outcomes)


async def _no_sleep(_seconds: float) -> None:
    return None


def _query(message: str, *, force_route: QueryRoute | None = None) -> QueryInput:
    return QueryInput(
        user_id=USER_ID,
        correlation_id=CORRELATION_ID,
        conversation_id=CONVERSATION_ID,
        message=message,
        access_filter=AccessFilter(access_levels=("PUBLIC", "INTERNAL"), departments=("HR",), doc_types=("POLICY",)),
        retrieval_options=RetrievalOptions.from_values(force_route=force_route),
    )


def _contains_schema_key(value, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_schema_key(child, key) for child in value.values())
    if isinstance(value, list):
        return any(_contains_schema_key(child, key) for child in value)
    return False
