from __future__ import annotations

import asyncio
import json

import pytest

from eval.io import load_golden_records
from eval.query_client import ActualOutcome, QuerySampleResult
from eval.ragas_runner import (
    DEFAULT_GOLDEN_PATH,
    RagasRunnerConfig,
    RagasScoringResult,
    build_ragas_rows,
    run_ragas_evaluation,
)
from eval.schema import ExpectedOutcome, GoldenRecord


def _sample(record: GoldenRecord) -> QuerySampleResult:
    answered = record.expected_outcome is ExpectedOutcome.ANSWERED
    if answered:
        actual_outcome = ActualOutcome.ANSWERED
        citation_document_ids = tuple(record.expected_doc_ids)
        retrieved_contexts = (f"Контекст для {record.id}",)
        answer = record.reference_answer
    elif record.expected_outcome is ExpectedOutcome.REFUSED_GUARD:
        actual_outcome = ActualOutcome.REFUSED_GUARD
        citation_document_ids = ()
        retrieved_contexts = ()
        answer = "Запрос отклонен защитной системой."
    else:
        actual_outcome = ActualOutcome.REFUSED_NO_EVIDENCE
        citation_document_ids = ()
        retrieved_contexts = ()
        answer = "В доступных документах нет подтвержденной информации."

    return QuerySampleResult(
        record_id=record.id,
        question=record.question,
        reference_answer=record.reference_answer,
        expected_doc_ids=tuple(record.expected_doc_ids),
        expected_outcome=record.expected_outcome.value,
        actual_outcome=actual_outcome,
        answered=answered,
        answer=answer,
        citations=(),
        retrieved_contexts=retrieved_contexts,
        citation_document_ids=citation_document_ids,
        route="FACTUAL",
        retrievers_attempted=("HYBRID",),
        retrievers_used=("HYBRID",) if answered else (),
        degradation_warnings=(),
        reranker_used=True,
        model_id="deepseek/deepseek-chat",
        confidence=0.9,
        service_latency_ms=100,
        client_latency_ms=120,
        trace_id=None,
        guard_verdict={"safe": False, "reason": "fixture"} if actual_outcome is ActualOutcome.REFUSED_GUARD else None,
    )


def test_build_ragas_rows_keeps_only_answered_answerable_records() -> None:
    records = load_golden_records(DEFAULT_GOLDEN_PATH)
    rows = build_ragas_rows(tuple(_sample(record) for record in records))

    assert len(rows) == 30
    assert all(row.record_id.startswith(("ru-factual", "ru-aggregation", "ru-multihop")) for row in rows)
    assert rows[0].retrieved_contexts


@pytest.mark.asyncio
async def test_runner_writes_reports_for_all_records_with_fake_clients(tmp_path) -> None:
    active_queries = 0
    max_active_queries = 0
    query_events: list[tuple[str, str]] = []

    class FakeClient:
        def __init__(self, config):
            self.config = config

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def query_golden(self, record: GoldenRecord) -> QuerySampleResult:
            nonlocal active_queries, max_active_queries
            assert self.config.access_filter is not None
            assert self.config.top_k == 5
            active_queries += 1
            max_active_queries = max(max_active_queries, active_queries)
            query_events.append(("start", record.id))
            await asyncio.sleep(0)
            active_queries -= 1
            query_events.append(("end", record.id))
            return _sample(record)

    def fake_evaluator(rows, config) -> RagasScoringResult:
        assert len(rows) == 30
        return RagasScoringResult(
            aggregate_scores={
                "faithfulness": 0.91,
                "answer_relevancy": "skipped",
                "context_precision": 0.83,
                "context_recall": 0.87,
            },
            per_record_scores={row.record_id: {"faithfulness": 0.91, "context_precision": 0.83} for row in rows},
            skipped_metrics={"answer_relevancy": "embedding fixture not configured"},
            external_judge_used=True,
            token_usage={"input_tokens": 10, "output_tokens": 5},
            total_cost=0.01,
        )

    output = await run_ragas_evaluation(
        RagasRunnerConfig(reports_dir=tmp_path / "reports"),
        query_client_factory=FakeClient,
        evaluator=fake_evaluator,
    )

    assert len(output.report.details) == 40
    assert output.report.external_judge_used is True
    assert {metric.name: metric.value for metric in output.report.metrics}["answer_relevancy"] == "skipped"
    assert output.markdown_path.exists()
    assert output.json_path.exists()
    assert output.csv_path is not None and output.csv_path.exists()
    markdown = output.markdown_path.read_text(encoding="utf-8")
    assert "ru-factual-001" in markdown
    assert "ru-out-010" in markdown
    assert max_active_queries == 1
    assert query_events[:4] == [
        ("start", "ru-factual-001"),
        ("end", "ru-factual-001"),
        ("start", "ru-factual-002"),
        ("end", "ru-factual-002"),
    ]


def test_runner_config_rejects_parallel_concurrency() -> None:
    with pytest.raises(ValueError, match="concurrency=1"):
        RagasRunnerConfig(concurrency=2)


@pytest.mark.asyncio
async def test_runner_persists_query_phase_report_before_scoring(tmp_path) -> None:
    class FakeClient:
        def __init__(self, config):
            self.config = config

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def query_golden(self, record: GoldenRecord) -> QuerySampleResult:
            assert self.config.top_k == 5
            return _sample(record)

    def failing_evaluator(rows, config) -> RagasScoringResult:
        assert len(rows) == 30
        raise RuntimeError("scoring failed")

    reports_dir = tmp_path / "reports"
    with pytest.raises(RuntimeError, match="scoring failed"):
        await run_ragas_evaluation(
            RagasRunnerConfig(reports_dir=reports_dir),
            query_client_factory=FakeClient,
            evaluator=failing_evaluator,
        )

    cache_path = reports_dir / "ragas_ru.json"
    assert cache_path.exists()
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["runner_config"]["options"]["query_phase_cache"] is True
    assert payload["runner_config"]["options"]["scoring_status"] == "pending"
    assert payload["runner_config"]["options"]["top_k"] == 5
    assert len(payload["details"]) == 40
    first_detail = payload["details"][0]
    assert {
        "question",
        "answer",
        "retrieved_contexts",
        "expected_doc_ids",
        "outcome",
        "reranker_used",
        "degradation_warnings",
    } <= set(first_detail)
    assert first_detail["outcome"] == first_detail["actual_outcome"]
    assert first_detail["ragas_scores"] == {}
