from __future__ import annotations

import argparse
import asyncio
import copy
import json
import math
import os
import sys
from collections import Counter
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from corp_rag_ai.pipeline.indexing.embedding import (
    DEFAULT_BGE_M3_MODEL,
    DEFAULT_EMBEDDING_BATCH_SIZE,
    LocalBgeM3Embedder,
)
from eval.io import load_corpus_metadata, load_golden_records, load_manifest
from eval.query_client import (
    ActualOutcome,
    DEFAULT_AI_DB_URL,
    DEFAULT_EVAL_TOP_K,
    DEFAULT_QDRANT_URL,
    ProductionQueryClient,
    QueryClientConfig,
    QuerySampleResult,
    access_filter_from_manifest,
)
from eval.reporting import write_report
from eval.schema import EvaluationReport, ExpectedOutcome, MetricSummary, RunnerConfig
from eval.validate_golden import (
    DEFAULT_CORPUS_DIR,
    DEFAULT_GOLDEN_PATH,
    DEFAULT_MANIFEST_PATH,
    DEFAULT_METADATA_PATH,
    GoldenValidationSummary,
    validate_golden,
)


EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_REPORTS_DIR = EVAL_DIR / "reports"
DEFAULT_REPORT_SLUG = "ragas_ru"
DEFAULT_SERVICE_BASE_URL = "http://localhost:8000"
DEFAULT_JUDGE_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_JUDGE_MODEL_ID = "deepseek/deepseek-chat"
DEFAULT_EMBEDDING_MODEL_ID = DEFAULT_BGE_M3_MODEL
RAGAS_METRIC_NAMES = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
RAGAS_THRESHOLDS = {
    "faithfulness": 0.75,
    "answer_relevancy": 0.75,
    "context_precision": 0.60,
    "context_recall": 0.60,
}


class RagasRunnerError(RuntimeError):
    pass


class QueryClientFactory(Protocol):
    def __call__(self, config: QueryClientConfig) -> Any: ...


@dataclass(frozen=True, slots=True)
class RagasRunnerConfig:
    golden_path: Path = DEFAULT_GOLDEN_PATH
    metadata_path: Path = DEFAULT_METADATA_PATH
    corpus_dir: Path = DEFAULT_CORPUS_DIR
    manifest_path: Path = DEFAULT_MANIFEST_PATH
    reports_dir: Path = DEFAULT_REPORTS_DIR
    report_slug: str = DEFAULT_REPORT_SLUG
    service_base_url: str = DEFAULT_SERVICE_BASE_URL
    top_k: int = DEFAULT_EVAL_TOP_K
    reranker_enabled: bool = True
    timeout_seconds: float = 180.0
    parent_context_enabled: bool = True
    qdrant_url: str = DEFAULT_QDRANT_URL
    ai_db_url: str = DEFAULT_AI_DB_URL
    judge_model_id: str = DEFAULT_JUDGE_MODEL_ID
    judge_base_url: str | None = None
    judge_api_key: str | None = None
    embedding_model_id: str | None = DEFAULT_EMBEDDING_MODEL_ID
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    concurrency: int = 1
    show_progress: bool = False
    score_report_path: Path | None = None
    ragas_max_retries: int = 1
    ragas_max_wait: int = 5

    def __post_init__(self) -> None:
        if self.concurrency != 1:
            raise ValueError("RAGAS production runner is pinned to concurrency=1")


@dataclass(frozen=True, slots=True)
class RagasRow:
    record_id: str
    user_input: str
    response: str
    retrieved_contexts: tuple[str, ...]
    reference: str

    def to_dataset_row(self) -> dict[str, Any]:
        return {
            "user_input": self.user_input,
            "response": self.response,
            "retrieved_contexts": list(self.retrieved_contexts),
            "reference": self.reference,
        }


@dataclass(frozen=True, slots=True)
class RagasScoringResult:
    aggregate_scores: dict[str, float | str]
    per_record_scores: dict[str, dict[str, float | str | None]] = field(default_factory=dict)
    per_record_errors: dict[str, dict[str, str]] = field(default_factory=dict)
    skipped_metrics: dict[str, str] = field(default_factory=dict)
    external_judge_used: bool = False
    token_usage: Any | None = None
    total_cost: float | None = None


RagasEvaluator = Callable[[tuple[RagasRow, ...], RagasRunnerConfig], RagasScoringResult]


