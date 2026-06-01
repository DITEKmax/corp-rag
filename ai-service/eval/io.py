from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from eval.schema import CorpusManifest, CorpusMetadata, GoldenRecord

T = TypeVar("T", bound=BaseModel)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_jsonl(path: Path, model: type[T]) -> tuple[T, ...]:
    records: list[T] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(model.model_validate_json(line))
        except Exception as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSONL record") from exc
    return tuple(records)


def write_jsonl(path: Path, records: Iterable[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [record.model_dump_json(exclude_none=True) for record in records]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def load_golden_records(path: Path) -> tuple[GoldenRecord, ...]:
    return load_jsonl(path, GoldenRecord)


def load_manifest(path: Path) -> CorpusManifest:
    return CorpusManifest.model_validate(read_json(path))


def load_corpus_metadata(path: Path) -> CorpusMetadata:
    return CorpusMetadata.model_validate(read_json(path))


def corpus_document_paths(corpus_dir: Path, manifest: CorpusManifest) -> tuple[Path, ...]:
    return tuple((corpus_dir / entry.path).resolve() for entry in sorted(manifest.documents, key=lambda item: item.doc_id))


def compute_corpus_hash(corpus_dir: Path, manifest: CorpusManifest) -> str:
    digest = hashlib.sha256()
    for path in corpus_document_paths(corpus_dir, manifest):
        relative = path.relative_to(corpus_dir.resolve()).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def iter_corpus_texts(corpus_dir: Path, manifest: CorpusManifest) -> Iterator[tuple[str, str]]:
    for entry in sorted(manifest.documents, key=lambda item: item.doc_id):
        yield entry.doc_id, (corpus_dir / entry.path).read_text(encoding="utf-8")
