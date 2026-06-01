from __future__ import annotations

from datetime import UTC, datetime

import pytest

from eval.reporting import write_report
from eval.schema import EvaluationReport, MetricSummary, RunnerConfig


def test_write_report_creates_markdown_json_and_csv(tmp_path) -> None:
    report = _report()

    artifact = write_report(report, reports_dir=tmp_path / "reports", slug="smoke", write_csv=True)

    markdown = artifact.markdown_path.read_text(encoding="utf-8")
    assert markdown.startswith("# Smoke Report")
    assert "## Details" in markdown
    assert "ru_fact_001" in markdown
    assert '"corpus_hash": "abc123"' in artifact.json_path.read_text(encoding="utf-8")
    assert artifact.csv_path is not None
    assert "question_id" in artifact.csv_path.read_text(encoding="utf-8")


def test_write_report_rejects_paths_outside_reports_dir(tmp_path) -> None:
    with pytest.raises(ValueError, match="reports_dir"):
        write_report(_report(), reports_dir=tmp_path / "reports", slug="../escape")


def _report() -> EvaluationReport:
    config = RunnerConfig(
        runner="smoke",
        model_id="deepseek-test",
        corpus_version="ru-aviation-logistics-v1",
        corpus_hash="abc123",
        external_judge_used=False,
        options={"top_k": 5},
    )
    return EvaluationReport(
        title="Smoke Report",
        corpus_version=config.corpus_version,
        corpus_hash=config.corpus_hash,
        model_id=config.model_id,
        eval_timestamp=datetime(2026, 6, 1, 8, 20, tzinfo=UTC),
        runner_config=config,
        external_judge_used=False,
        metrics=[MetricSummary(name="recall@5", value=1.0, threshold=0.8, passed=True)],
        details=[{"question_id": "ru_fact_001", "score": 1.0}],
    )
