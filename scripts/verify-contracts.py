"""Verify contract linting, generation, Java compile, and Python imports."""

from __future__ import annotations

import importlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
CONTRACT_FILES = [
    ROOT / "contracts" / "openapi" / "api-v1.yaml",
    ROOT / "contracts" / "openapi" / "ai-service-v1.yaml",
    ROOT / "contracts" / "asyncapi" / "events-v1.yaml",
    ROOT / "contracts" / "constants.yaml",
]
PYTHON_GENERATED = ROOT / "ai-service" / "src"


def load_codegen_module() -> Any:
    path = SCRIPT_DIR / "generate_constants.py"
    spec = importlib.util.spec_from_file_location("generate_constants", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(command: list[str], cwd: Path = ROOT) -> None:
    display = " ".join(command)
    print(f"==> {display}")
    subprocess.run(command, cwd=cwd, check=True)


def lint_yaml() -> None:
    loader = load_codegen_module().load_yaml
    for path in CONTRACT_FILES:
        data = loader(path)
        if not isinstance(data, dict):
            raise ValueError(f"{path} did not parse to a mapping")
        if path.name.endswith(".yaml") and path.name != "constants.yaml":
            if "components" not in data:
                raise ValueError(f"{path} is missing components")
        print(f"lint ok: {path.relative_to(ROOT)}")


def run_maven(goal: str) -> None:
    maven = os.environ.get("MAVEN_CMD", "mvn")
    run([maven, "-q", "-pl", "corp-rag-contracts", goal], cwd=ROOT / "backend")


def smoke_import_python() -> None:
    sys.path.insert(0, str(PYTHON_GENERATED))
    modules = [
        "corp_rag_ai.contracts.generated.api_v1",
        "corp_rag_ai.contracts.generated.ai_service_v1",
        "corp_rag_ai.contracts.generated.events_v1",
        "corp_rag_ai.contracts.generated.routing_keys",
        "corp_rag_ai.contracts.generated.queue_names",
        "corp_rag_ai.contracts.generated.exchange_names",
        "corp_rag_ai.contracts.generated.error_codes",
    ]
    for module_name in modules:
        importlib.import_module(module_name)
        print(f"import ok: {module_name}")


def main() -> int:
    lint_yaml()
    run([sys.executable, str(SCRIPT_DIR / "generate_constants.py")])
    run_maven("generate-sources")
    run_maven("compile")
    run([sys.executable, str(SCRIPT_DIR / "generate_python_contracts.py")])
    smoke_import_python()
    print("contract verification complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