@dataclass(frozen=True, slots=True)
class RagasRunOutput:
    report: EvaluationReport
    markdown_path: Path
    json_path: Path
    csv_path: Path | None
    validation_summary: GoldenValidationSummary


class LocalBgeM3LangchainEmbeddings:
    """LangChain-compatible dense embedding wrapper backed by the service bge-m3 adapter."""

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_BGE_M3_MODEL,
        batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
    ) -> None:
        self.model_name = model_name
        self._embedder = LocalBgeM3Embedder(model_name=model_name, batch_size=batch_size)

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [list(vector.dense) for vector in self._embedder.embed_texts(texts)]

    async def aembed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self.embed_query, text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self.embed_documents, texts)


async def run_ragas_evaluation(
    config: RagasRunnerConfig,
    *,
    query_client_factory: QueryClientFactory | None = None,
    evaluator: RagasEvaluator | None = None,
) -> RagasRunOutput:
    validation_summary = validate_golden(
        config.golden_path,
        metadata_path=config.metadata_path,
        corpus_dir=config.corpus_dir,
        manifest_path=config.manifest_path,
    )
    manifest = load_manifest(config.manifest_path)
    metadata = load_corpus_metadata(config.metadata_path)
    records = load_golden_records(config.golden_path)
    query_results = await collect_query_results(
        records,
        manifest=manifest,
        config=config,
        query_client_factory=query_client_factory,
    )
    write_query_phase_report(
        query_results,
        validation_summary=validation_summary,
        corpus_version=metadata.corpus_version,
        corpus_hash=metadata.corpus_hash,
        config=config,
    )
    rows = build_ragas_rows(query_results)
    scoring = evaluator(rows, config) if evaluator is not None else evaluate_ragas_rows(rows, config)
    report = build_evaluation_report(
        query_results,
        scoring=scoring,
        validation_summary=validation_summary,
        corpus_version=metadata.corpus_version,
        corpus_hash=metadata.corpus_hash,
        config=config,
    )
    artifact = write_report(report, reports_dir=config.reports_dir, slug=config.report_slug, write_csv=True)
    return RagasRunOutput(
        report=report,
        markdown_path=artifact.markdown_path,
        json_path=artifact.json_path,
        csv_path=artifact.csv_path,
        validation_summary=validation_summary,
    )


async def run_ragas_scoring_from_report(
    config: RagasRunnerConfig,
    source_report_path: Path,
    *,
    evaluator: RagasEvaluator | None = None,
) -> RagasRunOutput:
    validation_summary = validate_golden(
        config.golden_path,
        metadata_path=config.metadata_path,
        corpus_dir=config.corpus_dir,
        manifest_path=config.manifest_path,
    )
    metadata = load_corpus_metadata(config.metadata_path)
    records = load_golden_records(config.golden_path)
    source_report = _load_score_source_report(source_report_path)
    query_results = query_results_from_report(source_report, records)
    rows = build_ragas_rows(query_results)
    scoring = evaluator(rows, config) if evaluator is not None else evaluate_ragas_rows(rows, config)
    report = build_evaluation_report(
        query_results,
        scoring=scoring,
        validation_summary=validation_summary,
        corpus_version=metadata.corpus_version,
        corpus_hash=metadata.corpus_hash,
        config=config,
    )
    report.runner_config.options["score_source_report"] = str(source_report_path)
    artifact = write_report(report, reports_dir=config.reports_dir, slug=config.report_slug, write_csv=True)
    return RagasRunOutput(
        report=report,
        markdown_path=artifact.markdown_path,
        json_path=artifact.json_path,
        csv_path=artifact.csv_path,
        validation_summary=validation_summary,
    )


async def collect_query_results(
    records: Iterable,
    *,
    manifest,
    config: RagasRunnerConfig,
    query_client_factory: QueryClientFactory | None = None,
) -> tuple[QuerySampleResult, ...]:
    access_filter = access_filter_from_manifest(manifest)
    client_config = QueryClientConfig(
        base_url=config.service_base_url,
        timeout_seconds=config.timeout_seconds,
        top_k=config.top_k,
        reranker_enabled=config.reranker_enabled,
        access_filter=access_filter,
        parent_context_enabled=config.parent_context_enabled,
        qdrant_url=config.qdrant_url,
        ai_db_url=config.ai_db_url,
    )
    factory = query_client_factory or ProductionQueryClient
    results: list[QuerySampleResult] = []
    async with factory(client_config) as client:
        for record in records:
            # Keep production queries strictly sequential so each /v1/query
            # releases reranker/model resources before the next request starts.
            results.append(await client.query_golden(record))
    return tuple(results)


