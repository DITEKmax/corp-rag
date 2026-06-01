from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field

from corp_rag_ai.domain.query import QueryInput, QueryRoute, RouteDecision, RouteSource

QUERY_ROUTING_PROMPT_VERSION = "query_routing_v1"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_DEEPSEEK_MODEL = "deepseek/deepseek-v4-flash:free"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_OUTPUT_TOKENS = 120
DEFAULT_DEPENDENCY_ATTEMPTS = 2

_FACTUAL_PATTERNS = (
    re.compile(r"\b(what|who|when|where)\s+(is|are|was|were|does|do)\b", re.I),
    re.compile(r"\bhow\s+(do|does|can|should)\b", re.I),
    re.compile(r"\b(policy|procedure|regulation|manual|guide|deadline|vacation|payroll|benefits)\b", re.I),
    re.compile(r"\b(что|кто|когда|где)\s+(?:такое|является|указан[оы]?|описан[оы]?)\b", re.I),
    re.compile(r"\b(?:как|каким образом)\s+(?:нужно|следует|можно|должн[аоы]?)\b", re.I),
    re.compile(r"\b(политик[аиу]?|регламент|процедур[аы]|инструкци[яи]|срок|правил[оа])\b", re.I),
)

_AGGREGATION_PATTERNS = (
    re.compile(r"\b(how\s+many|count|number\s+of|total|aggregate|sum|average)\b", re.I),
    re.compile(
        r"\b(?:сколько|какое\s+число|общее\s+число)\s+"
        r"(?:компан(?:ий|ии)|поставщик(?:ов|и)|документ(?:ов|ы)|политик|регламент(?:ов|ы)|"
        r"рейс(?:ов|ы)|инцидент(?:ов|ы)|запис(?:ей|и)|требован(?:ий|ия))\b",
        re.I,
    ),
    re.compile(
        r"\b(?:какие|какая|какой|перечисли|назови)\s+"
        r"(?:компан(?:ии|ия)|поставщик(?:и|ов)|документ(?:ы|ов)|политик(?:и|а)|регламент(?:ы|ов)|"
        r"рейс(?:ы|ов)|инцидент(?:ы|ов)|требован(?:ия|ий))\b"
        r".*\b(?:перечислен[аыо]?|указан[аыо]?|упомянут[аыо]?|есть|вход[яи]т|содерж[аи]тся)\b",
        re.I,
    ),
)

_FACTUAL_NUMERIC_LOOKUP_PATTERNS = (
    re.compile(
        r"\b(?:in\s+)?how\s+many\s+(?:business\s+)?(?:days?|hours?|weeks?|months?)\s+"
        r"(?:must|should|do|does|can|may|are|is|before|after)\b",
        re.I,
    ),
)

_MULTI_HOP_PATTERNS = (
    re.compile(r"\b(relationship\s+between|depends\s+on|connected\s+to|impact\s+of)\b", re.I),
    re.compile(r"\bwhich\s+.+\s+(caused|requires|require|needed\s+before|are\s+needed\s+before)\b", re.I),
    re.compile(r"\bwhat\s+.+\s+(approvals|dependencies).+\s+(before|after|connect)\b", re.I),
    re.compile(r"\b(?:как|чем)\s+связан[аыо]?\s+.+\s+(?:и|с|со)\s+.+", re.I),
    re.compile(r"\bсвяз[а-яё]*\s+.+\s+(?:с|со)\s+.+", re.I),
    re.compile(r"\bпочему\s+.+\b(?:важн[аоы]?|влияет|приводит|требует|созда[её]т)\b", re.I),
    re.compile(r"\b(?:что|какие?\s+действия)\s+происходит\s+после\s+.+\b(?:если|когда|и)\b", re.I),
    re.compile(r"\b(?:после|до)\s+.+\b(?:если|когда)\s+.+", re.I),
    re.compile(r"\b(?:конфликт|противоречи[ея]|зависимост[ьи])\s+.+\b(?:между|с|со)\b", re.I),
)

_COMPARISON_PATTERNS = (
    re.compile(r"\b(compare|comparison|versus|vs\.?)\b", re.I),
    re.compile(r"\bdifference\s+between\b", re.I),
    re.compile(r"\b(?:сравни|сравнение|чем\s+отлича[ею]тся|разница\s+между|отличи[ея]\s+между)\b", re.I),
)

_UNSUPPORTED_PATTERNS = (
    re.compile(r"\b(weather|sports|football|movie|recipe|joke)\b", re.I),
    re.compile(r"\bwhat\s+is\s+\d+\s*[+\-*/]\s*\d+\b", re.I),
    re.compile(r"\b(погод[ауы]|спорт|футбол|фильм|рецепт|шутк[аиу])\b", re.I),
    re.compile(r"\bсколько\s+будет\s+\d+\s*[+\-*/]\s*\d+\b", re.I),
)


class RouteClassifierResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_type: QueryRoute
    confidence: float = Field(ge=0.0, le=1.0)


class RouteClassifierClient(Protocol):
    async def classify(self, query: QueryInput) -> RouteDecision:
        ...


SleepFn = Callable[[float], Awaitable[None]]


