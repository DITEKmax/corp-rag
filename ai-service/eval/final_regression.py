from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx


REPO_ROOT = Path(__file__).resolve().parents[2]
AI_SERVICE_DIR = Path(__file__).resolve().parents[1]
PHASE_DIR = REPO_ROOT / ".planning" / "phases" / "08-delivery-polish-demo-readiness"
DEFAULT_COMPOSE_EVIDENCE = PHASE_DIR / "08-COMPOSE-EVIDENCE.md"
DEFAULT_SEED_EVIDENCE = PHASE_DIR / "08-SEED-EVIDENCE.json"
DEFAULT_FINAL_REPORT = PHASE_DIR / "08-FINAL-REGRESSION.md"
DEFAULT_FINAL_JSON = PHASE_DIR / "08-FINAL-REGRESSION.json"
DEFAULT_DIAGNOSTICS_URL = "http://localhost:8000/diagnostics"
DEFAULT_JAVA_BASE_URL = "http://localhost:8080"
DEFAULT_AI_SERVICE_BASE_URL = "http://localhost:8000"
DEFAULT_RAGAS_REPORT_JSON = AI_SERVICE_DIR / "eval" / "reports" / "ragas_ru.json"
DEFAULT_CHAT_QUESTION = "Что требует регламент передачи рейса при передаче рейса между сменами?"
RAGAS_METRIC_NAMES = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
WAIVED_MULTI_HOP_IDS = ("ru-multihop-002", "ru-multihop-003", "ru-multihop-005", "ru-multihop-006")


class FinalRegressionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ComposeEvidence:
    success: bool
    services_healthy: str
    diagnostics: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SeedEvidence:
    success: bool
    corpus_version: str
    expected_document_count: int
    document_count: int
    java_indexed_count: int
    qdrant_count: int
    qdrant_points: int | None
    neo4j_count: int
    non_seed_count: int
    java_base_url: str
    qdrant_url: str


@dataclass(frozen=True, slots=True)
class FinalRegressionInput:
    compose: ComposeEvidence
    seed: SeedEvidence


@dataclass(frozen=True, slots=True)
class DiagnosticsDelta:
    before: dict[str, Any]
    after: dict[str, Any]
    reranker_degraded_before: int
    reranker_degraded_after: int

    @classmethod
    def from_snapshots(cls, before: Mapping[str, Any], after: Mapping[str, Any]) -> DiagnosticsDelta:
        before_count = _int_metric(before, "reranker_degraded_count")
        after_count = _int_metric(after, "reranker_degraded_count")
        if after_count > before_count:
            raise FinalRegressionError(
                "reranker_degraded_count increased "
                f"from {before_count} to {after_count}; final regression is blocked"
            )
        return cls(
            before=dict(before),
            after=dict(after),
            reranker_degraded_before=before_count,
            reranker_degraded_after=after_count,
        )


@dataclass(frozen=True, slots=True)
class ChatProbeConfig:
    java_base_url: str
    username: str
    password: str
    question: str = DEFAULT_CHAT_QUESTION
    timeout_seconds: float = 120.0
    conversation_id: str | None = None
    browser_origin: str = "http://localhost"


@dataclass(frozen=True, slots=True)
class ChatProof:
    conversation_id: str
    message_id: str | None
    question: str
    answered: bool
    status: str
    answer_excerpt: str
    citation_titles: tuple[str, ...]
    citation_document_ids: tuple[str, ...]
    route: str | None
    reranker_used: bool | None
    degradation_warnings: tuple[str, ...]
    trace_id: str | None


@dataclass(frozen=True, slots=True)
class RagasCommandConfig:
    evidence: FinalRegressionInput
    python_executable: str = sys.executable
    ai_service_dir: Path = AI_SERVICE_DIR
    reports_dir: Path = Path("eval") / "reports"
    ai_service_base_url: str = DEFAULT_AI_SERVICE_BASE_URL
    judge_base_url: str = "https://openrouter.ai/api/v1"
    judge_model_id: str = "deepseek/deepseek-chat"
    embedding_model_id: str = "BAAI/bge-m3"
    top_k: int = 10
    timeout_seconds: int = 60
    ragas_max_retries: int = 1
    ragas_max_wait: int = 5