def write_query_phase_report(
    results: tuple[QuerySampleResult, ...],
    *,
    validation_summary: GoldenValidationSummary,
    corpus_version: str,
    corpus_hash: str,
    config: RagasRunnerConfig,
) -> None:
    scoring = RagasScoringResult(
        aggregate_scores={name: "skipped" for name in RAGAS_METRIC_NAMES},
        skipped_metrics={
            name: "RAGAS scoring pending; query phase persisted before scoring."
            for name in RAGAS_METRIC_NAMES
        },
        external_judge_used=False,
    )
    report = build_evaluation_report(
        results,
        scoring=scoring,
        validation_summary=validation_summary,
        corpus_version=corpus_version,
        corpus_hash=corpus_hash,
        config=config,
    )
    report.runner_config.options["query_phase_cache"] = True
    report.runner_config.options["scoring_status"] = "pending"
    write_report(report, reports_dir=config.reports_dir, slug=config.report_slug, write_csv=False)


def query_results_from_report(
    report: EvaluationReport,
    records: Iterable,
) -> tuple[QuerySampleResult, ...]:
    records_by_id = {record.id: record for record in records}
    results: list[QuerySampleResult] = []
    for detail in report.details:
        record_id = str(detail.get("id") or detail.get("question_id") or "")
        record = records_by_id.get(record_id)
        if record is None:
            raise RagasRunnerError(f"source report detail {record_id!r} is not present in the golden set")
        actual_outcome = ActualOutcome(
            str(detail.get("actual_outcome") or detail.get("outcome") or ActualOutcome.REFUSED_NO_EVIDENCE.value)
        )
        answered = bool(detail.get("answered", actual_outcome is ActualOutcome.ANSWERED))
        results.append(
            QuerySampleResult(
                record_id=record.id,
                question=str(detail.get("question") or record.question),
                reference_answer=record.reference_answer,
                expected_doc_ids=tuple(str(item) for item in (detail.get("expected_doc_ids") or record.expected_doc_ids)),
                expected_outcome=str(detail.get("expected_outcome") or record.expected_outcome.value),
                actual_outcome=actual_outcome,
                answered=answered,
                answer=str(detail.get("answer") or ""),
                citations=(),
                retrieved_contexts=_string_tuple(detail.get("retrieved_contexts")),
                citation_document_ids=_string_tuple(detail.get("citation_document_ids")),
                route=str(detail.get("route") or ""),
                route_source=str(detail["route_source"]) if detail.get("route_source") else None,
                route_reason=str(detail["route_reason"]) if detail.get("route_reason") else None,
                retrievers_attempted=_string_tuple(detail.get("retrievers_attempted")),
                retrievers_used=_string_tuple(detail.get("retrievers_used")),
                degradation_warnings=_string_tuple(detail.get("degradation_warnings")),
                reranker_used=bool(detail.get("reranker_used", False)),
                model_id=str(detail.get("model_id") or report.model_id),
                confidence=float(detail.get("confidence") or 0.0),
                service_latency_ms=int(detail.get("service_latency_ms") or 0),
                client_latency_ms=int(detail.get("client_latency_ms") or 0),
                trace_id=str(detail["trace_id"]) if detail.get("trace_id") else None,
                guard_verdict=detail.get("guard_verdict") if isinstance(detail.get("guard_verdict"), dict) else None,
            )
        )
    return tuple(results)


def build_ragas_rows(results: Iterable[QuerySampleResult]) -> tuple[RagasRow, ...]:
    rows: list[RagasRow] = []
    for result in results:
        if result.expected_outcome != ExpectedOutcome.ANSWERED.value:
            continue
        if not result.answered:
            continue
        rows.append(
            RagasRow(
                record_id=result.record_id,
                user_input=result.question,
                response=result.answer,
                retrieved_contexts=result.retrieved_contexts,
                reference=result.reference_answer,
            )
        )
    return tuple(rows)


