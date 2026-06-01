from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
from collections import Counter
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from eval.io import load_corpus_metadata, load_golden_records, load_manifest
from eval.query_client import (
    ActualOutcome,
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
DEFAULT_EMBEDDING_MODEL_ID = "text-embedding-3-small"
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
    top_k: int = 10
    reranker_enabled: bool = True
    timeout_seconds: float = 180.0
    judge_model_id: str = DEFAULT_JUDGE_MODEL_ID
    judge_base_url: str | None = None
    judge_api_key: str | None = None
    embedding_model_id: str | None = DEFAULT_EMBEDDING_MODEL_ID
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    batch_size: int | None = None
    show_progress: bool = False


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
    per_record_scores: dict[str, dict[str, float | str]] = field(default_factory=dict)
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
    )
    factory = query_client_factory or ProductionQueryClient
    results: list[QuerySampleResult] = []
    async with factory(client_config) as client:
        for record in records:
            results.append(await client.query_golden(record))
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
        from datasets import Dataset
        from ragas import evaluate
    except ImportError as exc:  # pragma: no cover - exercised by dependency/lock verification instead.
        raise RagasRunnerError("ragas and datasets must be installed to run the quality evaluation") from exc

    dataset = Dataset.from_list([row.to_dataset_row() for row in rows])
    result = evaluate(
        dataset,
        metrics=metrics,
        llm=llm,
        embeddings=embeddings,
        raise_exceptions=False,
        show_progress=config.show_progress,
        batch_size=config.batch_size,
    )
    per_record_scores = _per_record_scores(result, rows)
    aggregate_scores = _aggregate_scores(per_record_scores, skipped_metrics)
    token_usage = _jsonable(_safe_call(result, "total_tokens"))
    total_cost = _safe_call(result, "total_cost")
    return RagasScoringResult(
        aggregate_scores=aggregate_scores,
        per_record_scores=per_record_scores,
        skipped_metrics=skipped_metrics,
        external_judge_used=True,
        token_usage=token_usage,
        total_cost=total_cost if isinstance(total_cost, float) and math.isfinite(total_cost) else None,
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
    details = [_detail_with_scores(result, scoring.per_record_scores.get(result.record_id, {})) for result in results]
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
                notes=scoring.skipped_metrics.get(name, f"RAGAS metric over {len(scoring.per_record_scores)} scored rows."),
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
            "judge_model_id": config.judge_model_id,
            "judge_base_url": config.judge_base_url or _default_judge_base_url(),
            "embedding_model_id": config.embedding_model_id,
            "answer_relevancy_skipped": "answer_relevancy" in scoring.skipped_metrics,
            "token_usage": scoring.token_usage,
            "total_cost": scoring.total_cost,
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
    if not config.embedding_model_id:
        return None, "embedding model disabled; answer_relevancy skipped"

    api_key = config.embedding_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None, "OPENAI_API_KEY is required for embeddings; answer_relevancy skipped"

    try:
        from langchain_openai import OpenAIEmbeddings
        from ragas.embeddings import LangchainEmbeddingsWrapper
    except ImportError as exc:  # pragma: no cover - exercised by dependency/lock verification instead.
        raise RagasRunnerError("langchain-openai and ragas are required for embedding integration") from exc

    return (
        LangchainEmbeddingsWrapper(
            OpenAIEmbeddings(
                model=config.embedding_model_id,
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
    per_record_scores: dict[str, dict[str, float | str]],
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


def _detail_with_scores(result: QuerySampleResult, ragas_scores: dict[str, float | str]) -> dict[str, Any]:
    detail = result.to_detail()
    detail["outcome_correct"] = _outcome_correct(result)
    detail["ragas_scores"] = ragas_scores
    return detail


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
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--no-reranker", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--judge-model-id", default=os.getenv("RAGAS_JUDGE_MODEL_ID", DEFAULT_JUDGE_MODEL_ID))
    parser.add_argument("--judge-base-url", default=os.getenv("RAGAS_JUDGE_BASE_URL"))
    parser.add_argument("--embedding-model-id", default=os.getenv("RAGAS_EMBEDDING_MODEL_ID", DEFAULT_EMBEDDING_MODEL_ID))
    parser.add_argument("--embedding-base-url", default=os.getenv("RAGAS_EMBEDDING_BASE_URL"))
    parser.add_argument("--batch-size", type=int, default=None)
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
        judge_model_id=args.judge_model_id,
        judge_base_url=args.judge_base_url,
        embedding_model_id=args.embedding_model_id,
        embedding_base_url=args.embedding_base_url,
        batch_size=args.batch_size,
        show_progress=args.show_progress,
    )


async def async_main(argv: list[str] | None = None) -> int:
    output = await run_ragas_evaluation(config_from_args(argv))
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
