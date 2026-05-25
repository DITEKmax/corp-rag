from __future__ import annotations

import os
import time
from uuid import UUID

import pytest
from pydantic import ValidationError

from corp_rag_ai.config import Settings
from corp_rag_ai.domain.retrieval import RetrievalCandidate, RetrieverType
from corp_rag_ai.pipeline.indexing.embedding import model_cache_available
from corp_rag_ai.pipeline.retrieval.reranker import (
    RERANKER_DISABLED_WARNING,
    RERANKER_UNAVAILABLE_WARNING,
    LocalReranker,
)


DOCUMENT_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
PARENT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


async def test_reranker_uses_normalized_scores_for_final_ranking() -> None:
    model = _FakeReranker([0.2, 0.95])
    reranker = LocalReranker(model_factory=lambda _name: model)

    outcome = await reranker.rerank(
        query="vacation policy",
        candidates=(_candidate("first", 0.8), _candidate("second", 0.4)),
        top_n=2,
    )

    assert outcome.reranker_used is True
    assert [candidate.content for candidate in outcome.candidates] == ["second", "first"]
    assert [candidate.score for candidate in outcome.candidates] == [0.95, 0.2]
    assert model.calls[0]["normalize"] is True
    assert all(0.0 <= candidate.score <= 1.0 for candidate in outcome.candidates)


async def test_disabled_reranker_keeps_raw_order_and_sets_metadata_warning() -> None:
    reranker = LocalReranker(enabled=False, model_factory=lambda _name: _FakeReranker([1.0]))

    outcome = await reranker.rerank(query="q", candidates=(_candidate("first", 0.8),), top_n=1)

    assert outcome.reranker_used is False
    assert outcome.warnings == (RERANKER_DISABLED_WARNING,)
    assert outcome.candidates[0].content == "first"


async def test_unavailable_reranker_keeps_candidates_without_reporting_reranker_scores() -> None:
    reranker = LocalReranker(model_factory=lambda _name: _FailingReranker())

    outcome = await reranker.rerank(
        query="q",
        candidates=(_candidate("first", 0.8), _candidate("second", 0.7)),
        top_n=1,
    )

    assert outcome.reranker_used is False
    assert outcome.warnings == (RERANKER_UNAVAILABLE_WARNING,)
    assert [candidate.content for candidate in outcome.candidates] == ["first"]
    assert outcome.candidates[0].score == 0.8


async def test_reranker_load_timeout_soft_degrades_to_raw_candidates() -> None:
    reranker = LocalReranker(
        model_factory=lambda _name: _sleep_then_model(0.05),
        timeout_seconds=0.02,
        load_timeout_seconds=0.01,
    )

    outcome = await reranker.rerank(
        query="q",
        candidates=(_candidate("first", 0.8), _candidate("second", 0.7)),
        top_n=1,
    )

    assert outcome.reranker_used is False
    assert outcome.warnings == (RERANKER_UNAVAILABLE_WARNING,)
    assert [candidate.content for candidate in outcome.candidates] == ["first"]
    assert outcome.candidates[0].score == 0.8


async def test_reranker_score_timeout_soft_degrades_to_raw_candidates() -> None:
    reranker = LocalReranker(
        model_factory=lambda _name: _SlowScoringReranker(delay_seconds=0.05),
        timeout_seconds=0.01,
        load_timeout_seconds=0.02,
    )

    outcome = await reranker.rerank(
        query="q",
        candidates=(_candidate("first", 0.8), _candidate("second", 0.7)),
        top_n=2,
    )

    assert outcome.reranker_used is False
    assert outcome.warnings == (RERANKER_UNAVAILABLE_WARNING,)
    assert [candidate.content for candidate in outcome.candidates] == ["first", "second"]
    assert [candidate.score for candidate in outcome.candidates] == [0.8, 0.7]


async def test_warm_working_reranker_is_not_falsely_degraded_by_timeout() -> None:
    model = _FakeReranker([1.0])
    factory_calls = 0

    def factory(_name: str) -> _FakeReranker:
        nonlocal factory_calls
        factory_calls += 1
        return model

    reranker = LocalReranker(model_factory=factory, timeout_seconds=0.5, load_timeout_seconds=0.5)
    await reranker.rerank(query="q", candidates=(_candidate("warmup", 0.5),), top_n=1)

    model.scores = [0.2, 0.95]
    outcome = await reranker.rerank(
        query="q",
        candidates=(_candidate("first", 0.8), _candidate("second", 0.7)),
        top_n=2,
    )

    assert factory_calls == 1
    assert outcome.reranker_used is True
    assert RERANKER_UNAVAILABLE_WARNING not in outcome.warnings
    assert [candidate.content for candidate in outcome.candidates] == ["second", "first"]
    assert [candidate.score for candidate in outcome.candidates] == [0.95, 0.2]