def evaluate_ragas_rows(rows: tuple[RagasRow, ...], config: RagasRunnerConfig) -> RagasScoringResult:
    if not rows:
        return RagasScoringResult(
            aggregate_scores={name: "skipped" for name in RAGAS_METRIC_NAMES},
            skipped_metrics={name: "no answered records available for RAGAS scoring" for name in RAGAS_METRIC_NAMES},
            external_judge_used=False,
        )

    llm = _build_judge_llm(config)
    embeddings, embedding_skip_reason = _build_embeddings(config)
    metrics, skipped_metrics = _ragas_metrics(include_answer_relevancy=embeddings is not None)
    if embedding_skip_reason:
        skipped_metrics["answer_relevancy"] = embedding_skip_reason

    try:
        from ragas.dataset_schema import SingleTurnSample
    except ImportError as exc:  # pragma: no cover - exercised by dependency/lock verification instead.
        raise RagasRunnerError("ragas and datasets must be installed to run the quality evaluation") from exc

    from ragas.run_config import RunConfig

    run_config = RunConfig(
        timeout=int(config.timeout_seconds),
        max_workers=config.concurrency,
        max_retries=config.ragas_max_retries,
        max_wait=config.ragas_max_wait,
    )
    scoring_metrics = tuple(copy.deepcopy(metric) for metric in metrics)
    _initialize_ragas_metrics(scoring_metrics, llm=llm, embeddings=embeddings, run_config=run_config)
    _disable_ragas_prompt_parser_retries(scoring_metrics)
    per_record_scores, per_record_errors = _run_ragas_metrics_per_record(
        rows,
        scoring_metrics,
        single_turn_sample_cls=SingleTurnSample,
        timeout_seconds=run_config.timeout,
    )
    aggregate_scores = _aggregate_scores(per_record_scores, skipped_metrics)
    return RagasScoringResult(
        aggregate_scores=aggregate_scores,
        per_record_scores=per_record_scores,
        per_record_errors=per_record_errors,
        skipped_metrics=skipped_metrics,
        external_judge_used=True,
    )


def build_evaluation_report(
    results: tuple[QuerySampleResult, ...],
    *,
    scoring: RagasScoringResult,
    validation_summary: GoldenValidationSummary,
    corpus_version: str,
    corpus_hash: str,
    config: RagasRunnerConfig,
) -> EvaluationReport:
    details = [
        _detail_with_scores(
            result,
            scoring.per_record_scores.get(result.record_id, {}),
            scoring.per_record_errors.get(result.record_id, {}),
        )
        for result in results
    ]
    outcome_counts = Counter(result.actual_outcome.value for result in results)
    route_counts = Counter(result.route for result in results)
    correct_outcomes = sum(1 for result in results if _outcome_correct(result))
    outcome_accuracy = correct_outcomes / len(results) if results else 0.0
    citation_recall = _citation_doc_recall(results)

    metrics = [
        MetricSummary(
            name="record_count",
            value=len(results),
            notes=f"Golden validation record_count={validation_summary.record_count}",
        ),
        MetricSummary(
            name="answered_count",
            value=outcome_counts[ActualOutcome.ANSWERED.value],
            notes=json.dumps(dict(sorted(outcome_counts.items())), ensure_ascii=False, sort_keys=True),
        ),
        MetricSummary(
            name="outcome_accuracy",
            value=round(outcome_accuracy, 4),
            threshold=0.80,
            passed=outcome_accuracy >= 0.80,
            notes="Actual outcome is compared to expected_outcome for all 40 records.",
        ),
        MetricSummary(
            name="citation_doc_recall",
            value=round(citation_recall, 4),
            threshold=0.70,
            passed=citation_recall >= 0.70,
            notes="Document-level expected_doc_ids present in returned citations for answerable records.",
        ),
        MetricSummary(
            name="route_mix",
            value=json.dumps(dict(sorted(route_counts.items())), ensure_ascii=False, sort_keys=True),
            notes="Production /v1/query route distribution.",
        ),
    ]
    for name in RAGAS_METRIC_NAMES:
        value = scoring.aggregate_scores.get(name, "skipped")
        threshold = RAGAS_THRESHOLDS.get(name)
        passed = None
        if isinstance(value, (float, int)) and threshold is not None:
            passed = float(value) >= threshold
        metrics.append(
            MetricSummary(
                name=name,
                value=round(float(value), 4) if isinstance(value, (float, int)) else value,
                threshold=threshold,
                passed=passed,
                notes=_metric_notes(name, scoring, len(scoring.per_record_scores)),
            )
        )

    runner_config = RunnerConfig(
        runner="ragas_production_query",
        model_id=config.judge_model_id,
        corpus_version=corpus_version,
        corpus_hash=corpus_hash,
        external_judge_used=scoring.external_judge_used,
        options={
            "service_base_url": config.service_base_url,
            "top_k": config.top_k,
            "reranker_enabled": config.reranker_enabled,
            "parent_context_enabled": config.parent_context_enabled,
            "qdrant_url": config.qdrant_url,
            "judge_model_id": config.judge_model_id,
            "judge_base_url": config.judge_base_url or _default_judge_base_url(),
            "embedding_model_id": config.embedding_model_id,
            "concurrency": config.concurrency,
            "batching": "disabled",
            "answer_relevancy_skipped": "answer_relevancy" in scoring.skipped_metrics,
            "token_usage": scoring.token_usage,
            "total_cost": scoring.total_cost,
            "ragas_max_retries": config.ragas_max_retries,
            "ragas_max_wait": config.ragas_max_wait,
            "ragas_score_failures": _score_failures_option(scoring.per_record_errors),
        },
    )
    return EvaluationReport(
        title="Russian Golden RAGAS Production Evaluation",
        corpus_version=corpus_version,
        corpus_hash=corpus_hash,
        model_id=config.judge_model_id,
        eval_timestamp=datetime.now(tz=UTC),
        runner_config=runner_config,
        external_judge_used=scoring.external_judge_used,
        metrics=metrics,
        details=details,
    )


