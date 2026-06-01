from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


EXPECTED_SERVICES = (
    "postgres",
    "minio",
    "rabbitmq",
    "qdrant",
    "neo4j",
    "langfuse",
    "java-backend",
    "python-ai",
    "frontend",
)
SECRET_TOKENS = ("password", "secret", "token", "key", "credential")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.self_test:
        return _run_self_test()

    ps_rows = _load_ps_rows(args)
    diagnostics = _load_diagnostics(args)
    memory = _capture_memory(args)
    report = build_report(
        ps_rows=ps_rows,
        diagnostics=diagnostics,
        memory=memory,
        compose_file=args.compose_file,
        env_file=args.env_file,
    )
    _write_output(report, args.output)
    _print_summary(report)
    return 0 if report["ok"] else 1


def build_report(
    *,
    ps_rows: Sequence[Mapping[str, Any]],
    diagnostics: Mapping[str, Any] | None,
    memory: Mapping[str, Any],
    compose_file: str,
    env_file: str | None,
) -> dict[str, Any]:
    rows_by_service = {str(row.get("Service") or row.get("service") or ""): row for row in ps_rows}
    services: list[dict[str, Any]] = []
    missing: list[str] = []
    unhealthy: list[str] = []
    for service in EXPECTED_SERVICES:
        row = rows_by_service.get(service)
        if row is None:
            missing.append(service)
            services.append({"service": service, "state": "missing", "health": "missing", "ok": False})
            continue
        state = str(row.get("State") or row.get("state") or "")
        health = _health(row)
        ok = state.lower() == "running" and health == "healthy"
        if not ok:
            unhealthy.append(service)
        services.append(
            {
                "service": service,
                "container": row.get("Name") or row.get("Names"),
                "state": state,
                "health": health,
                "status": row.get("Status"),
                "ok": ok,
            }
        )
    healthy_count = sum(1 for service in services if service["ok"])
    ok = healthy_count == len(EXPECTED_SERVICES)
    return {
        "ok": ok,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "compose_file": compose_file,
        "env_file": env_file,
        "healthy_count": healthy_count,
        "expected_count": len(EXPECTED_SERVICES),
        "missing_services": missing,
        "unhealthy_services": unhealthy,
        "services": services,
        "diagnostics": _redact(diagnostics or {}),
        "memory": _redact(memory),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    services = report.get("services") if isinstance(report.get("services"), list) else []
    diagnostics = report.get("diagnostics") if isinstance(report.get("diagnostics"), Mapping) else {}
    memory = report.get("memory") if isinstance(report.get("memory"), Mapping) else {}
    lines = [
        "# Phase 8 Compose Readiness Evidence",
        "",
        f"- Success: `{str(report.get('ok')).lower()}`",
        f"- Generated at: `{report.get('generated_at')}`",
        f"- Compose file: `{report.get('compose_file')}`",
        f"- Env file: `{report.get('env_file') or 'none'}`",
        f"- Services healthy: `{report.get('healthy_count')}/{report.get('expected_count')}`",
        "",
        "## Services",
        "",
        "| Service | Container | State | Health | Status |",
        "|---------|-----------|-------|--------|--------|",
    ]
    for service in services:
        if not isinstance(service, Mapping):
            continue
        lines.append(
            "| {service} | {container} | {state} | {health} | {status} |".format(
                service=service.get("service", ""),
                container=service.get("container", ""),
                state=service.get("state", ""),
                health=service.get("health", ""),
                status=service.get("status", ""),
            )
        )
    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
            f"`{json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)}`",
            "",
            "## Docker Memory",
            "",
            f"`{json.dumps(memory, ensure_ascii=False, sort_keys=True)}`",
            "",
        ]
    )
    if report.get("missing_services") or report.get("unhealthy_services"):
        lines.extend(
            [
                "## Blockers",
                "",
                f"- Missing services: `{', '.join(report.get('missing_services', [])) or 'none'}`",
                f"- Unhealthy services: `{', '.join(report.get('unhealthy_services', [])) or 'none'}`",
                "",
            ]
        )
    return "\n".join(lines)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only Phase 8 local demo stack health checker.")
    parser.add_argument("--compose-file", default="infra/docker-compose.yml")
    parser.add_argument("--env-file", default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--fixture-ps-json", type=Path, default=None)
    parser.add_argument("--diagnostics-json", type=Path, default=None)
    parser.add_argument("--diagnostics-url", default="http://localhost:8000/diagnostics")
    parser.add_argument("--skip-diagnostics", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def _load_ps_rows(args: argparse.Namespace) -> tuple[Mapping[str, Any], ...]:
    if args.fixture_ps_json is not None:
        return _parse_ps_json(args.fixture_ps_json.read_text(encoding="utf-8"))
    command = ["docker", "compose"]
    if args.env_file:
        command.extend(["--env-file", args.env_file])
    command.extend(["-f", args.compose_file, "ps", "--format", "json"])
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return _parse_ps_json(result.stdout)


def _parse_ps_json(text: str) -> tuple[Mapping[str, Any], ...]:
    stripped = text.strip()
    if not stripped:
        return ()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        rows = [json.loads(line) for line in stripped.splitlines() if line.strip()]
        return tuple(row for row in rows if isinstance(row, Mapping))
    if isinstance(parsed, list):
        return tuple(row for row in parsed if isinstance(row, Mapping))
    if isinstance(parsed, Mapping):
        return (parsed,)
    return ()


def _load_diagnostics(args: argparse.Namespace) -> Mapping[str, Any] | None:
    if args.skip_diagnostics:
        return None
    if args.diagnostics_json is not None:
        parsed = json.loads(args.diagnostics_json.read_text(encoding="utf-8"))
        return parsed if isinstance(parsed, Mapping) else {"value": parsed}
    try:
        with urllib.request.urlopen(args.diagnostics_url, timeout=8) as response:
            parsed = json.loads(response.read().decode("utf-8"))
            return parsed if isinstance(parsed, Mapping) else {"value": parsed}
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {"reachable": False, "error": exc.__class__.__name__, "message": str(exc)}


def _capture_memory(args: argparse.Namespace) -> dict[str, Any]:
    memory: dict[str, Any] = {
        "documented_python_ai_limit": "10g",
        "documented_python_ai_reservation": "8g",
        "documented_wsl_memory": "12GB",
    }
    mem_total = _run_optional(["docker", "info", "--format", "{{.MemTotal}}"])
    if mem_total:
        try:
            memory["docker_total_bytes"] = int(mem_total)
        except ValueError:
            memory["docker_total"] = mem_total
    container = _python_ai_container(args)
    if container:
        limit = _run_optional(["docker", "inspect", container, "--format", "{{.HostConfig.Memory}}"])
        reservation = _run_optional(["docker", "inspect", container, "--format", "{{.HostConfig.MemoryReservation}}"])
        memory["python_ai_container"] = container
        if limit:
            memory["python_ai_limit_bytes"] = int(limit)
        if reservation:
            memory["python_ai_reservation_bytes"] = int(reservation)
    return memory


def _python_ai_container(args: argparse.Namespace) -> str | None:
    command = ["docker", "compose"]
    if args.env_file:
        command.extend(["--env-file", args.env_file])
    command.extend(["-f", args.compose_file, "ps", "-q", "python-ai"])
    return _run_optional(command) or None


def _run_optional(command: Sequence[str]) -> str:
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def _health(row: Mapping[str, Any]) -> str:
    health = str(row.get("Health") or row.get("health") or "").strip().lower()
    if health:
        return health
    status = str(row.get("Status") or row.get("status") or "").lower()
    if "healthy" in status:
        return "healthy"
    if "unhealthy" in status:
        return "unhealthy"
    return "unknown"


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            if any(token in key_text.lower() for token in SECRET_TOKENS):
                result[key_text] = "[redacted]"
            else:
                result[key_text] = _redact(nested)
        return result
    if isinstance(value, list | tuple):
        return [_redact(item) for item in value]
    return value


def _write_output(report: Mapping[str, Any], output: Path | None) -> None:
    if output is None:
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".json":
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return
    output.write_text(render_markdown(report), encoding="utf-8")


def _print_summary(report: Mapping[str, Any]) -> None:
    print(f"services_healthy={report['healthy_count']}/{report['expected_count']}")
    if report["missing_services"]:
        print(f"missing={','.join(report['missing_services'])}")
    if report["unhealthy_services"]:
        print(f"unhealthy={','.join(report['unhealthy_services'])}")


def _run_self_test() -> int:
    fixture_rows = [
        {"Service": service, "Name": f"corp-rag-{service}-1", "State": "running", "Health": "healthy", "Status": "Up (healthy)"}
        for service in EXPECTED_SERVICES
    ]
    good = build_report(
        ps_rows=fixture_rows,
        diagnostics={"ready": True, "apiKey": "secret-value", "counters": {"query_count": 2}},
        memory={"python_ai_limit_bytes": 10737418240},
        compose_file="infra/docker-compose.yml",
        env_file="infra/.env",
    )
    assert good["ok"] is True
    assert good["healthy_count"] == 9
    assert good["diagnostics"]["apiKey"] == "[redacted]"
    assert "9/9" in render_markdown(good)

    broken_rows = fixture_rows[:-1]
    bad = build_report(
        ps_rows=broken_rows,
        diagnostics=None,
        memory={},
        compose_file="infra/docker-compose.yml",
        env_file=None,
    )
    assert bad["ok"] is False
    assert bad["missing_services"] == ["frontend"]
    print("self_test=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
