from __future__ import annotations

from uuid import UUID

import pytest

from corp_rag_ai.domain.exceptions import INDEXING_PIPELINE_ERROR, DEPENDENCY_UNAVAILABLE, IndexingStage, StageFailure
from corp_rag_ai.pipeline.indexing.entity_extractor import (
    DEFAULT_GEMINI_MODEL,
    ENTITY_EXTRACTION_PROMPT_VERSION,
    EntityExtractionSource,
    GeminiEntityExtractor,
    load_entity_extraction_prompt,
)


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModels:
    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeClient:
    def __init__(self, outcomes) -> None:
        self.models = _FakeModels(outcomes)


class _HttpError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


async def _no_sleep(_seconds: float) -> None:
    return None


@pytest.mark.asyncio
async def test_extract_parent_calls_gemini_structured_output_and_maps_candidates() -> None:
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
    extractor = GeminiEntityExtractor(client=client, sleep=_no_sleep)

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

    call = client.models.calls[0]
    assert call["model"] == DEFAULT_GEMINI_MODEL
    assert "HR Policy" in call["contents"]
    assert "Parent chunk ID" in call["contents"]
    config = call["config"]
    assert getattr(config, "temperature", None) == 0.1
    assert getattr(config, "max_output_tokens", None) == 2000
    assert getattr(config, "response_mime_type", None) == "application/json"


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
    extractor = GeminiEntityExtractor(client=client, sleep=_no_sleep)

    result = await extractor.extract_parent(_source(), document_title="Payroll", language="en")

    assert [entity.name for entity in result.entities] == ["Payroll Policy"]
    assert result.warnings == ("dropped unknown entity type 'team' for entity 'Secret Group'",)
    assert "dropped unknown entity type" in caplog.text


@pytest.mark.asyncio
async def test_empty_entities_are_valid() -> None:
    client = _FakeClient([_FakeResponse('{"entities": [], "relations": []}')])
    extractor = GeminiEntityExtractor(client=client, sleep=_no_sleep)

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
    extractor = GeminiEntityExtractor(client=client, sleep=_no_sleep)

    with pytest.raises(StageFailure) as failure:
        await extractor.extract_parent(_source(), document_title="Broken", language="en")

    assert failure.value.stage == IndexingStage.ENTITY_EXTRACTION
    assert failure.value.error_code == INDEXING_PIPELINE_ERROR
    assert failure.value.retryable is False
    assert len(client.models.calls) == 2


@pytest.mark.asyncio
async def test_retryable_dependency_errors_backoff_up_to_three_attempts() -> None:
    client = _FakeClient(
        [
            _HttpError(429),
            _HttpError(503),
            _FakeResponse('{"entities": [], "relations": []}'),
        ]
    )
    extractor = GeminiEntityExtractor(client=client, sleep=_no_sleep)

    result = await extractor.extract_parent(_source(), document_title="Retry", language="en")

    assert result.entities == ()
    assert len(client.models.calls) == 3


@pytest.mark.asyncio
async def test_auth_errors_fail_without_retry_as_non_retryable_dependency() -> None:
    client = _FakeClient([_HttpError(403), _FakeResponse('{"entities": [], "relations": []}')])
    extractor = GeminiEntityExtractor(client=client, sleep=_no_sleep)

    with pytest.raises(StageFailure) as failure:
        await extractor.extract_parent(_source(), document_title="Auth", language="en")

    assert failure.value.stage == IndexingStage.ENTITY_EXTRACTION
    assert failure.value.error_code == DEPENDENCY_UNAVAILABLE
    assert failure.value.retryable is False
    assert len(client.models.calls) == 1


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