def _build_judge_llm(config: RagasRunnerConfig):
    api_key = config.judge_api_key or os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RagasRunnerError("OPENAI_API_KEY or OPENROUTER_API_KEY is required for live RAGAS judge calls")

    try:
        from langchain_openai import ChatOpenAI
        from ragas.llms import LangchainLLMWrapper
    except ImportError as exc:  # pragma: no cover - exercised by dependency/lock verification instead.
        raise RagasRunnerError("langchain-openai and ragas are required for judge LLM integration") from exc

    return LangchainLLMWrapper(
        ChatOpenAI(
            model=config.judge_model_id,
            api_key=api_key,
            base_url=config.judge_base_url or _default_judge_base_url(),
            temperature=0,
        )
    )


def _build_embeddings(config: RagasRunnerConfig):
    embedding_model_id = (config.embedding_model_id or "").strip()
    if not embedding_model_id:
        return None, "embedding model disabled; answer_relevancy skipped"

    if _is_local_bge_embedding_model(embedding_model_id):
        try:
            from ragas.embeddings import LangchainEmbeddingsWrapper
        except ImportError as exc:  # pragma: no cover - exercised by dependency/lock verification instead.
            raise RagasRunnerError("ragas is required for local bge-m3 embedding integration") from exc

        return LangchainEmbeddingsWrapper(LocalBgeM3LangchainEmbeddings(model_name=embedding_model_id)), ""

    try:
        from langchain_openai import OpenAIEmbeddings
        from ragas.embeddings import LangchainEmbeddingsWrapper
    except ImportError as exc:  # pragma: no cover - exercised by dependency/lock verification instead.
        raise RagasRunnerError("langchain-openai and ragas are required for embedding integration") from exc

    api_key = config.embedding_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RagasRunnerError(f"OPENAI_API_KEY is required for non-local embedding model {embedding_model_id!r}")

    return (
        LangchainEmbeddingsWrapper(
            OpenAIEmbeddings(
                model=_openai_embedding_model_id(embedding_model_id),
                api_key=api_key,
                base_url=config.embedding_base_url or os.getenv("OPENAI_EMBEDDING_BASE_URL"),
            )
        ),
        "",
    )


def _ragas_metrics(*, include_answer_relevancy: bool):
    from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

    metrics = [faithfulness, context_precision, context_recall]
    skipped: dict[str, str] = {}
    if include_answer_relevancy:
        metrics.insert(1, answer_relevancy)
    else:
        skipped["answer_relevancy"] = "embeddings unavailable; answer_relevancy skipped"
    return metrics, skipped


def _initialize_ragas_metrics(
    metrics: tuple[Any, ...],
    *,
    llm: Any,
    embeddings: Any,
    run_config: Any,
) -> None:
    for metric in metrics:
        if hasattr(metric, "llm"):
            metric.llm = llm
        if hasattr(metric, "embeddings"):
            metric.embeddings = embeddings
        metric.init(run_config)


