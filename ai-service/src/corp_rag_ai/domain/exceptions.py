from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class IndexingStage(StrEnum):
    FETCHING = "FETCHING"
    PARSING = "PARSING"
    CHUNKING = "CHUNKING"
    SANITIZATION = "SANITIZATION"
    EMBEDDING = "EMBEDDING"
    VECTOR_UPSERT = "VECTOR_UPSERT"
    ENTITY_EXTRACTION = "ENTITY_EXTRACTION"
    GRAPH_UPSERT = "GRAPH_UPSERT"


DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
INVALID_FILE_FORMAT = "INVALID_FILE_FORMAT"
UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
INDEXING_PIPELINE_ERROR = "INDEXING_PIPELINE_ERROR"


STAGE_MESSAGE_TEMPLATES: dict[IndexingStage, str] = {
    IndexingStage.FETCHING: (
        "Получение файла не выполнено. Dependency detail: {detail}. "
        "Проверьте доступность хранилища и повторите индексацию."
    ),
    IndexingStage.PARSING: (
        "Парсинг документа не выполнен. Parser {parser} could not process MIME type {mime_type}. "
        "Проверьте формат файла."
    ),
    IndexingStage.CHUNKING: (
        "Разбиение документа на фрагменты не выполнено. Internal chunking error: {exception_class}. "
        "Проверьте структуру документа."
    ),
    IndexingStage.SANITIZATION: (
        "Санитизация фрагментов не выполнена. Sanitizer result: {detail}. "
        "Проверьте качество извлеченного текста."
    ),
    IndexingStage.EMBEDDING: (
        "Построение эмбеддингов не выполнено. Local FlagEmbedding bge-m3 error: {exception_class}. "
        "Проверьте модельный кеш, память и зависимости Python AI."
    ),
    IndexingStage.VECTOR_UPSERT: (
        "Запись в Qdrant не выполнена. Qdrant detail: {detail}. "
        "Проверьте коллекцию и доступность Qdrant."
    ),
    IndexingStage.ENTITY_EXTRACTION: (
        "Извлечение сущностей не выполнено. Gemini/entity extraction detail: {detail}. "
        "Проверьте ключ Gemini и структуру ответа."
    ),
    IndexingStage.GRAPH_UPSERT: (
        "Запись в Neo4j не выполнена. Neo4j detail: {detail}. "
        "Проверьте доступность Neo4j и ограничения графа."
    ),
}


@dataclass(frozen=True, slots=True)
class StageFailure(Exception):
    stage: IndexingStage
    error_code: str
    retryable: bool
    message_template: str | None = None
    template_vars: Mapping[str, Any] = field(default_factory=dict)

    def to_error_message(self, max_len: int = 2048) -> str:
        template = self.message_template or STAGE_MESSAGE_TEMPLATES[self.stage]
        rendered = template.format_map(_SafeTemplateValues(self.template_vars))
        rendered = _clean_message(rendered)
        if len(rendered) <= max_len:
            return rendered
        return rendered[: max(0, max_len - 3)].rstrip() + "..."


def stage_failure(
    *,
    stage: IndexingStage | str,
    error_code: str,
    retryable: bool,
    **safe_vars: Any,
) -> StageFailure:
    return StageFailure(
        stage=IndexingStage(stage),
        error_code=error_code,
        retryable=retryable,
        template_vars=safe_vars,
    )


def build_document_indexing_failed_payload(
    *,
    document_id: UUID,
    failure: StageFailure,
    failed_at: datetime | None = None,
    retry_count: int = 0,
) -> dict[str, object]:
    occurred_at = failed_at or datetime.now(UTC)
    return {
        "documentId": str(document_id),
        "stage": failure.stage.value,
        "errorCode": failure.error_code,
        "errorMessage": failure.to_error_message(),
        "failedAt": _isoformat_utc(occurred_at),
        "retryable": failure.retryable,
        "retryCount": retry_count,
    }


class _SafeTemplateValues(defaultdict[str, str]):
    def __init__(self, values: Mapping[str, Any]) -> None:
        super().__init__(lambda: "n/a")
        self._values = values

    def __missing__(self, key: str) -> str:
        return "n/a"

    def __getitem__(self, key: str) -> str:
        if key not in self._values:
            return "n/a"
        return _safe_value(self._values[key])


def _safe_value(value: Any) -> str:
    if isinstance(value, BaseException):
        return value.__class__.__name__
    if isinstance(value, type) and issubclass(value, BaseException):
        return value.__name__
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if "Traceback" in text:
        return "traceback-redacted"
    return _clean_message(text, max_len=240)


def _clean_message(value: str, max_len: int | None = None) -> str:
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    if max_len is not None and len(value) > max_len:
        return value[: max(0, max_len - 3)].rstrip() + "..."
    return value


def _isoformat_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
