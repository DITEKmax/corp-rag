from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_METADATA_PATH = EVAL_DIR / "golden" / "golden_ru.meta.json"


@dataclass(frozen=True, slots=True)
class ExpectedDocument:
    document_id: str
    title: str | None = None


@dataclass(frozen=True, slots=True)
class GraphDocumentState:
    document_id: str
    title: str | None = None
    entity_count: int | None = None
    relation_count: int | None = None
    mention_count: int | None = None


@dataclass(frozen=True, slots=True)
class JavaDocumentState:
    document_id: str
    title: str | None = None
    status: str | None = None
    neo4j_entity_count: int | None = None


@dataclass(frozen=True, slots=True)
class CorpusGraphStateReport:
    expected_count: int
    neo4j_count: int
    missing: tuple[ExpectedDocument, ...]
    extra: tuple[GraphDocumentState, ...]
    entity_count_zero: tuple[GraphDocumentState, ...]
    java_missing: tuple[ExpectedDocument, ...] = ()
    java_entity_count_zero: tuple[JavaDocumentState, ...] = ()
    java_status_not_indexed: tuple[JavaDocumentState, ...] = ()
    java_neo4j_count_mismatch: tuple[dict[str, Any], ...] = ()

    @property
    def ok(self) -> bool:
        return not (
            self.missing
            or self.extra
            or self.entity_count_zero
            or self.java_missing
            or self.java_entity_count_zero
            or self.java_status_not_indexed
            or self.java_neo4j_count_mismatch
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "expected_count": self.expected_count,
            "neo4j_count": self.neo4j_count,
            "missing": [_expected_to_dict(item) for item in self.missing],
            "extra": [_graph_to_dict(item) for item in self.extra],
            "entity_count_zero": [_graph_to_dict(item) for item in self.entity_count_zero],
            "java_missing": [_expected_to_dict(item) for item in self.java_missing],
            "java_entity_count_zero": [_java_to_dict(item) for item in self.java_entity_count_zero],
            "java_status_not_indexed": [_java_to_dict(item) for item in self.java_status_not_indexed],
            "java_neo4j_count_mismatch": list(self.java_neo4j_count_mismatch),
        }


def load_expected_documents(metadata_path: Path = DEFAULT_METADATA_PATH) -> tuple[ExpectedDocument, ...]:
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    document_map = payload.get("indexed_document_map")
    if isinstance(document_map, list) and document_map:
        documents = [
            ExpectedDocument(
                document_id=str(item["indexed_document_id"]),
                title=str(item["title"]) if item.get("title") is not None else None,
            )
            for item in document_map
        ]
    else:
        documents = [ExpectedDocument(document_id=str(document_id)) for document_id in payload["indexed_document_ids"]]
    return tuple(_sorted_expected(documents))


def compare_corpus_graph_state(
    *,
    expected_documents: Sequence[ExpectedDocument],
    neo4j_documents: Sequence[GraphDocumentState | Mapping[str, Any]],
    java_documents: Sequence[JavaDocumentState | Mapping[str, Any]] | None = None,
) -> CorpusGraphStateReport:
    expected_by_id = {doc.document_id: doc for doc in expected_documents}
    neo4j_by_id = {doc.document_id: doc for doc in (_coerce_graph_document(row) for row in neo4j_documents)}
    java_by_id = (
        {doc.document_id: doc for doc in (_coerce_java_document(row) for row in java_documents)}
        if java_documents is not None
        else {}
    )

    missing = _sorted_expected(expected_by_id[document_id] for document_id in set(expected_by_id) - set(neo4j_by_id))
    extra = _sorted_graph(neo4j_by_id[document_id] for document_id in set(neo4j_by_id) - set(expected_by_id))
    entity_count_zero = _sorted_graph(
        doc
        for document_id, doc in neo4j_by_id.items()
        if document_id in expected_by_id and doc.entity_count is not None and doc.entity_count <= 0
    )

    java_missing: tuple[ExpectedDocument, ...] = ()
    java_entity_count_zero: tuple[JavaDocumentState, ...] = ()
    java_status_not_indexed: tuple[JavaDocumentState, ...] = ()
    java_neo4j_count_mismatch: tuple[dict[str, Any], ...] = ()
    if java_documents is not None:
        java_missing = _sorted_expected(expected_by_id[document_id] for document_id in set(expected_by_id) - set(java_by_id))
        java_entity_count_zero = _sorted_java(
            doc
            for document_id, doc in java_by_id.items()
            if document_id in expected_by_id
            and doc.neo4j_entity_count is not None
            and doc.neo4j_entity_count <= 0
        )
        java_status_not_indexed = _sorted_java(
            doc for document_id, doc in java_by_id.items() if document_id in expected_by_id and doc.status != "INDEXED"
        )
        mismatches: list[dict[str, Any]] = []
        for document_id in sorted(set(expected_by_id) & set(neo4j_by_id) & set(java_by_id)):
            graph_count = neo4j_by_id[document_id].entity_count
            java_count = java_by_id[document_id].neo4j_entity_count
            if graph_count is None or java_count is None or graph_count == java_count:
                continue
            mismatches.append(
                {
                    "document_id": document_id,
                    "title": expected_by_id[document_id].title or neo4j_by_id[document_id].title or java_by_id[document_id].title,
                    "neo4j_entity_count": graph_count,
                    "java_neo4j_entity_count": java_count,
                }
            )
        java_neo4j_count_mismatch = tuple(mismatches)

    return CorpusGraphStateReport(
        expected_count=len(expected_by_id),
        neo4j_count=len(neo4j_by_id),
        missing=tuple(missing),
        extra=tuple(extra),
        entity_count_zero=tuple(entity_count_zero),
        java_missing=java_missing,
        java_entity_count_zero=java_entity_count_zero,
        java_status_not_indexed=java_status_not_indexed,
        java_neo4j_count_mismatch=java_neo4j_count_mismatch,
    )


