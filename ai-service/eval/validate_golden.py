from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from eval.io import compute_corpus_hash, load_corpus_metadata, load_manifest
from eval.schema import ExpectedOutcome, GoldenQuestionType, GoldenRecord

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_GOLDEN_PATH = EVAL_DIR / "golden" / "golden_ru.jsonl"
DEFAULT_METADATA_PATH = EVAL_DIR / "golden" / "golden_ru.meta.json"
DEFAULT_CORPUS_DIR = EVAL_DIR / "corpus"
DEFAULT_MANIFEST_PATH = DEFAULT_CORPUS_DIR / "manifest.json"
REQUIRED_RECORDS_PER_TYPE = 10
REQUIRED_RECORD_COUNT = REQUIRED_RECORDS_PER_TYPE * len(GoldenQuestionType)
EXACT_CHUNK_FIELDS = {"expected_chunk_id", "expected_chunk_ids", "expected_chunk_ids_exact"}


@dataclass(frozen=True, slots=True)
class GoldenValidationSummary:
    record_count: int
    type_counts: dict[str, int]
    outcome_counts: dict[str, int]
    expected_document_count: int
    advisory_chunk_hints: int
    corpus_version: str
    corpus_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_count": self.record_count,
            "type_counts": self.type_counts,
            "outcome_counts": self.outcome_counts,
            "expected_document_count": self.expected_document_count,
            "advisory_chunk_hints": self.advisory_chunk_hints,
            "corpus_version": self.corpus_version,
            "corpus_hash": self.corpus_hash,
        }


class GoldenValidationError(ValueError):
    pass


def validate_golden(
    golden_path: Path = DEFAULT_GOLDEN_PATH,
    *,
    metadata_path: Path = DEFAULT_METADATA_PATH,
    corpus_dir: Path = DEFAULT_CORPUS_DIR,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> GoldenValidationSummary:
    manifest = load_manifest(manifest_path)
    metadata = load_corpus_metadata(metadata_path)
    actual_hash = compute_corpus_hash(corpus_dir, manifest)
    errors: list[str] = []

    if metadata.corpus_hash != actual_hash:
        errors.append(f"metadata corpus_hash does not match frozen corpus hash: {metadata.corpus_hash} != {actual_hash}")
    if metadata.corpus_version != manifest.corpus_version:
        errors.append("metadata corpus_version does not match corpus manifest")
    if metadata.document_count != len(manifest.documents):
        errors.append("metadata document_count does not match corpus manifest")
    if not metadata.indexed:
        errors.append("metadata indexed=false; golden records require the frozen corpus to be indexed first")
    if not metadata.indexed_document_ids:
        errors.append("metadata indexed_document_ids is empty")

    records = _load_records(golden_path, errors)
    _validate_records(records, indexed_document_ids=set(metadata.indexed_document_ids), errors=errors)

    if errors:
        raise GoldenValidationError("\n".join(errors))

    type_counts = Counter(record.type.value for record in records)
    outcome_counts = Counter(record.expected_outcome.value for record in records)
    expected_documents = {doc_id for record in records for doc_id in record.expected_doc_ids}
    return GoldenValidationSummary(
        record_count=len(records),
        type_counts=dict(sorted(type_counts.items())),
        outcome_counts=dict(sorted(outcome_counts.items())),
        expected_document_count=len(expected_documents),
        advisory_chunk_hints=sum(1 for record in records if record.expected_chunk_hint),
        corpus_version=metadata.corpus_version,
        corpus_hash=metadata.corpus_hash,
    )


def _load_records(path: Path, errors: list[str]) -> tuple[GoldenRecord, ...]:
    if not path.exists():
        errors.append(f"{path}: file does not exist")
        return ()

    records: list[GoldenRecord] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_number}: invalid JSON: {exc.msg}")
            continue
        exact_chunk_fields = EXACT_CHUNK_FIELDS & set(payload)
        if exact_chunk_fields:
            errors.append(
                f"{path}:{line_number}: exact chunk-id fields are not allowed: {', '.join(sorted(exact_chunk_fields))}"
            )
        try:
            records.append(GoldenRecord.model_validate(payload))
        except ValidationError as exc:
            errors.append(f"{path}:{line_number}: invalid golden record: {exc.errors()[0]['msg']}")
    return tuple(records)


def _validate_records(records: tuple[GoldenRecord, ...], *, indexed_document_ids: set[str], errors: list[str]) -> None:
    if len(records) != REQUIRED_RECORD_COUNT:
        errors.append(f"golden dataset must contain exactly {REQUIRED_RECORD_COUNT} records; found {len(records)}")

    ids = [record.id for record in records]
    duplicate_ids = sorted(record_id for record_id, count in Counter(ids).items() if count > 1)
    if duplicate_ids:
        errors.append(f"golden ids must be unique; duplicates: {', '.join(duplicate_ids)}")

    type_counts = Counter(record.type for record in records)
    for question_type in GoldenQuestionType:
        count = type_counts[question_type]
        if count != REQUIRED_RECORDS_PER_TYPE:
            errors.append(f"type {question_type.value} must have {REQUIRED_RECORDS_PER_TYPE} records; found {count}")

    outcome_counts = Counter(record.expected_outcome for record in records)
    no_evidence = outcome_counts[ExpectedOutcome.REFUSED_NO_EVIDENCE]
    guard = outcome_counts[ExpectedOutcome.REFUSED_GUARD]
    if not 5 <= no_evidence <= 7 or not 3 <= guard <= 5:
        errors.append(
            "out-of-scope outcomes must be approximately 6 refused_no_evidence and 4 refused_guard "
            f"(found {no_evidence}/{guard})"
        )

    for record in records:
        _validate_record_semantics(record, indexed_document_ids=indexed_document_ids, errors=errors)


def _validate_record_semantics(record: GoldenRecord, *, indexed_document_ids: set[str], errors: list[str]) -> None:
    for field_name, value in (
        ("question", record.question),
        ("reference_answer", record.reference_answer),
    ):
        if not _contains_cyrillic(value):
            errors.append(f"{record.id}: {field_name} must contain Russian/Cyrillic text")

    unknown_doc_ids = sorted(set(record.expected_doc_ids) - indexed_document_ids)
    if unknown_doc_ids:
        errors.append(f"{record.id}: expected_doc_ids not found in indexed corpus: {', '.join(unknown_doc_ids)}")

    if record.type is GoldenQuestionType.OUT_OF_SCOPE:
        if record.expected_outcome is ExpectedOutcome.ANSWERED:
            errors.append(f"{record.id}: out_of_scope records must refuse, not answer")
        if record.expected_doc_ids:
            errors.append(f"{record.id}: refused out_of_scope records must not require expected_doc_ids")
        return

    if record.expected_outcome is not ExpectedOutcome.ANSWERED:
        errors.append(f"{record.id}: answerable records must use expected_outcome=answered")


def _contains_cyrillic(value: str) -> bool:
    return any("\u0400" <= char <= "\u04ff" for char in value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Russian golden JSONL dataset.")
    parser.add_argument("golden_path", nargs="?", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_PATH)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    args = parser.parse_args()

    summary = validate_golden(
        args.golden_path,
        metadata_path=args.metadata,
        corpus_dir=args.corpus_dir,
        manifest_path=args.manifest,
    )
    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
