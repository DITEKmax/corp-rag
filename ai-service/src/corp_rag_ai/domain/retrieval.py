from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID


class RetrieverType(str, Enum):
    HYBRID = "HYBRID"
    GRAPH = "GRAPH"


class RetrievalFailureReason(str, Enum):
    EMBEDDING_UNAVAILABLE = "embedding_unavailable"
    VECTOR_RETRIEVAL_UNAVAILABLE = "vector_retrieval_unavailable"


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    chunk_id: UUID
    document_id: UUID
    document_title: str
    section_path: tuple[str, ...]
    content: str
    score: float
    access_level: str
    retriever: RetrieverType
    parent_chunk_id: UUID | None = None
    page_number: int | None = None
    snippet: str | None = None
    sanitizer_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("retrieval candidate score must be between 0.0 and 1.0")
        if self.page_number is not None and self.page_number < 1:
            raise ValueError("page number must be positive")
        object.__setattr__(self, "section_path", tuple(part.strip() for part in self.section_path if part.strip()))
        object.__setattr__(self, "access_level", self.access_level.strip().upper())
        object.__setattr__(self, "sanitizer_flags", tuple(self.sanitizer_flags))


@dataclass(frozen=True, slots=True)
class CitationDraft:
    document_id: UUID
    document_title: str
    chunk_id: UUID
    section_path: tuple[str, ...]
    quote: str
    score: float
    access_level: str
    snippet: str | None = None
    page_number: int | None = None

    def __post_init__(self) -> None:
        if not self.quote.strip():
            raise ValueError("citation quote is required")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("citation score must be between 0.0 and 1.0")
        if self.page_number is not None and self.page_number < 1:
            raise ValueError("page number must be positive")
        object.__setattr__(self, "section_path", tuple(part.strip() for part in self.section_path if part.strip()))
        object.__setattr__(self, "access_level", self.access_level.strip().upper())

    @classmethod
    def from_candidate(cls, candidate: RetrievalCandidate, *, quote: str | None = None) -> CitationDraft:
        return cls(
            document_id=candidate.document_id,
            document_title=candidate.document_title,
            chunk_id=candidate.chunk_id,
            section_path=candidate.section_path,
            quote=quote or candidate.snippet or candidate.content,
            snippet=candidate.snippet,
            page_number=candidate.page_number,
            score=candidate.score,
            access_level=candidate.access_level,
        )

    @property
    def section_path_label(self) -> str:
        return " > ".join(self.section_path)


@dataclass(frozen=True, slots=True)
class RetrievalMetadata:
    route: str
    retrievers_attempted: tuple[RetrieverType, ...] = ()
    retrievers_used: tuple[RetrieverType, ...] = ()
    degradation_warnings: tuple[str, ...] = ()
    latency_ms: int = 0
    chunks_considered: int = 0
    chunks_returned: int = 0
    reranker_used: bool = False
    model_id: str = ""

    def __post_init__(self) -> None:
        if self.latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")
        if self.chunks_considered < 0 or self.chunks_returned < 0:
            raise ValueError("chunk counts must be non-negative")
        object.__setattr__(self, "route", _enum_value(self.route))
        object.__setattr__(self, "retrievers_attempted", tuple(self.retrievers_attempted))
        object.__setattr__(self, "retrievers_used", tuple(self.retrievers_used))
        object.__setattr__(self, "degradation_warnings", tuple(self.degradation_warnings))


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    candidates: tuple[RetrievalCandidate, ...]
    metadata: RetrievalMetadata
    failure_reason: RetrievalFailureReason | str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidates", tuple(self.candidates))

    @property
    def failed(self) -> bool:
        return self.failure_reason is not None
