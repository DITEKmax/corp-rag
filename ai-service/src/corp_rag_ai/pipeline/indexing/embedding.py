from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from corp_rag_ai.domain.exceptions import INDEXING_PIPELINE_ERROR, IndexingStage, StageFailure, stage_failure

DEFAULT_BGE_M3_MODEL = "BAAI/bge-m3"
DEFAULT_EMBEDDING_BATCH_SIZE = 32
BGE_M3_DENSE_DIMENSION = 1024
_SMOKE_TEXT = "corporate policy"


class _BgeM3Model(Protocol):
    def encode(
        self,
        sentences: Sequence[str],
        *,
        batch_size: int,
        return_dense: bool,
        return_sparse: bool,
        return_colbert_vecs: bool,
    ) -> Mapping[str, Any]:
        ...


ModelFactory = Callable[[str, bool], _BgeM3Model]


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    dense: tuple[float, ...]
    sparse: dict[int, float]


class EmbeddingOutputError(ValueError):
    """Raised when local bge-m3 output does not satisfy the locked contract."""


class LocalBgeM3Embedder:
    """Lazy local bge-m3 dense+sparse embedding adapter."""

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_BGE_M3_MODEL,
        batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
        dense_dimension: int = BGE_M3_DENSE_DIMENSION,
        model_factory: ModelFactory | None = None,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self._model_name = model_name
        self._batch_size = batch_size
        self._dense_dimension = dense_dimension
        self._model_factory = model_factory or _load_flag_embedding_model
        self._model: _BgeM3Model | None = None

    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingVector, ...]:
        if not texts:
            return ()
        model = self._get_model()
        vectors: list[EmbeddingVector] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            try:
                output = model.encode(
                    batch,
                    batch_size=self._batch_size,
                    return_dense=True,
                    return_sparse=True,
                    return_colbert_vecs=False,
                )
                vectors.extend(_parse_embedding_output(output, expected_count=len(batch), dense_dimension=self._dense_dimension))
            except StageFailure:
                raise
            except Exception as exc:  # pragma: no cover - exact dependency exceptions vary
                raise _embedding_failure(exc) from exc
        return tuple(vectors)

    def preflight(self) -> EmbeddingVector:
        return self.embed_texts([_SMOKE_TEXT])[0]

    def _get_model(self) -> _BgeM3Model:
        if self._model is None:
            self._model = self._load_with_fp16_fallback()
        return self._model

    def _load_with_fp16_fallback(self) -> _BgeM3Model:
        first_error: Exception | None = None
        for use_fp16 in (True, False):
            try:
                model = self._model_factory(self._model_name, use_fp16)
                output = model.encode(
                    [_SMOKE_TEXT],
                    batch_size=1,
                    return_dense=True,
                    return_sparse=True,
                    return_colbert_vecs=False,
                )
                _parse_embedding_output(output, expected_count=1, dense_dimension=self._dense_dimension)
                return model
            except Exception as exc:  # pragma: no cover - exercised through fake model tests
                if first_error is None:
                    first_error = exc
                if not use_fp16:
                    raise _embedding_failure(first_error or exc) from exc
        raise AssertionError("unreachable")


def should_run_live_smoke(
    *,
    enabled: bool,
    model_name: str = DEFAULT_BGE_M3_MODEL,
    cache_dir: str | Path | None = None,
) -> bool:
    return enabled or model_cache_available(model_name=model_name, cache_dir=cache_dir)


def model_cache_available(*, model_name: str = DEFAULT_BGE_M3_MODEL, cache_dir: str | Path | None = None) -> bool:
    cache_root = _resolve_huggingface_cache(cache_dir)
    model_cache_name = "models--" + model_name.replace("/", "--")
    model_root = cache_root / "hub" / model_cache_name
    if not model_root.exists():
        model_root = cache_root / model_cache_name
    snapshots = model_root / "snapshots"
    return any(snapshots.iterdir()) if snapshots.exists() else False


def _load_flag_embedding_model(model_name: str, use_fp16: bool) -> _BgeM3Model:
    from FlagEmbedding import BGEM3FlagModel

    return BGEM3FlagModel(model_name, use_fp16=use_fp16)


def _parse_embedding_output(
    output: Mapping[str, Any],
    *,
    expected_count: int,
    dense_dimension: int,
) -> tuple[EmbeddingVector, ...]:
    dense_vectors = _to_python_list(output.get("dense_vecs"))
    sparse_vectors = output.get("lexical_weights")
    if sparse_vectors is None:
        sparse_vectors = output.get("sparse_vecs")
    sparse_list = _to_python_list(sparse_vectors)

    if len(dense_vectors) != expected_count:
        raise EmbeddingOutputError("dense vector count mismatch")
    if len(sparse_list) != expected_count:
        raise EmbeddingOutputError("sparse vector count mismatch")

    vectors: list[EmbeddingVector] = []
    for dense, sparse in zip(dense_vectors, sparse_list, strict=True):
        dense_tuple = tuple(float(value) for value in _to_python_list(dense))
        if len(dense_tuple) != dense_dimension:
            raise EmbeddingOutputError(f"dense vector dimension must be {dense_dimension}")
        sparse_dict = _normalize_sparse_weights(sparse)
        if not sparse_dict:
            raise EmbeddingOutputError("sparse lexical weights must not be empty")
        vectors.append(EmbeddingVector(dense=dense_tuple, sparse=sparse_dict))
    return tuple(vectors)


def _normalize_sparse_weights(value: Any) -> dict[int, float]:
    if not isinstance(value, Mapping):
        raise EmbeddingOutputError("sparse lexical weights must be a mapping")
    sparse: dict[int, float] = {}
    for raw_index, raw_weight in value.items():
        weight = float(raw_weight)
        if weight == 0.0:
            continue
        sparse[int(raw_index)] = weight
    return sparse


def _to_python_list(value: Any) -> Any:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def _embedding_failure(exc: Exception) -> StageFailure:
    return stage_failure(
        stage=IndexingStage.EMBEDDING,
        error_code=INDEXING_PIPELINE_ERROR,
        retryable=False,
        exception_class=exc,
    )


def _resolve_huggingface_cache(cache_dir: str | Path | None) -> Path:
    if cache_dir is not None:
        return Path(cache_dir).expanduser()
    if "HF_HOME" in os.environ:
        return Path(os.environ["HF_HOME"]).expanduser()
    if "TRANSFORMERS_CACHE" in os.environ:
        return Path(os.environ["TRANSFORMERS_CACHE"]).expanduser()
    return Path.home() / ".cache" / "huggingface"
