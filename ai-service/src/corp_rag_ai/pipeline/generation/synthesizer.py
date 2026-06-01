from __future__ import annotations

"""DeepSeek answer synthesis with escaped evidence sentinels.

The packed context may contain XML-like evidence text, including fake closing
tags such as `</source>`. Prompt rendering wraps evidence in a per-request
random sentinel and HTML-escapes the packed context before insertion, so text
from retrieved documents cannot close or forge the prompt boundary.
"""

import asyncio
import html
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field

from corp_rag_ai.domain.query import QueryInput, RefusalReason
from corp_rag_ai.observability import NoopQueryObservability, QueryObservability
from corp_rag_ai.pipeline.retrieval.context_packer import PackedContext

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_DEEPSEEK_MODEL = "deepseek/deepseek-v4-flash:free"
DEFAULT_MAX_OUTPUT_TOKENS = 2000
DEFAULT_TEMPERATURE = 0.0
DEFAULT_DEPENDENCY_ATTEMPTS = 2
DEFAULT_CITATION_ATTEMPTS = 2
SYNTHESIS_PROMPT_VERSION = "synthesis_v1"


class SynthesisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answered: bool
    answer: str
    citation_indexes: list[int] = Field(default_factory=list)
    confidence_hint: float = Field(ge=0.0, le=1.0)


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    answered: bool
    answer: str
    citation_indexes: tuple[int, ...]
    confidence_hint: float
    failure_reason: RefusalReason | str | None = None


SleepFn = Callable[[float], Awaitable[None]]


class DeepSeekAnswerSynthesizer:
    def __init__(
        self,
        *,
        client: Any | None = None,
        api_key: str | None = None,
        base_url: str = DEFAULT_OPENROUTER_BASE_URL,
        model: str = DEFAULT_DEEPSEEK_MODEL,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        max_dependency_attempts: int = DEFAULT_DEPENDENCY_ATTEMPTS,
        max_citation_attempts: int = DEFAULT_CITATION_ATTEMPTS,
        sleep: SleepFn = asyncio.sleep,
        observability: QueryObservability | NoopQueryObservability | None = None,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._max_dependency_attempts = max_dependency_attempts
        self._max_citation_attempts = max(1, max_citation_attempts)
        self._sleep = sleep
        self._observability = observability or NoopQueryObservability()

    async def synthesize(self, query: QueryInput, context: PackedContext) -> SynthesisResult:
        prompt = _render_prompt(query, context, citation_retry=False)
        parse_failures = 0
        citation_failures = 0
        while True:
            try:
                async with self._observability.generation(
                    name="synthesize_generation",
                    model=self._model,
                    input=prompt,
                    metadata={
                        "provider": "openrouter",
                        "base_url": self._base_url,
                        "prompt_version": SYNTHESIS_PROMPT_VERSION,
                    },
                ) as generation:
                    response = await self._create_completion(prompt)
                    generation.update(output=_completion_message_content(response), usage=_completion_usage(response))
                parsed = _parse_response(response)
                if _needs_citation_retry(parsed, context):
                    citation_failures += 1
                    if citation_failures < self._max_citation_attempts:
                        prompt = _render_prompt(query, context, citation_retry=True, previous_answer=parsed.answer)
                        await self._sleep(_backoff_seconds(citation_failures))
                        continue
                return SynthesisResult(
                    answered=parsed.answered,
                    answer=parsed.answer,
                    citation_indexes=tuple(parsed.citation_indexes),
                    confidence_hint=parsed.confidence_hint,
                )
            except ValueError:
                parse_failures += 1
                if parse_failures >= self._max_dependency_attempts:
                    return _failure(RefusalReason.GENERATION_UNAVAILABLE)
                await self._sleep(_backoff_seconds(parse_failures))
            except Exception:
                return _failure(RefusalReason.GENERATION_UNAVAILABLE)

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


def _render_prompt(
    query: QueryInput,
    context: PackedContext,
    *,
    citation_retry: bool,
    previous_answer: str = "",
) -> str:
    sentinel = f"CORP_RAG_EVIDENCE_{uuid4().hex}"
    escaped_context = html.escape(context.text, quote=False)
    retry_instruction = (
        "\nPrevious answer omitted valid inline citations. Regenerate the answer with inline [N] markers."
        f"\nPrevious answer: {html.escape(previous_answer, quote=False)}"
        if citation_retry
        else ""
    )
    return "\n\n".join(
        (
            "You answer corporate document questions using only the provided evidence.",
            "If the evidence supports an answer, every factual sentence in answer MUST include an inline citation marker like [1].",
            "Use only citation indexes that appear in the provided evidence. Do not answer true unless answer contains at least one [N].",
            "Example valid answer: Managers must approve vacation requests within five business days [1].",
            "Example invalid answer: Managers must approve vacation requests within five business days.",
            "Return strict JSON with answered, answer, citation_indexes, and confidence_hint.",
            "When answered is true, citation_indexes MUST list each [N] used in answer.",
            retry_instruction.strip(),
            f"Question: {query.message}",
            f"<<<{sentinel}_START>>>",
            escaped_context,
            f"<<<{sentinel}_END>>>",
        )
    )


def _needs_citation_retry(parsed: SynthesisResponse, context: PackedContext) -> bool:
    if not parsed.answered or not context.citations:
        return False
    refs = tuple(int(match) for match in re.findall(r"\[(\d+)\]", parsed.answer))
    valid_indexes = set(range(1, len(context.citations) + 1))
    if any(ref not in valid_indexes for ref in refs):
        return True
    if any(index not in valid_indexes for index in parsed.citation_indexes):
        return True
    return not refs and _looks_factual(parsed.answer)


def _looks_factual(answer: str) -> bool:
    text = answer.strip()
    return any(char.isalnum() for char in text) and len(text.split()) >= 4


def _structured_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "cited_answer_result",
            "strict": True,
            "schema": _strip_unsupported_schema_keys(SynthesisResponse.model_json_schema()),
        },
    }


def _parse_response(response: Any) -> SynthesisResponse:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, SynthesisResponse):
        return parsed
    if parsed is not None:
        return SynthesisResponse.model_validate(parsed)
    text = getattr(response, "text", None) or _completion_message_content(response)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("OpenRouter response text is empty")
    return SynthesisResponse.model_validate_json(text)


def _completion_message_content(response: Any) -> str | None:
    choices = getattr(response, "choices", None)
    if not choices:
        return None
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    return content if isinstance(content, str) else None


def _completion_usage(response: Any) -> dict[str, int] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump(exclude_none=True)
    result = {
        key: int(value)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if isinstance((value := getattr(usage, key, None)), int)
    }
    return result or None


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


def _failure(reason: RefusalReason) -> SynthesisResult:
    return SynthesisResult(
        answered=False,
        answer="Answer generation is temporarily unavailable.",
        citation_indexes=(),
        confidence_hint=0.0,
        failure_reason=reason,
    )


def _backoff_seconds(attempt: int) -> float:
    return min(1.0, 0.1 * (2 ** max(0, attempt - 1)))