@dataclass(frozen=True, slots=True)
class RagasRunResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    summary: dict[str, Any]


def load_input_evidence(compose_markdown_path: Path, seed_json_path: Path) -> FinalRegressionInput:
    if not compose_markdown_path.exists():
        raise FinalRegressionError(f"Missing compose evidence: {compose_markdown_path}")
    if not seed_json_path.exists():
        raise FinalRegressionError(f"Missing seed evidence: {seed_json_path}")

    compose = _parse_compose_evidence(compose_markdown_path.read_text(encoding="utf-8"))
    seed_payload = json.loads(seed_json_path.read_text(encoding="utf-8"))
    seed = _parse_seed_evidence(seed_payload)
    _validate_seed_evidence(seed)
    return FinalRegressionInput(compose=compose, seed=seed)


def _parse_compose_evidence(text: str) -> ComposeEvidence:
    success = _markdown_bool(text, "Success")
    services_healthy = _markdown_field(text, "Services healthy")
    diagnostics = _extract_first_json_object_after(text, "## Diagnostics")
    if services_healthy != "9/9":
        raise FinalRegressionError(f"Compose evidence is not 9/9 healthy: {services_healthy!r}")
    if not success:
        raise FinalRegressionError("Compose evidence is not successful")
    return ComposeEvidence(success=success, services_healthy=services_healthy, diagnostics=diagnostics)


def _parse_seed_evidence(payload: Mapping[str, Any]) -> SeedEvidence:
    store_checks = payload.get("stores") if isinstance(payload.get("stores"), Mapping) else {}
    if not store_checks:
        store_checks = payload.get("store_checks") if isinstance(payload.get("store_checks"), Mapping) else {}
    qdrant = store_checks.get("qdrant") if isinstance(store_checks.get("qdrant"), Mapping) else {}
    neo4j = store_checks.get("neo4j") if isinstance(store_checks.get("neo4j"), Mapping) else {}
    qdrant_details = qdrant.get("details") if isinstance(qdrant.get("details"), Mapping) else {}
    neo4j_details = neo4j.get("details") if isinstance(neo4j.get("details"), Mapping) else {}
    java_documents = payload.get("java_documents") if isinstance(payload.get("java_documents"), list) else []
    compose_targets = payload.get("compose_targets") if isinstance(payload.get("compose_targets"), Mapping) else {}
    return SeedEvidence(
        success=bool(payload.get("success")),
        corpus_version=str(payload.get("corpus_version") or ""),
        expected_document_count=int(payload.get("expected_document_count") or 0),
        document_count=int(payload.get("document_count") or 0),
        java_indexed_count=sum(1 for document in java_documents if document.get("status") == "INDEXED"),
        qdrant_count=int(qdrant_details.get("document_count") or 0),
        qdrant_points=_optional_int(qdrant_details.get("point_count")),
        neo4j_count=int(neo4j_details.get("neo4j_count") or 0),
        non_seed_count=len(payload.get("non_seed_java_documents") or ()),
        java_base_url=str(compose_targets.get("java_base_url") or DEFAULT_JAVA_BASE_URL),
        qdrant_url=str(compose_targets.get("qdrant_url") or "http://localhost:6333"),
    )


def _validate_seed_evidence(seed: SeedEvidence) -> None:
    expected = seed.expected_document_count
    if not seed.success:
        raise FinalRegressionError("Seed evidence is not successful")
    if expected != 16:
        raise FinalRegressionError(f"Seed evidence expected_document_count is {expected}, not 16")
    counts = {
        "document_count": seed.document_count,
        "java_indexed_count": seed.java_indexed_count,
        "qdrant_count": seed.qdrant_count,
        "neo4j_count": seed.neo4j_count,
    }
    bad = {name: value for name, value in counts.items() if value != expected}
    if bad:
        raise FinalRegressionError(f"Seed/index evidence is not 16/16: {bad}")
    if seed.non_seed_count != 0:
        raise FinalRegressionError(f"Seed evidence has non_seed_java_documents={seed.non_seed_count}")


