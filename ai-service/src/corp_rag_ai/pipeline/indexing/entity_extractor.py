from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field as dataclass_field
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from corp_rag_ai.domain.exceptions import (
    DEPENDENCY_UNAVAILABLE,
    INDEXING_PIPELINE_ERROR,
    IndexingStage,
    StageFailure,
    stage_failure,
)
from corp_rag_ai.pipeline.indexing.embedding import EmbeddingVector
from corp_rag_ai.pipeline.indexing.graph_indexer import (
    GraphDocument,
    GraphDocumentIndex,
    GraphEntity,
    GraphEvidence,
    GraphRelationMention,
    deterministic_entity_id,
    deterministic_relation_mention_id,
    normalize_entity_name,
    normalize_entity_type,
    normalize_relation_type,
)

logger = logging.getLogger(__name__)

ENTITY_EXTRACTION_PROMPT_VERSION = "entity_extraction_v1"
DEFAULT_DEEPSEEK_MODEL = "deepseek/deepseek-v4-flash:free"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MAX_OUTPUT_TOKENS = 2000
DEFAULT_TEMPERATURE = 0.1
DEFAULT_DEPENDENCY_ATTEMPTS = 3
PROMPT_PATH = Path(__file__).with_name("prompts") / f"{ENTITY_EXTRACTION_PROMPT_VERSION}.md"


@dataclass(frozen=True, slots=True)
class EntityExtractionPrompt:
    system_prompt: str
    user_template: str

    def render_user(
        self,
        *,
        document_title: str,
        language: str,
        source: EntityExtractionSource,
    ) -> str:
        section_path = " > ".join(source.section_path) if source.section_path else "(root)"
        return (
            self.user_template.replace("{document_title}", document_title)
            .replace("{language}", language)
            .replace("{section_path}", section_path)
            .replace("{parent_chunk_id}", str(source.parent_chunk_id))
            .replace("{chunk_id}", str(source.chunk_id))
            .replace("{text}", source.text)
        )


@dataclass(frozen=True, slots=True)
class EntityExtractionSource:
    text: str
    chunk_id: UUID
    parent_chunk_id: UUID
    section_path: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExtractedEntityCandidate:
    entity_id: UUID
    name: str
    normalized_name: str
    entity_type: str
    description: str
    evidence: GraphEvidence


@dataclass(frozen=True, slots=True)
class ExtractedRelationCandidate:
    relation_id: UUID
    relation_type: str
    source_entity_id: UUID
    target_entity_id: UUID
    description: str
    evidence: GraphEvidence


@dataclass(frozen=True, slots=True)
class ParentEntityExtraction:
    entities: tuple[ExtractedEntityCandidate, ...]
    relations: tuple[ExtractedRelationCandidate, ...]
    warnings: tuple[str, ...] = ()


class EntityExtractionEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    description: str = Field(default="", max_length=500)

    @field_validator("type")
    @classmethod
    def _type_is_plain_text(cls, value: str) -> str:
        return value.strip().lower()


class EntityExtractionRelation(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    source_entity_name: str = Field(alias="sourceEntityName", min_length=1)
    target_entity_name: str = Field(alias="targetEntityName", min_length=1)
    type: str = Field(min_length=1)
    description: str = Field(default="", max_length=500)


class EntityExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: list[EntityExtractionEntity] = Field(default_factory=list)
    relations: list[EntityExtractionRelation] = Field(default_factory=list)


SleepFn = Callable[[float], Awaitable[None]]


class EntityEmbeddingProvider(Protocol):
    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingVector, ...]:
        ...


