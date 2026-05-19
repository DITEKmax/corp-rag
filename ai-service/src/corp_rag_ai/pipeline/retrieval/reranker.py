from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from corp_rag_ai.domain.retrieval import RetrievalCandidate

RERANKER_DISABLED_WARNING = "reranker_disabled"
RERANKER_UNAVAILABLE_WARNING = "reranker_unavailable"


class _RerankerModel(Protocol):
    def compute_score(self, pairs: Sequence[tuple[str, str]], *, normalize: bool) -> Sequence[float]:
        ...


RerankerFactory = Callable[[str], _RerankerModel]


@dataclass(frozen=True, slots=True)
class RerankOutcome:
    candidates: tuple[RetrievalCandidate, ...]
    reranker_used: bool
    warnings: tuple[str, ...] = ()


class LocalReranker:
    def __init__(
        self,
        *,
        enabled: bool = True,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        model_factory: RerankerFactory | None = None,
        concurrency: int = 1,
    ) -> None:
        if concurrency < 1:
            raise ValueError("reranker concurrency must be positive")
        self._enabled = enabled
        self._model_name = model_name
        self._model_factory = model_factory or _load_flag_reranker
        self._semaphore = asyncio.Semaphore(concurrency)
        self._model: _RerankerModel | None = None

    async def rerank(
        self,
        *,
        query: str,
        candidates: tuple[RetrievalCandidate, ...],
        top_n: int,
    ) -> RerankOutcome:
        if top_n < 1:
            raise ValueError("top_n must be positive")
        if not candidates:
            return RerankOutcome(candidates=(), reranker_used=False)
        if not self._enabled:
            return RerankOutcome(
                candidates=candidates[:top_n],
                reranker_used=False,
                warnings=(RERANKER_DISABLED_WARNING,),
            )
        try:
            async with self._semaphore:
                model = await asyncio.to_thread(self._get_model)
                pairs = [(query, candidate.content) for candidate in candidates]
                scores = await asyncio.to_thread(model.compute_score, pairs, normalize=True)
        except Exception:
            return RerankOutcome(
                candidates=candidates[:top_n],
                reranker_used=False,
                warnings=(RERANKER_UNAVAILABLE_WARNING,),
            )
        reranked = tuple(
            sorted(
                (replace(candidate, score=_clamp_score(score)) for candidate, score in zip(candidates, scores, strict=True)),
                key=lambda candidate: candidate.score,
                reverse=True,
            )
        )[:top_n]
        return RerankOutcome(candidates=reranked, reranker_used=True)

    def _get_model(self) -> _RerankerModel:
        if self._model is None:
            self._model = self._model_factory(self._model_name)
        return self._model


def _load_flag_reranker(model_name: str) -> _RerankerModel:
    from FlagEmbedding import FlagReranker

    return FlagReranker(model_name)


def _clamp_score(score: float) -> float:
    return min(1.0, max(0.0, float(score)))