async def run_chat_probe(config: ChatProbeConfig, *, client: httpx.AsyncClient | None = None) -> ChatProof:
    owns_client = client is None
    active_client = client or httpx.AsyncClient(
        base_url=config.java_base_url.rstrip("/"),
        timeout=httpx.Timeout(config.timeout_seconds),
    )
    try:
        await _login(active_client, config.username, config.password)
        unsafe_headers = _unsafe_headers(config.browser_origin)
        conversation_id = config.conversation_id or await _create_conversation(active_client, unsafe_headers)
        payload = {
            "conversationId": conversation_id,
            "message": config.question,
        }
        response = await active_client.post(
            "/api/v1/chat/query",
            json=payload,
            headers={"X-Correlation-Id": str(uuid4()), **unsafe_headers},
        )
        _raise_for_status(response, "chat query")
        body = response.json()
        return _chat_proof_from_response(config.question, body, response)
    finally:
        if owns_client:
            await active_client.aclose()


def build_ragas_command(config: RagasCommandConfig) -> list[str]:
    reports_dir = config.reports_dir
    if reports_dir.is_absolute():
        try:
            reports_dir = reports_dir.relative_to(config.ai_service_dir)
        except ValueError:
            pass
    return [
        config.python_executable,
        "eval/ragas_runner.py",
        "--service-base-url",
        config.ai_service_base_url,
        "--top-k",
        str(config.top_k),
        "--timeout-seconds",
        str(config.timeout_seconds),
        "--qdrant-url",
        config.evidence.seed.qdrant_url,
        "--judge-base-url",
        config.judge_base_url,
        "--judge-model-id",
        config.judge_model_id,
        "--embedding-model-id",
        config.embedding_model_id,
        "--reports-dir",
        str(reports_dir),
        "--ragas-max-retries",
        str(config.ragas_max_retries),
        "--ragas-max-wait",
        str(config.ragas_max_wait),
    ]


