from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class IndexStatus(StrEnum):
    """Durable document indexing state owned by the AI service."""

    PENDING = "PENDING"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"
    DELETED = "DELETED"


@dataclass(frozen=True, slots=True)
class DocumentIndexState:
    document_id: UUID
    status: IndexStatus
    last_indexed_event_id: UUID | None
    last_failure_stage: str | None
    last_failure_code: str | None
    last_failure_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ParentChunkRecord:
    parent_chunk_id: UUID
    document_id: UUID
    section_path: tuple[str, ...]
    content: str
    position: int
    token_count: int

    def __post_init__(self) -> None:
        if self.position < 0:
            raise ValueError("position must be non-negative")
        if self.token_count < 0:
            raise ValueError("token_count must be non-negative")
        if not self.content:
            raise ValueError("content must not be empty")


@dataclass(frozen=True, slots=True)
class ProcessedEvent:
    event_id: UUID
    event_type: str
    consumed_at: datetime