class DeepSeekEntityExtractor:
    def __init__(
        self,
        *,
        client: Any | None = None,
        api_key: str | None = None,
        base_url: str = DEFAULT_OPENROUTER_BASE_URL,
        model: str = DEFAULT_DEEPSEEK_MODEL,
        prompt: EntityExtractionPrompt | None = None,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        max_dependency_attempts: int = DEFAULT_DEPENDENCY_ATTEMPTS,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._prompt = prompt or load_entity_extraction_prompt()
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._max_dependency_attempts = max_dependency_attempts
        self._sleep = sleep

    async def extract_parent(
        self,
        source: EntityExtractionSource,
        *,
        document_title: str,
        language: str,
    ) -> ParentEntityExtraction:
        contents = self._render_contents(source, document_title=document_title, language=language)
        malformed_retry_used = False
        dependency_attempt = 0

        while True:
            dependency_attempt += 1
            try:
                response = await self._create_completion(contents)
            except StageFailure:
                raise
            except Exception as exc:
                if _is_auth_error(exc):
                    raise _dependency_failure(exc, retryable=False) from exc
                if _is_retryable_dependency_error(exc) and dependency_attempt < self._max_dependency_attempts:
                    await self._sleep(_backoff_seconds(dependency_attempt))
                    continue
                if _is_retryable_dependency_error(exc):
                    raise _dependency_failure(exc, retryable=True) from exc
                raise _malformed_or_sdk_failure(exc) from exc

            try:
                parsed = _parse_response(response)
            except (ValidationError, ValueError) as exc:
                logger.warning(
                    "Malformed DeepSeek/OpenRouter structured entity extraction response",
                    extra={"raw_openrouter_response": _raw_response_text(response)},
                )
                if malformed_retry_used:
                    raise _malformed_output_failure() from exc
                malformed_retry_used = True
                await self._sleep(_backoff_seconds(1))
                continue

            return _map_parent_extraction(parsed, source)

    def _render_contents(self, source: EntityExtractionSource, *, document_title: str, language: str) -> str:
        return "\n\n".join(
            (
                self._prompt.system_prompt,
                self._prompt.render_user(
                    document_title=document_title,
                    language=language,
                    source=source,
                ),
            )
        )

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
                raise stage_failure(
                    stage=IndexingStage.ENTITY_EXTRACTION,
                    error_code=DEPENDENCY_UNAVAILABLE,
                    retryable=False,
                    detail="missing_openrouter_api_key",
                )
            self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client


def load_entity_extraction_prompt(prompt_path: str | Path | None = None) -> EntityExtractionPrompt:
    return _parse_prompt(_read_prompt(str(prompt_path or PROMPT_PATH)))


@lru_cache(maxsize=8)
def _read_prompt(prompt_path: str) -> str:
    return Path(prompt_path).read_text(encoding="utf-8")


def _parse_prompt(text: str) -> EntityExtractionPrompt:
    system_marker = "## System prompt"
    user_marker = "## User template"
    if system_marker not in text or user_marker not in text:
        raise ValueError("entity extraction prompt must include system and user template sections")
    _before, system_and_after = text.split(system_marker, 1)
    system_text, user_text = system_and_after.split(user_marker, 1)
    return EntityExtractionPrompt(
        system_prompt=system_text.strip(),
        user_template=user_text.strip(),
    )


def _structured_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "entity_extraction_result",
            "strict": True,
            "schema": _entity_extraction_schema(),
        },
    }


def _entity_extraction_schema() -> dict[str, Any]:
    return _strip_unsupported_schema_keys(EntityExtractionResponse.model_json_schema())


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


def _parse_response(response: Any) -> EntityExtractionResponse:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, EntityExtractionResponse):
        return parsed
    if parsed is not None:
        return EntityExtractionResponse.model_validate(parsed)
    text = getattr(response, "text", None)
    if text is None:
        text = _completion_message_content(response)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("OpenRouter response text is empty")
    return EntityExtractionResponse.model_validate_json(text)


def _completion_message_content(response: Any) -> str | None:
    choices = getattr(response, "choices", None)
    if not choices:
        return None
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    return content if isinstance(content, str) else None


