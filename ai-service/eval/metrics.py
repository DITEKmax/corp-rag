from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from eval.schema import GoldenRecord, MetricSummary


@dataclass(frozen=True, slots=True)
class RetrievalObservation:
    record_id: str
    expected_doc_ids: tuple[str, ...]
    retrieved_doc_ids: tuple[str, ...]

    @classmethod
    def from_golden_record(
        cls,
        record: GoldenRecord,
        retrieved_doc_ids: Sequence[str],
    ) -> RetrievalObservation:
        return cls(
            record_id=record.id,
            expected_doc_ids=tuple(record.expected_doc_ids),
            retrieved_doc_ids=tuple(retrieved_doc_ids),
        )


@dataclass(frozen=True, slots=True)
class RetrievalObservationScore:
    record_id: str
    expected_doc_ids: tuple[str, ...]
    retrieved_doc_ids: tuple[str, ...]
    reciprocal_rank: float
    recall_by_k: dict[int, float]
    ndcg_by_k: dict[int, float]


def recall_at_k(expected_doc_ids: Sequence[str], retrieved_doc_ids: Sequence[str], *, k: int) -> float:
    if k < 1:
        raise ValueError("k must be positive")
    expected = set(_dedupe(expected_doc_ids))
    if not expected:
        return 0.0
    retrieved = set(_dedupe(retrieved_doc_ids[:k]))
    return len(expected & retrieved) / len(expected)


def reciprocal_rank(expected_doc_ids: Sequence[str], retrieved_doc_ids: Sequence[str]) -> float:
    expected = set(_dedupe(expected_doc_ids))
    if not expected:
        return 0.0
    for rank, doc_id in enumerate(_dedupe(retrieved_doc_ids), start=1):
        if doc_id in expected:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(expected_doc_ids: Sequence[str], retrieved_doc_ids: Sequence[str], *, k: int) -> float:
    if k < 1:
        raise ValueError("k must be positive")
    expected = set(_dedupe(expected_doc_ids))
    if not expected:
        return 0.0
    deduped_retrieved = _dedupe(retrieved_doc_ids[:k])
    dcg = sum(1.0 / math.log2(rank + 1) for rank, doc_id in enumerate(deduped_retrieved, start=1) if doc_id in expected)
    ideal_hits = min(len(expected), k)
    ideal_dcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / ideal_dcg if ideal_dcg else 0.0


def score_observations(
    observations: Iterable[RetrievalObservation],
    *,
    ks: Sequence[int] = (5, 10),
) -> tuple[RetrievalObservationScore, ...]:
    normalized_ks = _validate_ks(ks)
    scores: list[RetrievalObservationScore] = []
    for observation in observations:
        if not observation.expected_doc_ids:
            continue
        scores.append(
            RetrievalObservationScore(
                record_id=observation.record_id,
                expected_doc_ids=observation.expected_doc_ids,
                retrieved_doc_ids=observation.retrieved_doc_ids,
                reciprocal_rank=reciprocal_rank(observation.expected_doc_ids, observation.retrieved_doc_ids),
                recall_by_k={
                    k: recall_at_k(observation.expected_doc_ids, observation.retrieved_doc_ids, k=k)
                    for k in normalized_ks
                },
                ndcg_by_k={
                    k: ndcg_at_k(observation.expected_doc_ids, observation.retrieved_doc_ids, k=k)
                    for k in normalized_ks
                },
            )
        )
    return tuple(scores)


def summarize_retrieval_metrics(
    observations: Iterable[RetrievalObservation],
    *,
    ks: Sequence[int] = (5, 10),
    include_ndcg: bool = False,
) -> tuple[MetricSummary, ...]:
    normalized_ks = _validate_ks(ks)
    scores = score_observations(observations, ks=normalized_ks)
    count = len(scores)
    notes = f"{count} answered retrieval records"
    metrics: list[MetricSummary] = [
        MetricSummary(
            name=f"recall@{k}",
            value=_mean(score.recall_by_k[k] for score in scores),
            notes=notes,
        )
        for k in normalized_ks
    ]
    metrics.append(
        MetricSummary(
            name="mrr",
            value=_mean(score.reciprocal_rank for score in scores),
            notes=notes,
        )
    )
    if include_ndcg:
        metrics.extend(
            MetricSummary(
                name=f"ndcg@{k}",
                value=_mean(score.ndcg_by_k[k] for score in scores),
                notes=notes,
            )
            for k in normalized_ks
        )
    return tuple(metrics)


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        doc_id = value.strip()
        if doc_id and doc_id not in result:
            result.append(doc_id)
    return tuple(result)


def _validate_ks(ks: Sequence[int]) -> tuple[int, ...]:
    result = tuple(dict.fromkeys(int(k) for k in ks))
    if not result:
        raise ValueError("at least one k value is required")
    if any(k < 1 for k in result):
        raise ValueError("k values must be positive")
    return result


def _mean(values: Iterable[float]) -> float:
    collected = tuple(values)
    if not collected:
        return 0.0
    return sum(collected) / len(collected)