def _disable_ragas_prompt_parser_retries(metrics: tuple[Any, ...]) -> None:
    for metric in metrics:
        for value in vars(metric).values():
            if _looks_like_ragas_prompt(value):
                _force_prompt_no_parser_retry(value)


def _looks_like_ragas_prompt(value: Any) -> bool:
    return callable(getattr(value, "generate", None)) and hasattr(value, "output_model")


def _force_prompt_no_parser_retry(prompt: Any) -> None:
    original_generate = prompt.generate

    async def generate_without_parser_retries(*args: Any, **kwargs: Any) -> Any:
        kwargs["retries_left"] = 0
        return await original_generate(*args, **kwargs)

    prompt.generate = generate_without_parser_retries


def _run_ragas_metrics_per_record(
    rows: tuple[RagasRow, ...],
    metrics: tuple[Any, ...],
    *,
    single_turn_sample_cls: Any,
    timeout_seconds: float,
) -> tuple[dict[str, dict[str, float | None]], dict[str, dict[str, str]]]:
    return _run_coroutine_sync(
        _score_ragas_metrics_per_record(
            rows,
            metrics,
            single_turn_sample_cls=single_turn_sample_cls,
            timeout_seconds=timeout_seconds,
        )
    )


async def _score_ragas_metrics_per_record(
    rows: tuple[RagasRow, ...],
    metrics: tuple[Any, ...],
    *,
    single_turn_sample_cls: Any,
    timeout_seconds: float,
) -> tuple[dict[str, dict[str, float | None]], dict[str, dict[str, str]]]:
    per_record_scores: dict[str, dict[str, float | None]] = {}
    per_record_errors: dict[str, dict[str, str]] = {}
    for row in rows:
        sample = single_turn_sample_cls(**row.to_dataset_row())
        row_scores: dict[str, float | None] = {}
        per_record_scores[row.record_id] = row_scores
        for metric in metrics:
            metric_name = str(getattr(metric, "name", metric.__class__.__name__))
            try:
                score = await metric.single_turn_ascore(sample, callbacks=[], timeout=timeout_seconds)
            except Exception as exc:
                error = _format_exception_chain(exc)
                row_scores[metric_name] = None
                per_record_errors.setdefault(row.record_id, {})[metric_name] = error
                print(
                    f"RAGAS score failed: record_id={row.record_id} metric={metric_name} error={error}",
                    file=sys.stderr,
                    flush=True,
                )
                continue
            if isinstance(score, (float, int)) and math.isfinite(float(score)):
                row_scores[metric_name] = float(score)
            else:
                error = f"RAGAS returned non-finite score: {score!r}"
                row_scores[metric_name] = None
                per_record_errors.setdefault(row.record_id, {})[metric_name] = error
                print(
                    f"RAGAS score failed: record_id={row.record_id} metric={metric_name} error={error}",
                    file=sys.stderr,
                    flush=True,
                )
    return per_record_scores, per_record_errors


def _run_coroutine_sync(coro: Awaitable[Any]) -> Any:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    try:
        import nest_asyncio
    except ImportError as exc:  # pragma: no cover - ragas pulls this dependency in normal installs.
        raise RagasRunnerError("nest_asyncio is required to run RAGAS scoring inside async CLI flow") from exc

    nest_asyncio.apply()
    return loop.run_until_complete(coro)


def _format_exception_chain(exc: BaseException) -> str:
    parts: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        message = str(current).strip() or repr(current)
        parts.append(f"{type(current).__name__}: {message}")
        current = current.__cause__ or current.__context__
    summary = " <- ".join(parts)
    return summary if len(summary) <= 900 else summary[:897] + "..."


def _is_local_bge_embedding_model(model_id: str) -> bool:
    normalized = model_id.strip().lower()
    return normalized in {"bge-m3", DEFAULT_BGE_M3_MODEL.lower(), f"local/{DEFAULT_BGE_M3_MODEL.lower()}"}


def _openai_embedding_model_id(model_id: str) -> str:
    return model_id.removeprefix("openai/")