def test_reranker_step_budget_must_stay_below_query_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_QUERY_TIMEOUT_SECONDS", "25")
    monkeypatch.setenv("AI_RERANKER_TIMEOUT_SECONDS", "25")
    monkeypatch.setenv("AI_RERANKER_LOAD_TIMEOUT_SECONDS", "20")

    with pytest.raises(ValidationError, match="strictly less than AI_QUERY_TIMEOUT_SECONDS"):
        Settings(_env_file=None)

    monkeypatch.setenv("AI_QUERY_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("AI_RERANKER_TIMEOUT_SECONDS", "25")
    monkeypatch.setenv("AI_RERANKER_LOAD_TIMEOUT_SECONDS", "30")

    with pytest.raises(ValidationError, match="strictly less than AI_QUERY_TIMEOUT_SECONDS"):
        Settings(_env_file=None)


async def test_reranker_semaphore_serializes_concurrent_scoring() -> None:
    model = _BlockingReranker()
    reranker = LocalReranker(model_factory=lambda _name: model, concurrency=1)

    await asyncio_gather(
        reranker.rerank(query="q1", candidates=(_candidate("first", 0.8),), top_n=1),
        reranker.rerank(query="q2", candidates=(_candidate("second", 0.7),), top_n=1),
    )

    assert model.max_active == 1
    assert model.calls == 2


@pytest.mark.integration
def test_live_flag_reranker_scores_query_passage_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    model_name = os.environ.get("AI_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
    cache_dir = os.environ.get("AI_RERANKER_MODEL_CACHE_DIR") or os.environ.get("AI_EMBEDDING_MODEL_CACHE_DIR")
    if cache_dir:
        monkeypatch.setenv("HF_HOME", cache_dir)

    live_download_enabled = os.environ.get("AI_RERANKER_LIVE_SMOKE_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not live_download_enabled and not model_cache_available(model_name=model_name, cache_dir=cache_dir):
        pytest.skip("AI_RERANKER_LIVE_SMOKE_ENABLED=true or a cached reranker model is required")

    from FlagEmbedding import FlagReranker

    scores = FlagReranker(model_name).compute_score(
        [("vacation policy", "Employees request annual vacation after manager approval.")],
        normalize=True,
    )

    score = _first_score(scores)
    assert 0.0 <= score <= 1.0


class _FakeReranker:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.calls: list[dict[str, object]] = []

    def compute_score(self, pairs, *, normalize: bool):
        self.calls.append({"pairs": pairs, "normalize": normalize})
        return self.scores


class _FailingReranker:
    def compute_score(self, _pairs, *, normalize: bool):
        raise RuntimeError("reranker unavailable")


class _SlowScoringReranker:
    def __init__(self, *, delay_seconds: float) -> None:
        self._delay_seconds = delay_seconds

    def compute_score(self, pairs, *, normalize: bool):
        time.sleep(self._delay_seconds)
        return [0.5 for _ in pairs]


class _BlockingReranker:
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.calls = 0

    def compute_score(self, pairs, *, normalize: bool):
        self.calls += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        time.sleep(0.03)
        self.active -= 1
        return [0.5 for _ in pairs]


async def asyncio_gather(*awaitables) -> None:
    import asyncio

    await asyncio.gather(*awaitables)


def _first_score(scores) -> float:
    if isinstance(scores, (int, float)):
        return float(scores)
    if hasattr(scores, "tolist"):
        scores = scores.tolist()
    if isinstance(scores, list | tuple):
        return float(scores[0])
    return float(scores)


def _sleep_then_model(delay_seconds: float) -> _FakeReranker:
    time.sleep(delay_seconds)
    return _FakeReranker([1.0])


def _candidate(content: str, score: float) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=UUID(int=abs(hash(content)) % (1 << 128)),
        parent_chunk_id=PARENT_ID,
        document_id=DOCUMENT_ID,
        document_title="Policy",
        section_path=("HR",),
        content=content,
        score=score,
        access_level="INTERNAL",
        retriever=RetrieverType.HYBRID,
    )