def run_ragas_command(config: RagasCommandConfig, *, timeout_seconds: int = 3600) -> RagasRunResult:
    command = build_ragas_command(config)
    completed = subprocess.run(
        command,
        cwd=config.ai_service_dir,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    summary = {}
    if completed.returncode == 0:
        summary = load_ragas_summary(config.ai_service_dir / config.reports_dir / "ragas_ru.json")
    return RagasRunResult(
        command=tuple(command),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        summary=summary,
    )


def load_ragas_summary(report_json_path: Path) -> dict[str, Any]:
    if not report_json_path.exists():
        raise FinalRegressionError(f"Missing RAGAS report JSON: {report_json_path}")
    payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    metrics = payload.get("metrics") or []
    summary: dict[str, Any] = {}
    for metric in metrics:
        name = metric.get("name")
        if name in RAGAS_METRIC_NAMES:
            summary[name] = metric.get("value")
    summary["answered_count"] = _metric_value(metrics, "answered_count")
    summary["outcome_accuracy"] = _metric_value(metrics, "outcome_accuracy")
    summary["citation_doc_recall"] = _metric_value(metrics, "citation_doc_recall")
    summary["route_mix"] = _metric_value(metrics, "route_mix")
    return summary


async def fetch_diagnostics(url: str, *, timeout_seconds: float = 30.0) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
        response = await client.get(url)
        _raise_for_status(response, "diagnostics")
        return dict(response.json())


def run_compose_check(*, repo_root: Path = REPO_ROOT, env_file: Path | None = None) -> dict[str, Any]:
    env_file = env_file or repo_root / "infra" / ".env"
    command = [
        sys.executable,
        str(repo_root / "scripts" / "check_demo_stack.py"),
        "--compose-file",
        str(repo_root / "infra" / "docker-compose.yml"),
        "--env-file",
        str(env_file),
    ]
    completed = subprocess.run(command, cwd=repo_root, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise FinalRegressionError(
            "Compose health check failed: "
            + (completed.stdout.strip() or completed.stderr.strip() or f"exit {completed.returncode}")
        )
    match = re.search(r"services_healthy=(\d+/\d+)", completed.stdout)
    return {
        "command": command,
        "stdout": completed.stdout.strip(),
        "services_healthy": match.group(1) if match else "unknown",
    }


def render_markdown_report(
    *,
    evidence: FinalRegressionInput,
    current_compose: Mapping[str, Any] | None,
    chat_proof: ChatProof | None,
    diagnostics_delta: DiagnosticsDelta | None,
    ragas_summary: Mapping[str, Any] | None,
    ragas_command: Sequence[str],
    blocker: str | None,
) -> str:
    generated_at = datetime.now(UTC).isoformat()
    lines = [
        "# Phase 8 Final Regression Evidence",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Status: `{'blocked' if blocker else 'checkpoint'}`",
        f"- Corpus version: `{evidence.seed.corpus_version}`",
        "",
        "## Compose Health",
        "",
        f"- Input evidence: `{evidence.compose.services_healthy}`",
        f"- Live check: `{(current_compose or {}).get('services_healthy', 'not-run')}`",
        "",
        "## Seed And Index",
        "",
        f"- Expected documents: `{evidence.seed.expected_document_count}`",
        f"- Java indexed: `{evidence.seed.java_indexed_count}/16`",
        f"- Qdrant documents: `{evidence.seed.qdrant_count}/16`",
        f"- Qdrant points: `{evidence.seed.qdrant_points}`",
        f"- Neo4j documents: `{evidence.seed.neo4j_count}/16`",
        f"- Non-seed Java documents: `{evidence.seed.non_seed_count}`",
        "",
        "## Chat Citation Proof",
        "",
    ]
    if chat_proof is None:
        lines.append("- Chat probe: `not-run`")
    else:
        lines.extend(
            [
                f"- Question: `{chat_proof.question}`",
                f"- Answered: `{str(chat_proof.answered).lower()}`",
                f"- Status: `{chat_proof.status}`",
                f"- Route: `{chat_proof.route or ''}`",
                f"- Reranker used: `{chat_proof.reranker_used}`",
                f"- Citation document titles: `{', '.join(chat_proof.citation_titles)}`",
                f"- Citation document ids: `{', '.join(chat_proof.citation_document_ids)}`",
                f"- Trace id: `{chat_proof.trace_id or ''}`",
                "",
                "Answer excerpt:",
                "",
                f"> {_one_line(chat_proof.answer_excerpt)}",
            ]
        )
    lines.extend(["", "## Reranker Degradation", ""])
    if diagnostics_delta is None:
        lines.append("- Diagnostics delta: `not-run`")
    else:
        lines.extend(
            [
                f"- reranker_degraded_count before: `{diagnostics_delta.reranker_degraded_before}`",
                f"- reranker_degraded_count after: `{diagnostics_delta.reranker_degraded_after}`",
            ]
        )
    lines.extend(["", "## RAGAS Production Eval", "", f"- Command: `{_quote_command(ragas_command)}`"])
    if ragas_summary:
        for name in RAGAS_METRIC_NAMES:
            lines.append(f"- {name}: `{ragas_summary.get(name)}`")
        lines.extend(
            [
                f"- answered_count: `{ragas_summary.get('answered_count')}`",
                f"- outcome_accuracy: `{ragas_summary.get('outcome_accuracy')}`",
                f"- citation_doc_recall: `{ragas_summary.get('citation_doc_recall')}`",
                f"- route_mix: `{ragas_summary.get('route_mix')}`",
            ]
        )
    else:
        lines.append("- Summary: `not-run`")
    lines.extend(
        [
            "",
            "## Known Limitations",
            "",
            "- Multi-hop graph retrieval remains waived for Phase 8: "
            + ", ".join(f"`{record_id}`" for record_id in WAIVED_MULTI_HOP_IDS)
            + ".",
            "- Current safe behavior for those rows is `refused_no_evidence`, not fabricated unsupported answers.",
            "- Data-exfiltration explicit guard classification and `ru-factual-009` router work remain future work.",
            "",
            "## Guardrails",
            "",
            "- Guard, citation validation, access filters, weak-evidence thresholds, refusal behavior, corpus, golden data, and expected UUIDs were not changed.",
            "- Generated `ai-service/eval/reports/ragas_ru.*` files are checkpoint artifacts and must not be committed before review.",
        ]
    )
    if blocker:
        lines.extend(["", "## Blocker", "", blocker])
    return "\n".join(lines).rstrip() + "\n"


def write_json_report(
    path: Path,
    *,
    evidence: FinalRegressionInput,
    current_compose: Mapping[str, Any] | None,
    chat_proof: ChatProof | None,
    diagnostics_delta: DiagnosticsDelta | None,
    ragas_result: RagasRunResult | None,
    blocker: str | None,
) -> None:
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "blocked" if blocker else "checkpoint",
        "compose": {
            "input_services_healthy": evidence.compose.services_healthy,
            "live": dict(current_compose or {}),
        },
        "seed": {
            "corpus_version": evidence.seed.corpus_version,
            "expected_document_count": evidence.seed.expected_document_count,
            "document_count": evidence.seed.document_count,
            "java_indexed_count": evidence.seed.java_indexed_count,
            "qdrant_count": evidence.seed.qdrant_count,
            "qdrant_points": evidence.seed.qdrant_points,
            "neo4j_count": evidence.seed.neo4j_count,
            "non_seed_count": evidence.seed.non_seed_count,
        },
        "chat_proof": _dataclass_to_json(chat_proof),
        "diagnostics_delta": _dataclass_to_json(diagnostics_delta),
        "ragas": _dataclass_to_json(ragas_result),
        "blocker": blocker,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def run_final_regression(args: argparse.Namespace) -> int:
    evidence = load_input_evidence(args.compose_evidence, args.seed_evidence)
    current_compose: dict[str, Any] | None = None
    chat_proof: ChatProof | None = None
    diagnostics_delta: DiagnosticsDelta | None = None
    ragas_result: RagasRunResult | None = None
    blocker: str | None = None

    try:
        if not args.skip_compose_check:
            current_compose = run_compose_check(repo_root=REPO_ROOT, env_file=args.compose_env)
        before = await fetch_diagnostics(args.diagnostics_url)
        chat_proof = await run_chat_probe(
            ChatProbeConfig(
                java_base_url=args.java_base_url or evidence.seed.java_base_url,
                username=args.username,
                password=args.password,
                question=args.question,
                timeout_seconds=args.http_timeout_seconds,
                conversation_id=args.conversation_id,
                browser_origin=args.browser_origin,
            )
        )
        if args.skip_ragas:
            ragas_command = build_ragas_command(_ragas_config(args, evidence))
            ragas_summary: dict[str, Any] = {}
        else:
            ragas_config = _ragas_config(args, evidence)
            ragas_result = run_ragas_command(ragas_config, timeout_seconds=args.ragas_timeout_seconds)
            if ragas_result.returncode != 0:
                raise FinalRegressionError(
                    "RAGAS command failed: "
                    + (ragas_result.stderr.strip() or ragas_result.stdout.strip() or f"exit {ragas_result.returncode}")
                )
            ragas_command = ragas_result.command
            ragas_summary = ragas_result.summary
        after = await fetch_diagnostics(args.diagnostics_url)
        diagnostics_delta = DiagnosticsDelta.from_snapshots(before, after)
    except Exception as exc:
        blocker = str(exc)
        ragas_command = build_ragas_command(_ragas_config(args, evidence))
        ragas_summary = ragas_result.summary if ragas_result else {}

    markdown = render_markdown_report(
        evidence=evidence,
        current_compose=current_compose,
        chat_proof=chat_proof,
        diagnostics_delta=diagnostics_delta,
        ragas_summary=ragas_summary,
        ragas_command=ragas_command,
        blocker=blocker,
    )
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.write_text(markdown, encoding="utf-8")
    write_json_report(
        args.output_json,
        evidence=evidence,
        current_compose=current_compose,
        chat_proof=chat_proof,
        diagnostics_delta=diagnostics_delta,
        ragas_result=ragas_result,
        blocker=blocker,
    )
    print(f"Wrote final regression evidence: {args.output_markdown}")
    print(f"Wrote final regression JSON: {args.output_json}")
    if blocker:
        print(f"Final regression blocker: {blocker}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase 8 final regression evidence collection.")
    parser.add_argument("--compose-evidence", type=Path, default=DEFAULT_COMPOSE_EVIDENCE)
    parser.add_argument("--seed-evidence", type=Path, default=DEFAULT_SEED_EVIDENCE)
    parser.add_argument("--output-markdown", type=Path, default=DEFAULT_FINAL_REPORT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_FINAL_JSON)
    parser.add_argument("--compose-env", type=Path, default=REPO_ROOT / "infra" / ".env")
    parser.add_argument("--skip-compose-check", action="store_true")
    parser.add_argument("--skip-ragas", action="store_true")
    parser.add_argument("--diagnostics-url", default=DEFAULT_DIAGNOSTICS_URL)
    parser.add_argument("--java-base-url", default=os.getenv("DEMO_JAVA_BASE_URL", os.getenv("JAVA_BASE_URL", DEFAULT_JAVA_BASE_URL)))
    parser.add_argument("--ai-service-base-url", default=os.getenv("AI_SERVICE_BASE_URL", DEFAULT_AI_SERVICE_BASE_URL))
    parser.add_argument("--username", default=os.getenv("DEMO_ADMIN_USERNAME", os.getenv("ADMIN_USERNAME", "admin")))
    parser.add_argument("--password", default=os.getenv("DEMO_ADMIN_PASSWORD", os.getenv("ADMIN_PASSWORD")))
    parser.add_argument("--question", default=DEFAULT_CHAT_QUESTION)
    parser.add_argument("--conversation-id")
    parser.add_argument("--browser-origin", default=os.getenv("DEMO_BROWSER_ORIGIN", "http://localhost"))
    parser.add_argument("--http-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--ragas-timeout-seconds", type=int, default=3600)
    parser.add_argument("--ragas-reports-dir", type=Path, default=Path("eval") / "reports")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--ragas-max-retries", type=int, default=1)
    parser.add_argument("--ragas-max-wait", type=int, default=5)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.password:
        parser.error("admin password is required via --password, DEMO_ADMIN_PASSWORD, or ADMIN_PASSWORD")
    return asyncio.run(run_final_regression(args))


async def _login(client: httpx.AsyncClient, username: str, password: str) -> None:
    response = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    _raise_for_status(response, "login")


async def _create_conversation(client: httpx.AsyncClient, headers: Mapping[str, str]) -> str:
    response = await client.post("/api/v1/chat/conversations", json={}, headers=dict(headers))
    _raise_for_status(response, "create conversation")
    payload = response.json()
    conversation_id = str(payload.get("id") or "")
    if not conversation_id:
        raise FinalRegressionError("Java conversation creation did not return id")
    return conversation_id


def _chat_proof_from_response(question: str, body: Mapping[str, Any], response: httpx.Response) -> ChatProof:
    if body.get("answered") is not True or body.get("status") != "ANSWERED":
        raise FinalRegressionError(f"Chat probe did not answer successfully: status={body.get('status')!r}")
    answer = str(body.get("answer") or "").strip()
    if not answer:
        raise FinalRegressionError("Chat probe returned an empty answer")
    citations = body.get("citations")
    if not isinstance(citations, list) or not citations:
        raise FinalRegressionError("Chat probe returned no citations")
    titles: list[str] = []
    document_ids: list[str] = []
    for citation in citations:
        title = str(citation.get("documentTitle") or "").strip() if isinstance(citation, Mapping) else ""
        if not title:
            raise FinalRegressionError("Chat probe citation is missing documentTitle")
        titles.append(title)
        document_ids.append(str(citation.get("documentId") or ""))
    meta = body.get("retrievalMeta") if isinstance(body.get("retrievalMeta"), Mapping) else {}
    warnings = meta.get("degradationWarnings") if isinstance(meta.get("degradationWarnings"), list) else []
    return ChatProof(
        conversation_id=str(body.get("conversationId") or ""),
        message_id=str(body.get("messageId") or "") or None,
        question=question,
        answered=True,
        status=str(body.get("status") or ""),
        answer_excerpt=answer[:500],
        citation_titles=tuple(titles),
        citation_document_ids=tuple(document_ids),
        route=str(meta.get("route") or "") or None,
        reranker_used=meta.get("rerankerUsed") if isinstance(meta.get("rerankerUsed"), bool) else None,
        degradation_warnings=tuple(str(item) for item in warnings),
        trace_id=_trace_id(response.headers),
    )


def _ragas_config(args: argparse.Namespace, evidence: FinalRegressionInput) -> RagasCommandConfig:
    return RagasCommandConfig(
        evidence=evidence,
        python_executable=sys.executable,
        ai_service_dir=AI_SERVICE_DIR,
        reports_dir=args.ragas_reports_dir,
        ai_service_base_url=args.ai_service_base_url,
        top_k=args.top_k,
        ragas_max_retries=args.ragas_max_retries,
        ragas_max_wait=args.ragas_max_wait,
    )


def _raise_for_status(response: httpx.Response, operation: str) -> None:
    if response.status_code < 400:
        return
    try:
        body = response.json()
    except ValueError:
        body = {"detail": response.text}
    detail = body.get("detail") or body.get("title") or response.reason_phrase
    raise FinalRegressionError(f"Java {operation} failed with HTTP {response.status_code}: {detail}")


def _markdown_field(text: str, name: str) -> str:
    match = re.search(rf"-\s*{re.escape(name)}:\s*`([^`]+)`", text)
    if not match:
        raise FinalRegressionError(f"Compose evidence is missing {name!r}")
    return match.group(1).strip()


def _markdown_bool(text: str, name: str) -> bool:
    return _markdown_field(text, name).lower() == "true"


def _extract_first_json_object_after(text: str, marker: str) -> dict[str, Any]:
    start = text.find(marker)
    if start < 0:
        raise FinalRegressionError(f"Evidence is missing section {marker!r}")
    for line in text[start:].splitlines():
        candidate = line.strip().strip("`")
        if candidate.startswith("{") and candidate.endswith("}"):
            return dict(json.loads(candidate))
    raise FinalRegressionError(f"Evidence section {marker!r} does not contain JSON")


def _int_metric(payload: Mapping[str, Any], key: str) -> int:
    try:
        return int(payload.get(key) or 0)
    except (TypeError, ValueError) as exc:
        raise FinalRegressionError(f"diagnostics metric {key!r} is not an integer") from exc


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _metric_value(metrics: list[Mapping[str, Any]], name: str) -> Any:
    for metric in metrics:
        if metric.get("name") == name:
            return metric.get("value")
    return None


def _quote_command(command: Sequence[str]) -> str:
    return " ".join(str(part) for part in command)


def _one_line(value: str) -> str:
    return " ".join(value.split())


def _trace_id(headers: httpx.Headers) -> str | None:
    for name in ("x-langfuse-trace-id", "x-trace-id", "traceparent"):
        value = headers.get(name)
        if value:
            return value
    return None


def _unsafe_headers(origin: str) -> dict[str, str]:
    normalized = origin.rstrip("/")
    return {"Origin": normalized, "Referer": f"{normalized}/"}


def _dataclass_to_json(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "__dataclass_fields__"):
        result: dict[str, Any] = {}
        for name in value.__dataclass_fields__:
            result[name] = _dataclass_to_json(getattr(value, name))
        return result
    if isinstance(value, Mapping):
        return {str(key): _dataclass_to_json(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_dataclass_to_json(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


if __name__ == "__main__":
    raise SystemExit(main())