def _coerce_graph_document(row: GraphDocumentState | Mapping[str, Any]) -> GraphDocumentState:
    if isinstance(row, GraphDocumentState):
        return row
    return GraphDocumentState(
        document_id=_required_string(row, "document_id", "documentId", "id"),
        title=_optional_string(row, "title"),
        entity_count=_optional_int(row, "entity_count", "entityCount", "entities"),
        relation_count=_optional_int(row, "relation_count", "relationCount", "relations"),
        mention_count=_optional_int(row, "mention_count", "mentionCount", "mentions"),
    )


def _coerce_java_document(row: JavaDocumentState | Mapping[str, Any]) -> JavaDocumentState:
    if isinstance(row, JavaDocumentState):
        return row
    return JavaDocumentState(
        document_id=_required_string(row, "document_id", "documentId", "id"),
        title=_optional_string(row, "title"),
        status=_optional_string(row, "status"),
        neo4j_entity_count=_optional_int(row, "neo4j_entity_count", "neo4jEntityCount"),
    )


def _required_string(row: Mapping[str, Any], *keys: str) -> str:
    value = _first_present(row, *keys)
    if value is None:
        raise ValueError(f"row must contain one of: {', '.join(keys)}")
    return str(value)


def _optional_string(row: Mapping[str, Any], *keys: str) -> str | None:
    value = _first_present(row, *keys)
    return None if value is None else str(value)


def _optional_int(row: Mapping[str, Any], *keys: str) -> int | None:
    value = _first_present(row, *keys)
    if value is None:
        return None
    return int(value)


def _first_present(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return None


def _sorted_expected(rows: Sequence[ExpectedDocument] | Any) -> tuple[ExpectedDocument, ...]:
    return tuple(sorted(rows, key=lambda row: row.document_id))


def _sorted_graph(rows: Sequence[GraphDocumentState] | Any) -> tuple[GraphDocumentState, ...]:
    return tuple(sorted(rows, key=lambda row: row.document_id))


def _sorted_java(rows: Sequence[JavaDocumentState] | Any) -> tuple[JavaDocumentState, ...]:
    return tuple(sorted(rows, key=lambda row: row.document_id))


def _expected_to_dict(document: ExpectedDocument) -> dict[str, Any]:
    return {"document_id": document.document_id, "title": document.title}


def _graph_to_dict(document: GraphDocumentState) -> dict[str, Any]:
    return {
        "document_id": document.document_id,
        "title": document.title,
        "entity_count": document.entity_count,
        "relation_count": document.relation_count,
        "mention_count": document.mention_count,
    }


def _java_to_dict(document: JavaDocumentState) -> dict[str, Any]:
    return {
        "document_id": document.document_id,
        "title": document.title,
        "status": document.status,
        "neo4j_entity_count": document.neo4j_entity_count,
    }


def _load_json_rows(path: Path) -> list[Mapping[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return payload["rows"]
    raise ValueError(f"{path} must contain a JSON list or an object with a rows list")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare live graph corpus rows to the frozen Russian golden metadata.")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_PATH)
    parser.add_argument("--neo4j-json", type=Path, required=True)
    parser.add_argument("--java-json", type=Path)
    args = parser.parse_args()

    expected_documents = load_expected_documents(args.metadata)
    report = compare_corpus_graph_state(
        expected_documents=expected_documents,
        neo4j_documents=_load_json_rows(args.neo4j_json),
        java_documents=_load_json_rows(args.java_json) if args.java_json else None,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