def _map_parent_extraction(
    response: EntityExtractionResponse,
    source: EntityExtractionSource,
) -> ParentEntityExtraction:
    evidence = GraphEvidence(
        chunk_id=source.chunk_id,
        parent_chunk_id=source.parent_chunk_id,
        section_path=source.section_path,
    )
    warnings: list[str] = []
    entities: list[ExtractedEntityCandidate] = []
    entity_by_name: dict[str, ExtractedEntityCandidate] = {}

    for raw_entity in response.entities:
        try:
            entity_type = normalize_entity_type(raw_entity.type)
        except ValueError:
            message = f"dropped unknown entity type '{raw_entity.type}' for entity '{raw_entity.name}'"
            warnings.append(message)
            logger.warning(message)
            continue
        normalized_name = normalize_entity_name(raw_entity.name)
        if not normalized_name:
            continue
        entity = ExtractedEntityCandidate(
            entity_id=deterministic_entity_id(normalized_name, entity_type),
            name=raw_entity.name.strip(),
            normalized_name=normalized_name,
            entity_type=entity_type,
            description=raw_entity.description.strip(),
            evidence=evidence,
        )
        entities.append(entity)
        entity_by_name.setdefault(normalized_name, entity)

    relations: list[ExtractedRelationCandidate] = []
    for raw_relation in response.relations:
        source_entity = entity_by_name.get(normalize_entity_name(raw_relation.source_entity_name))
        target_entity = entity_by_name.get(normalize_entity_name(raw_relation.target_entity_name))
        if source_entity is None or target_entity is None:
            warnings.append(f"dropped relation '{raw_relation.type}' because source or target entity was not extracted")
            continue
        relation_type = normalize_relation_type(raw_relation.type)
        relations.append(
            ExtractedRelationCandidate(
                relation_id=deterministic_relation_mention_id(
                    source_entity.entity_id,
                    target_entity.entity_id,
                    relation_type,
                ),
                relation_type=relation_type,
                source_entity_id=source_entity.entity_id,
                target_entity_id=target_entity.entity_id,
                description=raw_relation.description.strip(),
                evidence=evidence,
            )
        )

    return ParentEntityExtraction(
        entities=tuple(entities),
        relations=tuple(relations),
        warnings=tuple(warnings),
    )


def build_graph_document_index(
    *,
    document: GraphDocument,
    parent_extractions: Sequence[ParentEntityExtraction],
    embedder: EntityEmbeddingProvider,
) -> GraphDocumentIndex:
    entity_builders: dict[UUID, _EntityCandidateBuilder] = {}
    relation_builders: dict[UUID, _RelationCandidateBuilder] = {}
    warnings: list[str] = []

    for parent in parent_extractions:
        warnings.extend(parent.warnings)
        for entity in parent.entities:
            builder = entity_builders.setdefault(
                entity.entity_id,
                _EntityCandidateBuilder(
                    entity_id=entity.entity_id,
                    name=entity.name,
                    normalized_name=entity.normalized_name,
                    entity_type=entity.entity_type,
                    description=entity.description,
                ),
            )
            _append_unique_evidence(builder.evidence, entity.evidence)

        for relation in parent.relations:
            builder = relation_builders.setdefault(
                relation.relation_id,
                _RelationCandidateBuilder(
                    relation_id=relation.relation_id,
                    relation_type=relation.relation_type,
                    source_entity_id=relation.source_entity_id,
                    target_entity_id=relation.target_entity_id,
                    description=relation.description,
                ),
            )
            _append_unique_evidence(builder.evidence, relation.evidence)

    entity_values = tuple(entity_builders.values())
    embeddings = _embed_unique_entities(embedder, entity_values)
    graph_entities = tuple(
        GraphEntity(
            entity_id=builder.entity_id,
            name=builder.name,
            normalized_name=builder.normalized_name,
            entity_type=builder.entity_type,
            description=builder.description,
            embedding=embedding.dense,
            mentions=tuple(builder.evidence),
        )
        for builder, embedding in zip(entity_values, embeddings, strict=True)
    )
    graph_relations = tuple(
        GraphRelationMention(
            relation_id=builder.relation_id,
            relation_type=builder.relation_type,
            source_entity_id=builder.source_entity_id,
            target_entity_id=builder.target_entity_id,
            description=builder.description,
            evidence=tuple(builder.evidence),
        )
        for builder in relation_builders.values()
    )
    return GraphDocumentIndex(
        document=document,
        entities=graph_entities,
        relations=graph_relations,
        warnings=tuple(warnings),
    )


