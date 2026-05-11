"""Generate importable Python contract modules from root OpenAPI and AsyncAPI."""

from __future__ import annotations

import argparse
import json
import keyword
import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
PYTHON_OUT = ROOT / "ai-service" / "src" / "corp_rag_ai" / "contracts" / "generated"


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def class_name(name: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", name) if part]
    cleaned = "".join(part[:1].upper() + part[1:] for part in parts)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"Model{cleaned}"
    return cleaned


def enum_name(value: Any) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_").upper()
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"VALUE_{cleaned}"
    return cleaned


def field_name(name: str) -> tuple[str, bool]:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", name)
    if cleaned.startswith("_"):
        cleaned = cleaned.lstrip("_") or "value"
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"field_{cleaned}"
    if keyword.iskeyword(cleaned):
        cleaned = f"{cleaned}_"
    return cleaned, cleaned != name


def ref_name(ref: str) -> str:
    return class_name(ref.rsplit("/", 1)[-1])


def literal_type(values: list[Any]) -> str:
    return "Literal[" + ", ".join(json.dumps(value, ensure_ascii=False) for value in values) + "]"


def type_for(schema: dict[str, Any] | None) -> str:
    if not schema:
        return "Any"
    if "$ref" in schema:
        return ref_name(str(schema["$ref"]))
    if "enum" in schema:
        return literal_type(schema["enum"])
    schema_type = schema.get("type")
    schema_format = schema.get("format")
    if schema_type == "array":
        return f"list[{type_for(schema.get('items'))}]"
    if schema_type == "integer":
        return "int"
    if schema_type == "number":
        return "float"
    if schema_type == "boolean":
        return "bool"
    if schema_type == "object":
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            return f"dict[str, {type_for(additional)}]"
        return "dict[str, Any]"
    if schema_type == "string" and schema_format == "date-time":
        return "datetime"
    if schema_type == "string" and schema_format == "date":
        return "date"
    if schema_type == "string" and schema_format == "uuid":
        return "UUID"
    if schema_type == "string" and schema_format == "binary":
        return "bytes"
    return "str"


def schema_parts(schema: dict[str, Any], schemas: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    properties: dict[str, Any] = dict(schema.get("properties") or {})
    required = set(schema.get("required") or [])

    if "allOf" not in schema:
        return properties, required

    properties = {}
    required = set()
    for part in schema["allOf"]:
        if "$ref" in part:
            source_name = str(part["$ref"]).rsplit("/", 1)[-1]
            ref_properties, ref_required = schema_parts(schemas[source_name], schemas)
            properties.update(ref_properties)
            required.update(ref_required)
        else:
            properties.update(part.get("properties") or {})
            required.update(part.get("required") or [])
    return properties, required


def generate_module(module_name: str, source_file: Path) -> Path:
    data = load_yaml(source_file)
    schemas = ((data.get("components") or {}).get("schemas") or {})
    PYTHON_OUT.mkdir(parents=True, exist_ok=True)

    scalar_lines: list[str] = []
    model_lines: list[str] = []

    for raw_name, schema in schemas.items():
        name = class_name(raw_name)
        schema_type = schema.get("type")
        if "enum" in schema and schema_type == "string":
            scalar_lines.append(f"class {name}(str, Enum):")
            for value in schema["enum"]:
                scalar_lines.append(f"    {enum_name(value)} = {json.dumps(value, ensure_ascii=False)}")
            scalar_lines.append("")
            continue
        if schema_type != "object" and "allOf" not in schema:
            scalar_lines.append(f"{name} = {type_for(schema)}")
            scalar_lines.append("")
            continue

        properties, required = schema_parts(schema, schemas)
        model_lines.append(f"class {name}(BaseModel):")
        model_lines.append('    model_config = ConfigDict(populate_by_name=True, extra="allow")')
        if not properties:
            model_lines.append("    pass")
            model_lines.append("")
            continue
        for raw_field, field_schema in properties.items():
            safe_name, renamed = field_name(raw_field)
            annotation = type_for(field_schema)
            if raw_field not in required:
                annotation = f"{annotation} | None"
                default = "None"
            else:
                default = None
            if renamed:
                if default is None:
                    model_lines.append(f"    {safe_name}: {annotation} = Field(alias={json.dumps(raw_field)})")
                else:
                    model_lines.append(
                        f"    {safe_name}: {annotation} = Field(default={default}, alias={json.dumps(raw_field)})"
                    )
            elif default is None:
                model_lines.append(f"    {safe_name}: {annotation}")
            else:
                model_lines.append(f"    {safe_name}: {annotation} = {default}")
        model_lines.append("")

    lines = [
        '"""Generated contract models. Do not edit by hand."""',
        "from __future__ import annotations",
        "",
        "from datetime import date, datetime",
        "from enum import Enum",
        "from typing import Any, Literal",
        "from uuid import UUID",
        "",
        "from pydantic import BaseModel, ConfigDict, Field",
        "",
    ]
    lines.extend(scalar_lines)
    lines.extend(model_lines)

    path = PYTHON_OUT / f"{module_name}.py"
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def generate() -> list[Path]:
    generated = [
        generate_module("api_v1", ROOT / "contracts" / "openapi" / "api-v1.yaml"),
        generate_module("ai_service_v1", ROOT / "contracts" / "openapi" / "ai-service-v1.yaml"),
        generate_module("events_v1", ROOT / "contracts" / "asyncapi" / "events-v1.yaml"),
    ]
    init_file = PYTHON_OUT / "__init__.py"
    if not init_file.exists():
        init_file.write_text('"""Generated contract modules."""\n', encoding="utf-8")
    return generated


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    for path in generate():
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
