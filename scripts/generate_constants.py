"""Generate Java and Python constants from contracts/constants.yaml."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONSTANTS_FILE = ROOT / "contracts" / "constants.yaml"

# Keep these synchronized with backend/pom.xml and ai-service/pyproject.toml package layout.
JAVA_MODULE = "corp-rag-contracts"
JAVA_PACKAGE = "com.corprag.contracts.constants"
PYTHON_PACKAGE = "corp_rag_ai.contracts.generated"

JAVA_OUT = (
    ROOT
    / "backend"
    / JAVA_MODULE
    / "target/generated-sources/constants/java"
    / Path(*JAVA_PACKAGE.split("."))
)
PYTHON_OUT = (
    ROOT
    / "ai-service/src"
    / Path(*PYTHON_PACKAGE.split("."))
)


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def constant_name(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", key).strip("_").upper()


def java_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def write_lines(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_java_string_class(class_name: str, values: dict[str, str]) -> Path:
    lines = [
        "package com.corprag.contracts.constants;",
        "",
        f"public final class {class_name} {{",
        f"    private {class_name}() {{",
        "    }",
        "",
    ]
    for key, value in values.items():
        lines.append(f"    public static final String {constant_name(key)} = {java_string(value)};")
    lines.append("}")
    return write_lines(JAVA_OUT / f"{class_name}.java", lines)


def write_java_error_codes(values: dict[str, dict[str, Any]]) -> Path:
    lines = [
        "package com.corprag.contracts.constants;",
        "",
        "import java.util.Map;",
        "",
        "public final class ErrorCodes {",
        "    private ErrorCodes() {",
        "    }",
        "",
        "    public record ErrorCode(String code, int httpStatus, String problemType, String defaultTitle) {",
        "    }",
        "",
    ]
    for key, item in values.items():
        name = constant_name(key)
        lines.append(
            "    public static final ErrorCode "
            f"{name} = new ErrorCode({java_string(name)}, {int(item['http_status'])}, "
            f"{java_string(item['problem_type'])}, {java_string(item['default_title'])});"
        )
    lines.extend(["", "    public static final Map<String, ErrorCode> ALL = Map.ofEntries("])
    entries = [f"        Map.entry({constant_name(key)}.code(), {constant_name(key)})" for key in values]
    lines.append(",\n".join(entries))
    lines.extend(["    );", "}"])
    return write_lines(JAVA_OUT / "ErrorCodes.java", lines)


def write_python_string_module(module_name: str, values: dict[str, str]) -> Path:
    lines = [
        '"""Generated constants. Do not edit by hand."""',
        "",
    ]
    for key, value in values.items():
        lines.append(f"{constant_name(key)} = {json.dumps(value, ensure_ascii=False)}")
    lines.append("")
    lines.append("__all__ = [")
    for key in values:
        lines.append(f"    {json.dumps(constant_name(key))},")
    lines.append("]")
    return write_lines(PYTHON_OUT / f"{module_name}.py", lines)


def write_python_error_codes(values: dict[str, dict[str, Any]]) -> Path:
    lines = [
        '"""Generated error-code constants. Do not edit by hand."""',
        "",
    ]
    for key in values:
        lines.append(f"{constant_name(key)} = {json.dumps(constant_name(key))}")
    lines.extend(["", "ERROR_CODES = {"])
    for key, item in values.items():
        lines.append(
            f"    {json.dumps(constant_name(key))}: "
            f"{json.dumps({'http_status': item['http_status'], 'problem_type': item['problem_type'], 'default_title': item['default_title']}, ensure_ascii=False)},"
        )
    lines.extend(["}", "", "__all__ = ["])
    for key in values:
        lines.append(f"    {json.dumps(constant_name(key))},")
    lines.extend(['    "ERROR_CODES",', "]"])
    return write_lines(PYTHON_OUT / "error_codes.py", lines)


def generate(constants_file: Path = CONSTANTS_FILE) -> list[Path]:
    data = load_yaml(constants_file)
    JAVA_OUT.mkdir(parents=True, exist_ok=True)
    PYTHON_OUT.mkdir(parents=True, exist_ok=True)

    generated = [
        write_java_string_class("EventRoutingKeys", data["routing_keys"]),
        write_java_string_class("ExchangeNames", data["exchanges"]),
        write_java_string_class("QueueNames", data["queues"]),
        write_java_error_codes(data["error_codes"]),
        write_python_string_module("routing_keys", data["routing_keys"]),
        write_python_string_module("exchange_names", data["exchanges"]),
        write_python_string_module("queue_names", data["queues"]),
        write_python_error_codes(data["error_codes"]),
    ]
    init_file = PYTHON_OUT / "__init__.py"
    write_lines(init_file, ['"""Generated Pydantic models and constants. Do not edit by hand."""'])
    generated.append(init_file)
    return generated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--constants-file", type=Path, default=CONSTANTS_FILE)
    args = parser.parse_args()

    generated = generate(args.constants_file)
    for path in generated:
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
