from __future__ import annotations

from uuid import UUID

import httpx
import openai
import pytest

from corp_rag_ai.domain.exceptions import DEPENDENCY_UNAVAILABLE, INDEXING_PIPELINE_ERROR, IndexingStage, StageFailure
from corp_rag_ai.pipeline.indexing.entity_extractor import (
    DEFAULT_DEEPSEEK_MODEL,
    ENTITY_EXTRACTION_PROMPT_VERSION,
    DeepSeekEntityExtractor,
    EntityExtractionSource,
    _structured_response_format,
    load_entity_extraction_prompt,
)


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


class _HttpError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


async def _no_sleep(_seconds: float) -> None:
    return None


@pytest.mark.asyncio
async def test_extract_parent_calls_deepseek_structured_output_and_maps_candidates() -> None:
    client = _FakeClient(
        [
            _FakeResponse(
                """
                {
                  "entities": [
                    {"name": "HR department", "type": "department", "description": "HR owns the policy."},
                    {"name": "Vacation Policy", "type": "policy", "description": "Vacation rules."}
                  ],
                  "relations": [
                    {
                      "sourceEntityName": "HR department",
                      "targetEntityName": "Vacation Policy",
                      "type": "owns",
                      "description": "HR owns the policy."
                    }
                  ]
                }
                """
            )
        ]
    )
    extractor = DeepSeekEntityExtractor(client=client, sleep=_no_sleep)

    result = await extractor.extract_parent(
        _source(),
        document_title="HR Policy",
        language="en",
    )

    assert len(result.entities) == 2
    assert len(result.relations) == 1
    assert result.entities[0].normalized_name == "hr department"
    assert result.entities[0].entity_type == "department"
    assert result.entities[0].evidence.chunk_id == _source().chunk_id
    assert result.relations[0].relation_type == "OWNS"
    assert result.relations[0].source_entity_id == result.entities[0].entity_id
    assert result.relations[0].target_entity_id == result.entities[1].entity_id

    call = client.chat.completions.calls[0]
    assert call["model"] == DEFAULT_DEEPSEEK_MODEL
    assert call["messages"][0]["role"] == "user"
    assert "HR Policy" in call["messages"][0]["content"]
    assert "Parent chunk ID" in call["messages"][0]["content"]
    assert call["temperature"] == 0.1
    assert call["max_tokens"] == 2000
    assert call["response_format"]["type"] == "json_schema"
    assert call["response_format"]["json_schema"]["strict"] is True
    assert call["extra_body"] == {"plugins": [{"id": "response-healing"}]}


@pytest.mark.asyncio
async def test_unknown_entity_types_are_dropped_with_warning(caplog) -> None:
    client = _FakeClient(
        [
            _FakeResponse(
                """
                {
                  "entities": [
                    {"name": "Secret Group", "type": "team", "description": "Unknown type."},
                    {"name": "Payroll Policy", "type": "policy", "description": "Payroll rules."}
                  ],
                  "relations": []
                }
                """
            )
        ]
    )
    extractor = DeepSeekEntityExtractor(client=client, sleep=_no_sleep)

    result = await extractor.extract_parent(_source(), document_title="Payroll", language="en")

    assert [entity.name for entity in result.entities] == ["Payroll Policy"]
    assert result.warnings == ("dropped unknown entity type 'team' for entity 'Secret Group'",)
    assert "dropped unknown entity type" in caplog.text


@pytest.mark.asyncio
async def test_empty_entities_are_valid() -> None:
    client = _FakeClient([_FakeResponse('{"entities": [], "relations": []}')])
    extractor = DeepSeekEntityExtractor(client=client, sleep=_no_sleep)

    result = await extractor.extract_parent(_source(), document_title="Empty", language="en")

    assert result.entities == ()
    assert result.relations == ()


@pytest.mark.asyncio
async def test_malformed_structured_output_retries_once_total_then_fails() -> None:
    client = _FakeClient(
        [
            _FakeResponse('{"entities": [{"type": "person", "description": "missing name"}], "relations": []}'),
            _FakeResponse("not json"),
            _FakeResponse('{"entities": [], "relations": []}'),
        ]
    )
    extractor = DeepSeekEntityExtractor(client=client, sleep=_no_sleep)

    with pytest.raises(StageFailure) as failure:
        await extractor.extract_parent(_source(), document_title="Broken", language="en")

    assert failure.value.stage == IndexingStage.ENTITY_EXTRACTION
    assert failure.value.error_code == INDEXING_PIPELINE_ERROR
    assert failure.value.retryable is False
    assert len(client.chat.completions.calls) == 2


@pytest.mark.asyncio
async def test_retryable_dependency_errors_backoff_up_to_three_attempts() -> None:
    client = _FakeClient(
        [
            _HttpError(429),
            _HttpError(503),
            _FakeResponse('{"entities": [], "relations": []}'),
        ]
    )
    extractor = DeepSeekEntityExtractor(client=client, sleep=_no_sleep)

    result = await extractor.extract_parent(_source(), document_title="Retry", language="en")

    assert result.entities == ()
    assert len(client.chat.completions.calls) == 3


@pytest.mark.asyncio
async def test_auth_errors_fail_without_retry_as_non_retryable_dependency() -> None:
    client = _FakeClient([_HttpError(403), _FakeResponse('{"entities": [], "relations": []}')])
    extractor = DeepSeekEntityExtractor(client=client, sleep=_no_sleep)

    with pytest.raises(StageFailure) as failure:
        await extractor.extract_parent(_source(), document_title="Auth", language="en")

    assert failure.value.stage == IndexingStage.ENTITY_EXTRACTION
    assert failure.value.error_code == DEPENDENCY_UNAVAILABLE
    assert failure.value.retryable is False
    assert len(client.chat.completions.calls) == 1


@pytest.mark.asyncio
async def test_openai_bad_request_raises_stage_failure_without_traceback_type_error() -> None:
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(400, request=request)
    bad_request = openai.BadRequestError(
        message="Invalid response_format schema.",
        response=response,
        body={"error": {"code": 400, "message": "Invalid schema"}},
    )
    client = _FakeClient([bad_request])
    extractor = DeepSeekEntityExtractor(client=client, sleep=_no_sleep)

    with pytest.raises(StageFailure) as failure:
        await extractor.extract_parent(_source(), document_title="Broken schema", language="en")

    assert failure.value.stage == IndexingStage.ENTITY_EXTRACTION
    assert failure.value.error_code == INDEXING_PIPELINE_ERROR
    assert failure.value.retryable is False
    assert failure.value.__traceback__ is not None


def test_openrouter_response_schema_strips_additional_properties_recursively() -> None:
    schema = _structured_response_format()["json_schema"]["schema"]

    assert not _contains_schema_key(schema, "additionalProperties")
    assert not _contains_schema_key(schema, "additional_properties")


def test_prompt_artifact_is_versioned_and_has_required_sections() -> None:
    prompt = load_entity_extraction_prompt()

    assert ENTITY_EXTRACTION_PROMPT_VERSION == "entity_extraction_v1"
    assert "Allowed entity types" in prompt.system_prompt
    assert "UPPER_SNAKE_CASE" in prompt.system_prompt
    assert "{document_title}" in prompt.user_template
    assert "{text}" in prompt.user_template


def _source() -> EntityExtractionSource:
    return EntityExtractionSource(
        text="The HR department owns the Vacation Policy.",
        chunk_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        parent_chunk_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        section_path=("Benefits",),
    )


def _contains_schema_key(value, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_schema_key(child, key) for child in value.values())
    if isinstance(value, list):
        return any(_contains_schema_key(child, key) for child in value)
    return False
