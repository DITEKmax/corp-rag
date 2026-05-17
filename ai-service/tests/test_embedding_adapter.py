from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from corp_rag_ai.domain.exceptions import INDEXING_PIPELINE_ERROR, IndexingStage, StageFailure
from corp_rag_ai.pipeline.indexing.embedding import (
    BGE_M3_DENSE_DIMENSION,
    LocalBgeM3Embedder,
    model_cache_available,
    should_run_live_smoke,
)


class _FakeBgeM3Model:
    def __init__(self, output: dict[str, Any] | Exception) -> None:
        self.output = output
        self.calls: list[dict[str, object]] = []

    def encode(
        self,
        sentences: Sequence[str],
        *,
        batch_size: int,
        return_dense: bool,
        return_sparse: bool,
        return_colbert_vecs: bool,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "sentences": list(sentences),
                "batch_size": batch_size,
                "return_dense": return_dense,
                "return_sparse": return_sparse,
                "return_colbert_vecs": return_colbert_vecs,
            }
        )
        if isinstance(self.output, Exception):
            raise self.output
        return _resize_output(self.output, len(sentences))


def test_embedder_batches_dense_sparse_local_model_calls_without_downloading_weights() -> None:
    model = _FakeBgeM3Model(_embedding_output(count=1))

    embedder = LocalBgeM3Embedder(batch_size=32, model_factory=lambda _name, _use_fp16: model)
    vectors = embedder.embed_texts([f"text-{index}" for index in range(33)])

    assert len(vectors) == 33
    assert len(vectors[0].dense) == BGE_M3_DENSE_DIMENSION
    assert vectors[0].sparse == {11: 0.25, 42: 0.75}
    assert [len(call["sentences"]) for call in model.calls] == [1, 32, 1]
    assert all(call["return_dense"] is True for call in model.calls)
    assert all(call["return_sparse"] is True for call in model.calls)
    assert all(call["return_colbert_vecs"] is False for call in model.calls)


def test_embedder_falls_back_to_cpu_safe_fp32_when_fp16_smoke_fails() -> None:
    calls: list[bool] = []
    fp16_model = _FakeBgeM3Model(RuntimeError("fp16 unsupported"))
    fp32_model = _FakeBgeM3Model(_embedding_output(count=1))

    def factory(_name: str, use_fp16: bool) -> _FakeBgeM3Model:
        calls.append(use_fp16)
        return fp16_model if use_fp16 else fp32_model

    embedder = LocalBgeM3Embedder(model_factory=factory)

    assert len(embedder.preflight().dense) == BGE_M3_DENSE_DIMENSION
    assert calls == [True, False]


def test_missing_sparse_weights_map_to_non_retryable_embedding_stage_failure() -> None:
    embedder = LocalBgeM3Embedder(
        model_factory=lambda _name, _use_fp16: _FakeBgeM3Model(
            {"dense_vecs": [[0.1] * BGE_M3_DENSE_DIMENSION], "lexical_weights": [{}]}
        )
    )

    with pytest.raises(StageFailure) as exc_info:
        embedder.preflight()

    failure = exc_info.value
    assert failure.stage == IndexingStage.EMBEDDING
    assert failure.error_code == INDEXING_PIPELINE_ERROR
    assert failure.retryable is False


def test_live_smoke_is_skipped_unless_enabled_or_model_cache_exists(tmp_path) -> None:
    missing_cache = tmp_path / "missing"
    assert should_run_live_smoke(enabled=False, cache_dir=missing_cache) is False
    assert should_run_live_smoke(enabled=True, cache_dir=missing_cache) is True

    snapshots = tmp_path / "hub" / "models--BAAI--bge-m3" / "snapshots" / "local"
    snapshots.mkdir(parents=True)

    assert model_cache_available(cache_dir=tmp_path) is True
    assert should_run_live_smoke(enabled=False, cache_dir=tmp_path) is True


def _embedding_output(*, count: int) -> dict[str, Any]:
    return {
        "dense_vecs": [[0.1] * BGE_M3_DENSE_DIMENSION for _ in range(count)],
        "lexical_weights": [{"11": 0.25, "42": 0.75} for _ in range(count)],
    }


def _resize_output(output: dict[str, Any], count: int) -> dict[str, Any]:
    dense = output["dense_vecs"]
    sparse = output["lexical_weights"]
    if len(dense) == count and len(sparse) == count:
        return output
    return {
        "dense_vecs": [dense[0] for _ in range(count)],
        "lexical_weights": [sparse[0] for _ in range(count)],
    }