def _per_record_scores(result: Any, rows: tuple[RagasRow, ...]) -> dict[str, dict[str, float | str]]:
    raw_scores = getattr(result, "scores", None)
    if raw_scores is None:
        raw_scores = result.to_pandas().to_dict(orient="records")

    per_record: dict[str, dict[str, float | str]] = {}
    for row, scores in zip(rows, raw_scores, strict=False):
        per_record[row.record_id] = {
            key: value
            for key, value in scores.items()
            if key in RAGAS_METRIC_NAMES and _is_reportable_score(value)
        }
    return per_record


def _aggregate_scores(
    per_record_scores: dict[str, dict[str, float | str | None]],
    skipped_metrics: dict[str, str],
) -> dict[str, float | str]:
    aggregates: dict[str, float | str] = {}
    for name in RAGAS_METRIC_NAMES:
        if name in skipped_metrics:
            aggregates[name] = "skipped"
            continue
        values = [
            float(scores[name])
            for scores in per_record_scores.values()
            if name in scores and isinstance(scores[name], (float, int)) and math.isfinite(float(scores[name]))
        ]
        aggregates[name] = sum(values) / len(values) if values else "skipped"
        if not values:
            skipped_metrics[name] = "RAGAS did not return finite scores for this metric"
    return aggregates


def _detail_with_scores(
    result: QuerySampleResult,
    ragas_scores: dict[str, float | str | None],
    ragas_errors: dict[str, str],
) -> dict[str, Any]:
    detail = result.to_detail()
    detail["outcome_correct"] = _outcome_correct(result)
    detail["ragas_scores"] = ragas_scores
    if ragas_errors:
        detail["ragas_score_errors"] = ragas_errors
    return detail


def _metric_notes(name: str, scoring: RagasScoringResult, row_count: int) -> str:
    if name in scoring.skipped_metrics:
        return scoring.skipped_metrics[name]
    scored = sum(
        1
        for scores in scoring.per_record_scores.values()
        if isinstance(scores.get(name), (float, int)) and math.isfinite(float(scores[name]))
    )
    failures = [
        f"{record_id}: {errors[name]}"
        for record_id, errors in scoring.per_record_errors.items()
        if name in errors
    ]
    if failures:
        preview = "; ".join(failures[:3])
        suffix = "" if len(failures) <= 3 else f"; +{len(failures) - 3} more"
        return f"RAGAS metric over {scored}/{row_count} scored rows. Failed rows: {preview}{suffix}"
    return f"RAGAS metric over {scored}/{row_count} scored rows."


def _score_failures_option(per_record_errors: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    return [
        {"record_id": record_id, "metric": metric, "error": error}
        for record_id, errors in sorted(per_record_errors.items())
        for metric, error in sorted(errors.items())
    ]


def _load_score_source_report(source_report_path: Path) -> EvaluationReport:
    raw = source_report_path.read_text(encoding="utf-8")
    try:
        return EvaluationReport.model_validate_json(raw)
    except Exception as exc:
        try:
            from pydantic import ValidationError
        except ImportError:  # pragma: no cover - pydantic is a direct dependency.
            raise
        if isinstance(exc, ValidationError):
            raise RagasRunnerError(_format_report_validation_error(exc, raw)) from exc
        raise


def _format_report_validation_error(exc: Any, raw: str) -> str:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {}
    details: list[str] = []
    for error in exc.errors():
        loc = tuple(error.get("loc", ()))
        record_hint = _validation_record_hint(payload, loc)
        details.append(
            f"{_format_validation_loc(loc)}{record_hint}: {error.get('msg', '')} "
            f"(type={error.get('type', '')})"
        )
    return "score source report failed schema validation: " + "; ".join(details)


def _validation_record_hint(payload: Any, loc: tuple[Any, ...]) -> str:
    if not (len(loc) >= 2 and loc[0] == "details" and isinstance(loc[1], int)):
        return ""
    raw_details = payload.get("details") if isinstance(payload, dict) else None
    detail = raw_details[loc[1]] if isinstance(raw_details, list) and loc[1] < len(raw_details) else None
    if not isinstance(detail, dict):
        return f" at details[{loc[1]}]"
    record_id = detail.get("id") or detail.get("question_id") or "<missing id>"
    return f" at details[{loc[1]}] record_id={record_id!r}"


def _format_validation_loc(loc: tuple[Any, ...]) -> str:
    if not loc:
        return "<root>"
    return ".".join(str(item) for item in loc)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return (str(value),)


def _outcome_correct(result: QuerySampleResult) -> bool:
    return result.actual_outcome.value == result.expected_outcome


def _citation_doc_recall(results: Iterable[QuerySampleResult]) -> float:
    answerable = [result for result in results if result.expected_outcome == ExpectedOutcome.ANSWERED.value]
    if not answerable:
        return 0.0
    hits = 0
    for result in answerable:
        expected = set(result.expected_doc_ids)
        returned = set(result.citation_document_ids)
        if expected and expected <= returned:
            hits += 1
    return hits / len(answerable)


def _is_reportable_score(value: Any) -> bool:
    if isinstance(value, (float, int)):
        return math.isfinite(float(value))
    return isinstance(value, str) and bool(value)


def _safe_call(result: Any, method_name: str) -> Any | None:
    method = getattr(result, method_name, None)
    if method is None:
        return None
    try:
        return method()
    except Exception:
        return None


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump(mode="json"))
    if hasattr(value, "__dict__"):
        return _jsonable(vars(value))
    return str(value)


