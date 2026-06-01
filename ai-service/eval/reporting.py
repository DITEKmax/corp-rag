from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from eval.io import write_json
from eval.schema import EvaluationReport, ReportArtifact


def write_report(report: EvaluationReport, *, reports_dir: Path, slug: str, write_csv: bool = False) -> ReportArtifact:
    reports_dir = reports_dir.resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = _safe_report_path(reports_dir, f"{slug}.md")
    json_path = _safe_report_path(reports_dir, f"{slug}.json")
    csv_path = _safe_report_path(reports_dir, f"{slug}.csv") if write_csv else None

    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    write_json(json_path, report.model_dump(mode="json"))
    if csv_path is not None:
        _write_csv(csv_path, report.details)
    return ReportArtifact(markdown_path=markdown_path, json_path=json_path, csv_path=csv_path)


def _safe_report_path(reports_dir: Path, filename: str) -> Path:
    path = (reports_dir / filename).resolve()
    if reports_dir not in path.parents and path != reports_dir:
        raise ValueError("report path must stay under reports_dir")
    return path


def _render_markdown(report: EvaluationReport) -> str:
    lines = [
        f"# {report.title}",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Corpus version | `{report.corpus_version}` |",
        f"| Corpus hash | `{report.corpus_hash}` |",
        f"| Model id | `{report.model_id}` |",
        f"| Eval timestamp | `{report.eval_timestamp.isoformat()}` |",
        f"| External judge used | `{str(report.external_judge_used).lower()}` |",
        "",
        "## Runner Configuration",
        "",
        "```json",
        report.runner_config.model_dump_json(indent=2),
        "```",
        "",
        "## Metrics",
        "",
        "| Metric | Value | Threshold | Passed | Notes |",
        "|---|---:|---:|---|---|",
    ]
    for metric in report.metrics:
        threshold = "" if metric.threshold is None else str(metric.threshold)
        passed = "" if metric.passed is None else str(metric.passed).lower()
        lines.append(f"| {metric.name} | {metric.value} | {threshold} | {passed} | {metric.notes} |")
    if report.details:
        lines.extend(
            [
                "",
                "## Details",
                "",
                "| ID | Expected | Actual | Correct | Route | Citation Docs | Trace ID |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for detail in report.details:
            citation_docs = detail.get("citation_document_ids") or detail.get("expected_doc_ids") or []
            if isinstance(citation_docs, list):
                citation_docs_value = ", ".join(str(item) for item in citation_docs)
            else:
                citation_docs_value = str(citation_docs)
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(detail.get("id") or detail.get("question_id") or ""),
                        _markdown_cell(detail.get("expected_outcome", "")),
                        _markdown_cell(detail.get("actual_outcome", "")),
                        _markdown_cell(detail.get("outcome_correct", "")),
                        _markdown_cell(detail.get("route", "")),
                        _markdown_cell(citation_docs_value),
                        _markdown_cell(detail.get("trace_id", "")),
                    ]
                )
                + " |"
            )
    lines.append("")
    return "\n".join(lines)


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