@dataclass(slots=True)
class _EntityCandidateBuilder:
    entity_id: UUID
    name: str
    normalized_name: str
    entity_type: str
    description: str
    evidence: list[GraphEvidence] = dataclass_field(default_factory=list)


@dataclass(slots=True)
class _RelationCandidateBuilder:
    relation_id: UUID
    relation_type: str
    source_entity_id: UUID
    target_entity_id: UUID
    description: str
    evidence: list[GraphEvidence] = dataclass_field(default_factory=list)


def entity_embedding_text(*, name: str, entity_type: str, description: str) -> str:
    parts = [name.strip(), f"type: {entity_type.strip()}"]
    if description.strip():
        parts.append(description.strip())
    return "\n".join(parts)


def _embed_unique_entities(
    embedder: EntityEmbeddingProvider,
    entities: Sequence[_EntityCandidateBuilder],
) -> tuple[EmbeddingVector, ...]:
    if not entities:
        return ()
    texts = [
        entity_embedding_text(
            name=entity.name,
            entity_type=entity.entity_type,
            description=entity.description,
        )
        for entity in entities
    ]
    try:
        embeddings = embedder.embed_texts(texts)
    except StageFailure as exc:
        raise _entity_embedding_failure(exc) from exc
    except Exception as exc:
        raise _entity_embedding_failure(exc) from exc
    if len(embeddings) != len(entities):
        raise _entity_embedding_failure(ValueError("entity embedding count mismatch"))
    return embeddings


def _append_unique_evidence(target: list[GraphEvidence], evidence: GraphEvidence) -> None:
    identity = (evidence.chunk_id, evidence.parent_chunk_id)
    if all((item.chunk_id, item.parent_chunk_id) != identity for item in target):
        target.append(evidence)


def _entity_embedding_failure(exc: Exception) -> StageFailure:
    return stage_failure(
        stage=IndexingStage.ENTITY_EXTRACTION,
        error_code=INDEXING_PIPELINE_ERROR,
        retryable=False,
        detail=exc.__class__.__name__,
    )


def _raw_response_text(response: Any) -> str:
    text = getattr(response, "text", "")
    if not text:
        text = _completion_message_content(response) or ""
    return text if isinstance(text, str) else repr(response)


def _status_code(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    return response_status if isinstance(response_status, int) else None


def _is_auth_error(exc: Exception) -> bool:
    return isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)) or _status_code(exc) in {
        401,
        403,
    }


def _is_retryable_dependency_error(exc: Exception) -> bool:
    if isinstance(exc, (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError)):
        return True
    status = _status_code(exc)
    if status == 429 or (status is not None and 500 <= status <= 599):
        return True
    return "timeout" in exc.__class__.__name__.lower()


def _dependency_failure(exc: Exception, *, retryable: bool) -> StageFailure:
    status = _status_code(exc)
    detail = f"status_{status}" if status is not None else exc.__class__.__name__
    return stage_failure(
        stage=IndexingStage.ENTITY_EXTRACTION,
        error_code=DEPENDENCY_UNAVAILABLE,
        retryable=retryable,
        detail=detail,
    )


def _malformed_or_sdk_failure(exc: Exception) -> StageFailure:
    return stage_failure(
        stage=IndexingStage.ENTITY_EXTRACTION,
        error_code=INDEXING_PIPELINE_ERROR,
        retryable=False,
        detail=exc.__class__.__name__,
    )


def _malformed_output_failure() -> StageFailure:
    return stage_failure(
        stage=IndexingStage.ENTITY_EXTRACTION,
        error_code=INDEXING_PIPELINE_ERROR,
        retryable=False,
        detail="malformed_structured_output",
    )


def _backoff_seconds(attempt: int) -> float:
    return min(2.0, 0.25 * (2 ** max(0, attempt - 1)))