class QueryRouter:
    def __init__(
        self,
        *,
        classifier: RouteClassifierClient | None = None,
        confidence_threshold: float = 0.65,
    ) -> None:
        self._classifier = classifier
        self._confidence_threshold = confidence_threshold

    async def route(self, query: QueryInput) -> RouteDecision:
        if query.retrieval_options.force_route is not None:
            route = query.retrieval_options.force_route
            return RouteDecision(route=route, confidence=1.0, source=RouteSource.FORCED, reason="forced_route")

        rule_decision = _route_by_rules(query.message)
        if rule_decision is not None:
            return rule_decision

        if self._classifier is None:
            return RouteDecision.unsupported(
                source=RouteSource.FALLBACK,
                reason="classifier_unavailable",
            )

        try:
            decision = await self._classifier.classify(query)
        except Exception:
            return RouteDecision.unsupported(
                source=RouteSource.FALLBACK,
                reason="classifier_dependency_unavailable",
            )

        if decision.confidence < self._confidence_threshold:
            return RouteDecision.unsupported(
                source=RouteSource.LLM,
                reason="low_confidence",
                confidence=decision.confidence,
            )
        return decision


class DeepSeekQueryRouteClassifier:
    def __init__(
        self,
        *,
        client: Any | None = None,
        api_key: str | None = None,
        base_url: str = DEFAULT_OPENROUTER_BASE_URL,
        model: str = DEFAULT_DEEPSEEK_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        max_dependency_attempts: int = DEFAULT_DEPENDENCY_ATTEMPTS,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._max_dependency_attempts = max_dependency_attempts
        self._sleep = sleep

    async def classify(self, query: QueryInput) -> RouteDecision:
        contents = _render_prompt(query)
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._create_completion(contents)
                parsed = _parse_response(response)
                return RouteDecision(
                    route=parsed.query_type,
                    confidence=parsed.confidence,
                    source=RouteSource.LLM,
                    reason=QUERY_ROUTING_PROMPT_VERSION,
                )
            except Exception:
                if attempt >= self._max_dependency_attempts:
                    raise
                await self._sleep(_backoff_seconds(attempt))

    async def _create_completion(self, contents: str) -> Any:
        client = self._get_client()
        return await client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": contents}],
            response_format=_structured_response_format(),
            extra_body={"plugins": [{"id": "response-healing"}]},
            temperature=self._temperature,
            max_tokens=self._max_output_tokens,
        )

    def _get_client(self) -> Any:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("missing_openrouter_api_key")
            self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client


def _route_by_rules(message: str) -> RouteDecision | None:
    text = message.strip()
    if _matches_any(_UNSUPPORTED_PATTERNS, text):
        return RouteDecision.unsupported(source=RouteSource.RULES, reason="rules_out_of_scope", confidence=1.0)
    if _matches_any(_FACTUAL_NUMERIC_LOOKUP_PATTERNS, text):
        return RouteDecision(route=QueryRoute.FACTUAL, confidence=1.0, source=RouteSource.RULES)
    if _matches_any(_COMPARISON_PATTERNS, text):
        return RouteDecision(
            route=QueryRoute.COMPARISON,
            confidence=1.0,
            source=RouteSource.RULES,
            reason="rules_comparison",
        )
    if _matches_any(_MULTI_HOP_PATTERNS, text):
        return RouteDecision(
            route=QueryRoute.MULTI_HOP,
            confidence=1.0,
            source=RouteSource.RULES,
            reason="rules_multi_hop",
        )
    if _matches_any(_AGGREGATION_PATTERNS, text):
        return RouteDecision(
            route=QueryRoute.AGGREGATION,
            confidence=1.0,
            source=RouteSource.RULES,
            reason="rules_aggregation",
        )
    if _matches_any(_FACTUAL_PATTERNS, text):
        return RouteDecision(route=QueryRoute.FACTUAL, confidence=1.0, source=RouteSource.RULES, reason="rules_factual")
    return None


def _render_prompt(query: QueryInput) -> str:
    history = "\n".join(f"{item.role}: {item.content}" for item in query.conversation_history[-4:])
    return "\n\n".join(
        (
            "You classify corporate RAG questions into exactly one route.",
            "Allowed query_type values: FACTUAL, AGGREGATION, MULTI_HOP, COMPARISON, UNSUPPORTED.",
            "Return only JSON matching the requested schema with query_type and confidence.",
            f"Conversation history:\n{history or '(none)'}",
            f"Question:\n{query.message}",
        )
    )


def _structured_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "query_route_classifier_result",
            "strict": True,
            "schema": _strip_unsupported_schema_keys(RouteClassifierResponse.model_json_schema()),
        },
    }


def _parse_response(response: Any) -> RouteClassifierResponse:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, RouteClassifierResponse):
        return parsed
    if parsed is not None:
        return RouteClassifierResponse.model_validate(parsed)
    text = getattr(response, "text", None)
    if text is None:
        text = _completion_message_content(response)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("OpenRouter response text is empty")
    return RouteClassifierResponse.model_validate_json(text)


def _completion_message_content(response: Any) -> str | None:
    choices = getattr(response, "choices", None)
    if not choices:
        return None
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    return content if isinstance(content, str) else None


def _strip_unsupported_schema_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_unsupported_schema_keys(child)
            for key, child in value.items()
            if key not in {"additionalProperties", "additional_properties"}
        }
    if isinstance(value, list):
        return [_strip_unsupported_schema_keys(child) for child in value]
    return value


def _matches_any(patterns: tuple[re.Pattern[str], ...], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _backoff_seconds(attempt: int) -> float:
    return min(1.0, 0.1 * (2 ** max(0, attempt - 1)))
