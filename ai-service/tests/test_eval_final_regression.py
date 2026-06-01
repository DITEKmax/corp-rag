from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from eval.final_regression import (
    ChatProbeConfig,
    DiagnosticsDelta,
    FinalRegressionError,
    RagasCommandConfig,
    build_ragas_command,
    load_input_evidence,
    render_markdown_report,
    run_chat_probe,
)


def _write_compose_evidence(path: Path, *, diagnostics: dict | None = None) -> None:
    payload = diagnostics or {"reranker_degraded_count": 0, "query_service": True}
    path.write_text(
        "\n".join(
            [
                "# Phase 8 Compose Readiness Evidence",
                "",
                "- Success: `true`",
                "- Services healthy: `9/9`",
                "",
                "## Diagnostics",
                "",
                f"`{json.dumps(payload)}`",
            ]
        ),
        encoding="utf-8",
    )


def _write_seed_evidence(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "success": True,
                "corpus_version": "ru-aviation-logistics-v1",
                "expected_document_count": 16,
                "document_count": 16,
                "compose_targets": {
                    "java_base_url": "http://localhost:8080",
                    "qdrant_url": "http://localhost:6333",
                },
                "java_documents": [
                    {"id": f"00000000-0000-4000-8000-{index:012d}", "status": "INDEXED"}
                    for index in range(16)
                ],
                "stores": {
                    "qdrant": {"status": "passed", "details": {"document_count": 16, "point_count": 16}},
                    "neo4j": {"status": "passed", "details": {"neo4j_count": 16}},
                },
            }
        ),
        encoding="utf-8",
    )


def test_evidence_loader_rejects_missing_compose_or_seed_evidence(tmp_path: Path) -> None:
    compose = tmp_path / "compose.md"
    seed = tmp_path / "seed.json"

    with pytest.raises(FinalRegressionError, match="compose evidence"):
        load_input_evidence(compose, seed)

    _write_compose_evidence(compose)
    with pytest.raises(FinalRegressionError, match="seed evidence"):
        load_input_evidence(compose, seed)


def test_evidence_loader_reads_compose_and_seed_counts(tmp_path: Path) -> None:
    compose = tmp_path / "compose.md"
    seed = tmp_path / "seed.json"
    _write_compose_evidence(compose, diagnostics={"reranker_degraded_count": 2})
    _write_seed_evidence(seed)

    evidence = load_input_evidence(compose, seed)

    assert evidence.compose.success is True
    assert evidence.compose.services_healthy == "9/9"
    assert evidence.compose.diagnostics["reranker_degraded_count"] == 2
    assert evidence.seed.expected_document_count == 16
    assert evidence.seed.java_indexed_count == 16
    assert evidence.seed.qdrant_count == 16
    assert evidence.seed.neo4j_count == 16


