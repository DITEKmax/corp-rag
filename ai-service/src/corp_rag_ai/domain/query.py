from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4

from corp_rag_ai.domain.guard import GuardVerdict
from corp_rag_ai.domain.retrieval import CitationDraft, RetrievalMetadata

MAX_QUERY_MESSAGE_LENGTH = 2000
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_MESSAGE_LENGTH = 4000
DEFAULT_TOP_K = 10
MAX_TOP_K = 20


class QueryRoute(str, Enum):
    FACTUAL = "FACTUAL"
    AGGREGATION = "AGGREGATION"
    MULTI_HOP = "MULTI_HOP"
    COMPARISON = "COMPARISON"
    UNSUPPORTED = "UNSUPPORTED"


class RouteSource(str, Enum):
    RULES = "rules"
    LLM = "llm"
    FALLBACK = "fallback"
    FORCED = "forced"


class RefusalReason(str, Enum):
    PROMPT_INJECTION = "prompt_injection"
    OUT_OF_SCOPE = "out_of_scope"
    POLICY = "policy"
    UNSUPPORTED = "unsupported"
    LOW_CONFIDENCE = "low_confidence"
    NO_EVIDENCE = "no_evidence"
    WEAK_EVIDENCE = "weak_evidence"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    role: str
    content: str

    def __post_init__(self) -> None:
        role = _enum_value(self.role).strip().lower()
        content = self.content.strip()
        if role not in {"user", "assistant"}:
            raise ValueError("conversation role must be user or assistant")
        if not content:
            raise ValueError("conversation content is required")
        if len(content) > MAX_HISTORY_MESSAGE_LENGTH:
            raise ValueError("conversation content exceeds maximum length")
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "content", content)


@dataclass(frozen=True, slots=True)
class AccessFilter:
    access_levels: tuple[str, ...]
    departments: tuple[str, ...]
    doc_types: tuple[str, ...]

    def __post_init__(self) -> None:
        access_levels = _normalize_upper_tuple(self.access_levels)
        departments = _normalize_plain_tuple(self.departments)
        doc_types = _normalize_upper_tuple(self.doc_types)
        if not access_levels:
            raise ValueError("access filter requires at least one access level")
        if not doc_types:
            raise ValueError("access filter requires at least one document type")
        object.__setattr__(self, "access_levels", access_levels)
        object.__setattr__(self, "departments", departments)
        object.__setattr__(self, "doc_types", doc_types)

    @property
    def department_wildcard(self) -> bool:
        return not self.departments


@dataclass(frozen=True, slots=True)
class RetrievalOptions:
    top_k: int = DEFAULT_TOP_K
    reranker_enabled: bool = True
    force_route: QueryRoute | None = None

    @classmethod
    def from_values(
        cls,
        *,
        top_k: int | None = None,
        reranker_enabled: bool | None = None,
        force_route: QueryRoute | str | None = None,
        default_top_k: int = DEFAULT_TOP_K,
        max_top_k: int = MAX_TOP_K,
        default_reranker_enabled: bool = True,
    ) -> RetrievalOptions:
        top_k_value = default_top_k if top_k is None else int(top_k)
        top_k_value = min(max(top_k_value, 1), max_top_k)
        route = QueryRoute(_enum_value(force_route)) if force_route is not None else None
        return cls(
            top_k=top_k_value,
            reranker_enabled=default_reranker_enabled if reranker_enabled is None else bool(reranker_enabled),
            force_route=route,
        )

    def __post_init__(self) -> None:
        if self.top_k < 1 or self.top_k > MAX_TOP_K:
            raise ValueError("top_k must be within the contract range")


@dataclass(frozen=True, slots=True)
class QueryInput:
    user_id: UUID
    correlation_id: UUID
    conversation_id: UUID
    message: str
    access_filter: AccessFilter
    retrieval_options: RetrievalOptions = field(default_factory=RetrievalOptions)
    conversation_history: tuple[ConversationMessage, ...] = ()

    def __post_init__(self) -> None:
        message = self.message.strip()
        history = tuple(self.conversation_history)
        if not message:
            raise ValueError("query message is required")
        if len(message) > MAX_QUERY_MESSAGE_LENGTH:
            raise ValueError("query message exceeds maximum length")
        if len(history) > MAX_HISTORY_MESSAGES:
            raise ValueError("conversation history exceeds maximum item count")
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "conversation_history", history)


@dataclass(frozen=True, slots=True)
class RouteDecision:
    route: QueryRoute
    confidence: float
    source: RouteSource
    reason: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("route confidence must be between 0.0 and 1.0")

    @classmethod
    def unsupported(cls, *, source: RouteSource, reason: str, confidence: float = 0.0) -> RouteDecision:
        return cls(route=QueryRoute.UNSUPPORTED, confidence=confidence, source=source, reason=reason)

    @property
    def allows_retrieval(self) -> bool:
        return self.route is not QueryRoute.UNSUPPORTED


@dataclass(frozen=True, slots=True)
class QueryRefusal:
    reason: RefusalReason | str
    message: str
    guard_verdict: GuardVerdict | None = None
    route_decision: RouteDecision | None = None


@dataclass(frozen=True, slots=True)
class QueryResult:
    answered: bool
    answer: str
    citations: tuple[CitationDraft, ...]
    confidence: float
    conversation_id: UUID
    message_id: UUID
    retrieval_meta: RetrievalMetadata
    guard_verdict: GuardVerdict | None = None
    refusal_reason: RefusalReason | str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("query confidence must be between 0.0 and 1.0")
        if not self.answered and self.citations:
            raise ValueError("unanswered query results must not contain citations")
        object.__setattr__(self, "citations", tuple(self.citations))

    @classmethod
    def refused(
        cls,
        *,
        query: QueryInput,
        reason: RefusalReason | str,
        answer: str,
        retrieval_meta: RetrievalMetadata,
        guard_verdict: GuardVerdict | None = None,
        message_id: UUID | None = None,
    ) -> QueryResult:
        return cls(
            answered=False,
            answer=answer,
            citations=(),
            confidence=0.0,
            conversation_id=query.conversation_id,
            message_id=message_id or uuid4(),
            guard_verdict=guard_verdict,
            retrieval_meta=retrieval_meta,
            refusal_reason=reason,
        )


def _normalize_upper_tuple(values: tuple[object, ...]) -> tuple[str, ...]:
    return _dedupe(value.strip().upper() for value in (_enum_value(item) for item in values) if value.strip())


def _normalize_plain_tuple(values: tuple[object, ...]) -> tuple[str, ...]:
    return _dedupe(value.strip() for value in (_enum_value(item) for item in values) if value.strip())


def _dedupe(values: object) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw)