def _default_judge_base_url() -> str | None:
    return os.getenv("OPENAI_BASE_URL") or (DEFAULT_JUDGE_BASE_URL if os.getenv("OPENROUTER_API_KEY") else None)


def config_from_args(argv: list[str] | None = None) -> RagasRunnerConfig:
    parser = argparse.ArgumentParser(description="Run production /v1/query RAGAS evaluation over the Russian golden set.")
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_PATH)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--report-slug", default=DEFAULT_REPORT_SLUG)
    parser.add_argument("--service-base-url", default=os.getenv("AI_SERVICE_BASE_URL", DEFAULT_SERVICE_BASE_URL))
    parser.add_argument("--top-k", type=int, default=DEFAULT_EVAL_TOP_K)
    parser.add_argument("--no-reranker", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--no-parent-context", action="store_true")
    parser.add_argument("--qdrant-url", default=os.getenv("QDRANT_URL", DEFAULT_QDRANT_URL))
    parser.add_argument("--ai-db-url", default=os.getenv("AI_DB_URL", DEFAULT_AI_DB_URL))
    parser.add_argument("--judge-model-id", default=os.getenv("RAGAS_JUDGE_MODEL_ID", DEFAULT_JUDGE_MODEL_ID))
    parser.add_argument("--judge-base-url", default=os.getenv("RAGAS_JUDGE_BASE_URL"))
    parser.add_argument("--embedding-model-id", default=os.getenv("RAGAS_EMBEDDING_MODEL_ID", DEFAULT_EMBEDDING_MODEL_ID))
    parser.add_argument("--embedding-base-url", default=os.getenv("RAGAS_EMBEDDING_BASE_URL"))
    parser.add_argument("--score-report", type=Path, default=None)
    parser.add_argument("--ragas-max-retries", type=int, default=1)
    parser.add_argument("--ragas-max-wait", type=int, default=5)
    parser.add_argument("--show-progress", action="store_true")
    args = parser.parse_args(argv)
    return RagasRunnerConfig(
        golden_path=args.golden,
        metadata_path=args.metadata,
        corpus_dir=args.corpus_dir,
        manifest_path=args.manifest,
        reports_dir=args.reports_dir,
        report_slug=args.report_slug,
        service_base_url=args.service_base_url,
        top_k=args.top_k,
        reranker_enabled=not args.no_reranker,
        timeout_seconds=args.timeout_seconds,
        parent_context_enabled=not args.no_parent_context,
        qdrant_url=args.qdrant_url,
        ai_db_url=args.ai_db_url,
        judge_model_id=args.judge_model_id,
        judge_base_url=args.judge_base_url,
        embedding_model_id=args.embedding_model_id,
        embedding_base_url=args.embedding_base_url,
        concurrency=1,
        show_progress=args.show_progress,
        score_report_path=args.score_report,
        ragas_max_retries=args.ragas_max_retries,
        ragas_max_wait=args.ragas_max_wait,
    )


async def async_main(argv: list[str] | None = None) -> int:
    config = config_from_args(argv)
    if config.score_report_path is not None:
        output = await run_ragas_scoring_from_report(config, config.score_report_path)
    else:
        output = await run_ragas_evaluation(config)
    print(
        json.dumps(
            {
                "markdown_path": str(output.markdown_path),
                "json_path": str(output.json_path),
                "csv_path": str(output.csv_path) if output.csv_path else None,
                "record_count": len(output.report.details),
                "metrics": [metric.model_dump(mode="json") for metric in output.report.metrics],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