@pytest.mark.asyncio
async def test_java_chat_probe_requires_answered_response_with_citation_document_title() -> None:
    requests: list[tuple[str, dict | None, httpx.Headers]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8")) if request.content else None
        requests.append((request.url.path, payload, request.headers))
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={"user": {"id": "u"}}, headers={"Set-Cookie": "corp_rag_session=t; Path=/"})
        if request.url.path == "/api/v1/chat/conversations":
            return httpx.Response(200, json={"id": "22222222-2222-4222-8222-222222222222"})
        if request.url.path == "/api/v1/chat/query":
            return httpx.Response(
                200,
                json={
                    "conversationId": payload["conversationId"],
                    "messageId": "33333333-3333-4333-8333-333333333333",
                    "answered": True,
                    "status": "ANSWERED",
                    "answer": "Передача рейса фиксируется в журнале смены [1].",
                    "citations": [
                        {
                            "documentId": "337f4a65-efdc-4b3a-91a1-f2e3434439ca",
                            "documentTitle": "Регламент передачи рейса",
                            "chunkId": "44444444-4444-4444-8444-444444444444",
                            "sectionPath": "Документ",
                            "quote": "Журнал смены фиксирует передачу рейса.",
                            "score": 0.91,
                            "accessLevel": "INTERNAL",
                        }
                    ],
                    "retrievalMeta": {"route": "FACTUAL", "rerankerUsed": True, "degradationWarnings": []},
                },
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://java") as client:
        proof = await run_chat_probe(
            ChatProbeConfig(
                java_base_url="http://java",
                username="admin",
                password="secret",
                question="Что требует регламент передачи рейса?",
            ),
            client=client,
        )

    assert proof.answered is True
    assert proof.citation_titles == ("Регламент передачи рейса",)
    assert proof.route == "FACTUAL"
    assert requests[-1][0] == "/api/v1/chat/query"
    assert requests[-1][2]["Origin"] == "http://localhost"
    assert requests[-1][2]["Referer"] == "http://localhost/"
    assert requests[-2][0] == "/api/v1/chat/conversations"
    assert requests[-2][2]["Origin"] == "http://localhost"


@pytest.mark.asyncio
async def test_java_chat_probe_rejects_answer_without_document_title() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={}, headers={"Set-Cookie": "corp_rag_session=t; Path=/"})
        if request.url.path == "/api/v1/chat/conversations":
            return httpx.Response(200, json={"id": "22222222-2222-4222-8222-222222222222"})
        return httpx.Response(
            200,
            json={
                "conversationId": "22222222-2222-4222-8222-222222222222",
                "answered": True,
                "status": "ANSWERED",
                "answer": "Ответ [1].",
                "citations": [{"documentId": "d", "documentTitle": "", "chunkId": "c"}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://java") as client:
        with pytest.raises(FinalRegressionError, match="documentTitle"):
            await run_chat_probe(
                ChatProbeConfig(
                    java_base_url="http://java",
                    username="admin",
                    password="secret",
                    question="test",
                ),
                client=client,
            )


def test_diagnostics_delta_fails_when_reranker_degraded_count_increases() -> None:
    with pytest.raises(FinalRegressionError, match="reranker_degraded_count increased"):
        DiagnosticsDelta.from_snapshots(
            {"reranker_degraded_count": 0},
            {"reranker_degraded_count": 1},
        )

    delta = DiagnosticsDelta.from_snapshots(
        {"reranker_degraded_count": 2},
        {"reranker_degraded_count": 2},
    )
    assert delta.reranker_degraded_before == 2
    assert delta.reranker_degraded_after == 2


def test_ragas_command_uses_seed_metadata_and_required_safety_flags(tmp_path: Path) -> None:
    _write_compose_evidence(tmp_path / "compose.md")
    _write_seed_evidence(tmp_path / "seed.json")
    loaded = load_input_evidence(tmp_path / "compose.md", tmp_path / "seed.json")

    command = build_ragas_command(
        RagasCommandConfig(
            evidence=loaded,
            python_executable="python",
            ai_service_dir=Path("ai-service"),
            reports_dir=Path("ai-service/eval/reports"),
        )
    )

    assert command[:3] == ["python", "eval/ragas_runner.py", "--service-base-url"]
    assert "--top-k" in command and command[command.index("--top-k") + 1] == "10"
    assert "--ragas-max-retries" in command and command[command.index("--ragas-max-retries") + 1] == "1"
    assert "--ragas-max-wait" in command and command[command.index("--ragas-max-wait") + 1] == "5"
    assert "--embedding-model-id" in command and command[command.index("--embedding-model-id") + 1] == "BAAI/bge-m3"
    assert "--qdrant-url" in command and command[command.index("--qdrant-url") + 1] == "http://localhost:6333"


def test_report_rendering_includes_multihop_known_limitation(tmp_path: Path) -> None:
    _write_compose_evidence(tmp_path / "compose.md")
    _write_seed_evidence(tmp_path / "seed.json")
    evidence = load_input_evidence(tmp_path / "compose.md", tmp_path / "seed.json")
    markdown = render_markdown_report(
        evidence=evidence,
        current_compose={"services_healthy": "9/9"},
        chat_proof=None,
        diagnostics_delta=DiagnosticsDelta.from_snapshots(
            {"reranker_degraded_count": 0},
            {"reranker_degraded_count": 0},
        ),
        ragas_summary={"faithfulness": 0.9},
        ragas_command=["python", "eval/ragas_runner.py"],
        blocker=None,
    )

    assert "ru-multihop-002" in markdown
    assert "ru-multihop-003" in markdown
    assert "ru-multihop-005" in markdown
    assert "ru-multihop-006" in markdown
    assert "refused_no_evidence" in markdown
