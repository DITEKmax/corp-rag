from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any

from corp_rag_ai.domain.query import RefusalReason

RERANKER_UNAVAILABLE_WARNING = "reranker_unavailable"


@dataclass(frozen=True, slots=True)
class QueryMetricsSnapshot:
    total_queries: int = 0
    answered_count: int = 0
    refused_no_evidence_count: int = 0
    guard_blocked_count: int = 0
    reranker_degraded_count: int = 0
    total_latency_ms: int = 0

    @property
    def answered_rate(self) -> float:
        return self.answered_count / self.total_queries if self.total_queries else 0.0

    @property
    def mean_latency_ms(self) -> int:
        return int(self.total_latency_ms / self.total_queries) if self.total_queries else 0

    def as_dict(self) -> dict[str, int | float]:
        return {
            "query_count": self.total_queries,
            "answered_count": self.answered_count,
            "answered_rate": round(self.answered_rate, 4),
            "refused_no_evidence_count": self.refused_no_evidence_count,
            "guard_blocked_count": self.guard_blocked_count,
            "reranker_degraded_count": self.reranker_degraded_count,
            "mean_latency_ms": self.mean_latency_ms,
        }


class QueryMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._snapshot = QueryMetricsSnapshot()

    def record(self, result: Any) -> None:
        meta = result.retrieval_meta
        reason = _enum_value(result.refusal_reason)
        guard_blocked = result.guard_verdict is not None and result.guard_verdict.blocked
        reranker_degraded = RERANKER_UNAVAILABLE_WARNING in tuple(meta.degradation_warnings or ())
        with self._lock:
            current = self._snapshot
            self._snapshot = QueryMetricsSnapshot(
                total_queries=current.total_queries + 1,
                answered_count=current.answered_count + int(bool(result.answered)),
                refused_no_evidence_count=current.refused_no_evidence_count
                + int(reason == RefusalReason.NO_EVIDENCE.value),
                guard_blocked_count=current.guard_blocked_count + int(guard_blocked),
                reranker_degraded_count=current.reranker_degraded_count + int(reranker_degraded),
                total_latency_ms=current.total_latency_ms + int(meta.latency_ms),
            )

    def snapshot(self) -> QueryMetricsSnapshot:
        with self._lock:
            return self._snapshot


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return "" if raw is None else str(raw)
