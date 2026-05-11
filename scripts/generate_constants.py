"""Generate Java and Python constants from contracts/constants.yaml."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONSTANTS_FILE = ROOT / "contracts" / "constants.yaml"
JAVA_OUT = (
    ROOT
    / "backend"
    / "corp-rag-contracts"
    / "target"
    / "generated-sources"
    / "constants"
    / "java"
    / "com"
    / "corprag"
    / "contracts"
    / "constants"
)
PYTHON_OUT = (
    ROOT
    / "ai-service"
    / "src"
    / "corp_rag_ai"
    / "contracts"
    / "generated"
)


class YamlSubsetParser:
    """A structured parser for the YAML subset used by the contract files."""

    def __init__(self, text: str) -> None:
        self.lines = self._prepare(text)

    def parse(self) -> Any:
        value, index = self._parse_block(0, 0)
        if index != len(self.lines):
            raise ValueError(f"Unexpected trailing YAML at line {self.lines[index][2]}")
        return value

    @staticmethod
    def _prepare(text: str) -> list[tuple[int, str, int]]:
        prepared: list[tuple[int, str, int]] = []
        for line_number, raw in enumerate(text.splitlines(), start=1):
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            content = _strip_comment(raw[indent:]).rstrip()
            if content:
                prepared.append((indent, content, line_number))
        return prepared

    def _parse_block(self, index: int, indent: int) -> tuple[Any, int]:
        if index >= len(self.lines):
            return {}, index
        current_indent, content, _ = self.lines[index]
        if current_indent < indent:
            return {}, index
        if current_indent != indent:
            indent = current_indent
        if content.startswith("- "):
            return self._parse_sequence(index, indent)
        return self._parse_mapping(index, indent)

    def _parse_mapping(self, index: int, indent: int) -> tuple[dict[str, Any], int]:
        result: dict[str, Any] = {}
        while index < len(self.lines):
            current_indent, content, line_number = self.lines[index]
            if current_indent < indent:
                break
            if current_indent > indent:
                raise ValueError(f"Unexpected indentation at line {line_number}")
            if content.startswith("- "):
                break

            key, raw_value = _split_key_value(content, line_number)
            if raw_value in {"|", ">"}:
                value, index = self._collect_block_scalar(index + 1, current_indent)
            elif raw_value == "":
                if index + 1 < len(self.lines) and self.lines[index + 1][0] > current_indent:
                    value, index = self._parse_block(index + 1, self.lines[index + 1][0])
                else:
                    value, index = {}, index + 1
            else:
                value = _parse_inline(raw_value)
                index += 1
            result[key] = value
        return result, index

    def _parse_sequence(self, index: int, indent: int) -> tuple[list[Any], int]:
        result: list[Any] = []
        while index < len(self.lines):
            current_indent, content, line_number = self.lines[index]
            if current_indent < indent:
                break
            if current_indent != indent or not content.startswith("- "):
                break

            raw_value = content[2:].strip()
            if raw_value == "":
                if index + 1 < len(self.lines) and self.lines[index + 1][0] > current_indent:
                    value, index = self._parse_block(index + 1, self.lines[index + 1][0])
                else:
                    value, index = None, index + 1
            elif _has_top_level_colon(raw_value):
                key, nested_value = _split_key_value(raw_value, line_number)
                value = {key: _parse_inline(nested_value) if nested_value else {}}
                index += 1
                if index < len(self.lines) and self.lines[index][0] > current_indent:
                    nested, index = self._parse_block(index, self.lines[index][0])
                    if isinstance(nested, dict):
                        value.update(nested)
            else:
                value = _parse_inline(raw_value)
                index += 1
                if index < len(self.lines) and self.lines[index][0] > current_indent:
                    _, index = self._parse_block(index, self.lines[index][0])
            result.append(value)
        return result, index

    def _collect_block_scalar(self, index: int, parent_indent: int) -> tuple[str, int]:
        parts: list[str] = []
        while index < len(self.lines):
            indent, content, _ = self.lines[index]
            if indent <= parent_indent:
                break
            parts.append(content)
            index += 1
        return "\n".join(parts).strip(), index


def _strip_comment(value: str) -> str:
    quote: str | None = None
    escaped = False
    for position, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char in {"'", '"'}:
            quote = None if quote == char else char if quote is None else quote
            continue
        if char == "#" and quote is None and (position == 0 or value[position - 1].isspace()):
            return value[:position].rstrip()
    return value


def _split_key_value(content: str, line_number: int) -> tuple[str, str]:
    quote: str | None = None
    depth = 0
    for position, char in enumerate(content):
        if char in {"'", '"'}:
            quote = None if quote == char else char if quote is None else quote
        elif quote is None:
            if char in "[{(":
                depth += 1
            elif char in "]})":
                depth -= 1
            elif char == ":" and depth == 0:
                return content[:position].strip(), content[position + 1 :].strip()
    raise ValueError(f"Expected key/value pair at line {line_number}: {content}")


def _has_top_level_colon(value: str) -> bool:
    try:
        _split_key_value(value, 0)
    except ValueError:
        return False
    return True


def _parse_inline(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    if value in {"[]", "{}"}:
        return [] if value == "[]" else {}
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [_parse_inline(part) for part in _split_top_level(inner, ",")]
    if value.startswith("{") and value.endswith("}"):
        inner = value[1:-1].strip()
        mapping: dict[str, Any] = {}
        if not inner:
            return mapping
        for part in _split_top_level(inner, ","):
            key, item_value = _split_key_value(part, 0)
            mapping[_unquote(key)] = _parse_inline(item_value)
        return mapping
    if value in {"true", "false"}:
        return value == "true"
    if value in {"null", "~"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return _unquote(value)


def _split_top_level(value: str, separator: str) -> list[str]:
    parts: list[str] = []
    quote: str | None = None
    depth = 0
    start = 0
    for position, char in enumerate(value):
        if char in {"'", '"'}:
            quote = None if quote == char else char if quote is None else quote
        elif quote is None:
            if char in "[{(":
                depth += 1
            elif char in "]})":
                depth -= 1
            elif char == separator and depth == 0:
                parts.append(value[start:position].strip())
                start = position + 1
    parts.append(value[start:].strip())
    return parts


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_yaml(path: Path) -> Any:
    return YamlSubsetParser(path.read_text(encoding="utf-8")).parse()


def constant_name(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", key).strip("_").upper()


def java_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


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
    path = JAVA_OUT / f"{class_name}.java"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


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
    path = JAVA_OUT / "ErrorCodes.java"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


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
    path = PYTHON_OUT / f"{module_name}.py"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


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
    path = PYTHON_OUT / "error_codes.py"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


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
    init_file.write_text('"""Generated contract modules."""\n', encoding="utf-8")
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
