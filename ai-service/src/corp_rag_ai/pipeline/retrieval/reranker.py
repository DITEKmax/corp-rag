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
        timeout_seconds: float = 25.0,
        load_timeout_seconds: float = 28.0,
    ) -> None:
        if concurrency < 1:
            raise ValueError("reranker concurrency must be positive")
        if timeout_seconds <= 0:
            raise ValueError("reranker timeout must be positive")
        if load_timeout_seconds <= 0:
            raise ValueError("reranker load timeout must be positive")
        self._enabled = enabled
        self._model_name = model_name
        self._model_factory = model_factory or _load_flag_reranker
        self._semaphore = asyncio.Semaphore(concurrency)
        self._model: _RerankerModel | None = None
        self._timeout_seconds = timeout_seconds
        self._load_timeout_seconds = load_timeout_seconds

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
                loop = asyncio.get_running_loop()
                deadline = loop.time() + max(self._timeout_seconds, self._load_timeout_seconds)
                model = await asyncio.wait_for(
                    asyncio.to_thread(self._get_model),
                    timeout=min(self._load_timeout_seconds, _remaining_seconds(deadline, loop)),
                )
                pairs = [(query, candidate.content) for candidate in candidates]
                scores = await asyncio.wait_for(
                    asyncio.to_thread(model.compute_score, pairs, normalize=True),
                    timeout=min(self._timeout_seconds, _remaining_seconds(deadline, loop)),
                )
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

    async def prewarm(self) -> bool:
        if not self._enabled:
            return False
        async with self._semaphore:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + max(self._timeout_seconds, self._load_timeout_seconds)
            model = await asyncio.wait_for(
                asyncio.to_thread(self._get_model),
                timeout=min(self._load_timeout_seconds, _remaining_seconds(deadline, loop)),
            )
            await asyncio.wait_for(
                asyncio.to_thread(
                    model.compute_score,
                    [("corporate policy", "Employees follow corporate policy.")],
                    normalize=True,
                ),
                timeout=min(self._timeout_seconds, _remaining_seconds(deadline, loop)),
            )
        return True

    def _get_model(self) -> _RerankerModel:
        if self._model is None:
            self._model = self._model_factory(self._model_name)
        return self._model


def _load_flag_reranker(model_name: str) -> _RerankerModel:
    from FlagEmbedding import FlagReranker

    return FlagReranker(model_name)


def _clamp_score(score: float) -> float:
    return min(1.0, max(0.0, float(score)))


def _remaining_seconds(deadline: float, loop: asyncio.AbstractEventLoop) -> float:
    return max(0.001, deadline - loop.time())
