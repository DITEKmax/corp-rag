from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from eval.graph_corpus_state import ExpectedDocument, JavaDocumentState, compare_corpus_graph_state
from eval.io import load_manifest, write_json
from eval.schema import CorpusManifest, CorpusManifestEntry


EVAL_DIR = Path(__file__).resolve().parent
AI_SERVICE_DIR = EVAL_DIR.parent
PROJECT_ROOT = AI_SERVICE_DIR.parent
DEFAULT_CORPUS_DIR = EVAL_DIR / "corpus"
DEFAULT_MANIFEST_PATH = DEFAULT_CORPUS_DIR / "manifest.json"
DEFAULT_PHASE_DIR = PROJECT_ROOT / ".planning" / "phases" / "08-delivery-polish-demo-readiness"
DEFAULT_EVIDENCE_JSON = DEFAULT_PHASE_DIR / "08-SEED-EVIDENCE.json"
DEFAULT_EVIDENCE_MARKDOWN = DEFAULT_PHASE_DIR / "08-SEED-EVIDENCE.md"
DEFAULT_JAVA_BASE_URL = "http://localhost:8080"
DEFAULT_QDRANT_URL = "http://localhost:6333"
DEFAULT_QDRANT_COLLECTION = "documents_chunks"
DEFAULT_NEO4J_URI = "bolt://localhost:7687"
DEFAULT_NEO4J_USER = "neo4j"
DEFAULT_NEO4J_PASSWORD = "local-neo4j-password"
DEFAULT_NEO4J_DATABASE = "neo4j"
EXPECTED_DEMO_DOCUMENT_COUNT = 16
SEED_MARKER_PREFIX = "corp-rag-demo-seed"
INDEXED_STATUS = "INDEXED"
FAILED_STATUSES = {"INDEXING_FAILED"}


class SeedCorpusError(RuntimeError):
    """Raised when the demo seed reset cannot finish cleanly."""


@dataclass(frozen=True, slots=True)
class JavaDocumentRecord:
    id: str
    title: str
    status: str
    chunk_count: int | None
    indexed_at: str | None
    failure_reason: str | None
    original_filename: str | None = None
    description: str | None = None
    access_level: str | None = None
    department: str | None = None
    doc_type: str | None = None
    language: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> JavaDocumentRecord:
        return cls(
            id=str(_first_present(payload, "id", "documentId")),
            title=str(payload.get("title") or ""),
            original_filename=_optional_string(payload, "originalFilename", "original_filename"),
            description=_optional_string(payload, "description"),
            access_level=_optional_string(payload, "accessLevel", "access_level"),
            department=_optional_string(payload, "department"),
            doc_type=_optional_string(payload, "docType", "doc_type"),
            language=_optional_string(payload, "language"),
            status=str(payload.get("status") or ""),
            chunk_count=_optional_int(payload, "chunkCount", "chunk_count"),
            indexed_at=_optional_string(payload, "indexedAt", "indexed_at"),
            failure_reason=_optional_string(payload, "failureReason", "failure_reason"),
        )

    def to_evidence(self, *, manifest_doc_id: str | None = None) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "chunk_count": self.chunk_count,
            "indexed_at": self.indexed_at,
            "failure_reason": self.failure_reason,
        }
        if manifest_doc_id is not None:
            payload["manifest_doc_id"] = manifest_doc_id
        return payload


@dataclass(frozen=True, slots=True)
class StoreCheck:
    ok: bool
    status: str
    details: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "details": _redact(self.details),
        }


@dataclass(frozen=True, slots=True)
class SeedRunConfig:
    java_base_url: str = DEFAULT_JAVA_BASE_URL
    username: str = "admin"
    password: str | None = None
    corpus_dir: Path = DEFAULT_CORPUS_DIR
    manifest_path: Path = DEFAULT_MANIFEST_PATH
    evidence_json_path: Path = DEFAULT_EVIDENCE_JSON
    evidence_markdown_path: Path = DEFAULT_EVIDENCE_MARKDOWN
    poll_interval_seconds: float = 5.0
    timeout_seconds: float = 900.0
    http_timeout_seconds: float = 30.0
    qdrant_url: str = DEFAULT_QDRANT_URL
    qdrant_collection: str = DEFAULT_QDRANT_COLLECTION
    neo4j_uri: str = DEFAULT_NEO4J_URI
    neo4j_user: str = DEFAULT_NEO4J_USER
    neo4j_password: str = DEFAULT_NEO4J_PASSWORD
    neo4j_database: str = DEFAULT_NEO4J_DATABASE

    def public_targets(self) -> dict[str, str]:
        return {
            "java_base_url": self.java_base_url,
            "qdrant_url": self.qdrant_url,
            "qdrant_collection": self.qdrant_collection,
            "neo4j_uri": self.neo4j_uri,
            "neo4j_database": self.neo4j_database,
        }


class JavaDocumentApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 30.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        normalized = base_url.rstrip("/")
        self._api_prefix = "" if normalized.endswith("/api/v1") else "/api/v1"
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            base_url=normalized,
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> JavaDocumentApiClient:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def login(self, username: str, password: str) -> None:
        response = self._client.post(
            self._path("/auth/login"),
            json={"username": username, "password": password},
        )
        _raise_for_status(response, "login")

    def list_documents(self) -> tuple[JavaDocumentRecord, ...]:
        documents: list[JavaDocumentRecord] = []
        page = 0
        size = 100
        while True:
            response = self._client.get(self._path("/documents"), params={"page": page, "size": size})
            _raise_for_status(response, "list documents")
            payload = response.json()
            items = payload.get("items") if isinstance(payload, Mapping) else None
            if not isinstance(items, list):
                raise SeedCorpusError("Java document list response did not contain an items array")
            documents.extend(JavaDocumentRecord.from_payload(item) for item in items)
            total = int(payload.get("total") or len(documents))
            if len(documents) >= total or not items:
                break
            page += 1
        return tuple(documents)

    def get_document(self, document_id: str) -> JavaDocumentRecord:
        response = self._client.get(self._path(f"/documents/{document_id}"))
        _raise_for_status(response, f"get document {document_id}")
        return JavaDocumentRecord.from_payload(response.json())

    def delete_document(self, document_id: str) -> None:
        response = self._client.delete(self._path(f"/documents/{document_id}"))
        _raise_for_status(response, f"delete document {document_id}")

    def upload_document(self, manifest: CorpusManifest, entry: CorpusManifestEntry, corpus_dir: Path) -> JavaDocumentRecord:
        document_path = corpus_dir / entry.path
        if not document_path.is_file():
            raise SeedCorpusError(f"Corpus file not found: {document_path}")
        with document_path.open("rb") as handle:
            files = {"file": (document_path.name, handle, _content_type(document_path))}
            response = self._client.post(
                self._path("/documents"),
                data=build_upload_fields(manifest, entry),
                files=files,
            )
        _raise_for_status(response, f"upload {entry.doc_id}")
        return JavaDocumentRecord.from_payload(response.json())

    def _path(self, path: str) -> str:
        return f"{self._api_prefix}{path}"


def build_seed_marker(corpus_version: str, doc_id: str) -> str:
    return f"{SEED_MARKER_PREFIX}:{corpus_version.strip()}:{doc_id.strip()}"


def build_upload_fields(manifest: CorpusManifest, entry: CorpusManifestEntry) -> dict[str, str]:
    return {
        "title": entry.title,
        "accessLevel": entry.access_level,
        "department": entry.department,
        "docType": entry.doc_type,
        "language": entry.language,
        "description": build_seed_marker(manifest.corpus_version, entry.doc_id),
    }


def document_matches_seed_entry(
    document: JavaDocumentRecord | Mapping[str, Any],
    manifest: CorpusManifest,
    entry: CorpusManifestEntry,
) -> bool:
    marker = build_seed_marker(manifest.corpus_version, entry.doc_id)
    description = _document_value(document, "description")
    if description and marker in description:
        return True
    return (
        _document_value(document, "title") == entry.title
        and _document_value(document, "original_filename", "originalFilename") == Path(entry.path).name
        and _document_value(document, "access_level", "accessLevel") == entry.access_level
        and _document_value(document, "department") == entry.department
        and _document_value(document, "doc_type", "docType") == entry.doc_type
        and _document_value(document, "language") == entry.language
    )


def find_seed_documents(
    documents: Sequence[JavaDocumentRecord],
    manifest: CorpusManifest,
) -> dict[str, list[JavaDocumentRecord]]:
    matches: dict[str, list[JavaDocumentRecord]] = {entry.doc_id: [] for entry in manifest.documents}
    for document in documents:
        for entry in manifest.documents:
            if document_matches_seed_entry(document, manifest, entry):
                matches[entry.doc_id].append(document)
                break
    return matches


def poll_indexing_complete(
    client: Any,
    uploaded_by_doc_id: Mapping[str, JavaDocumentRecord],
    *,
    timeout_seconds: float,
    interval_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, JavaDocumentRecord]:
    deadline = monotonic() + timeout_seconds
    latest = dict(uploaded_by_doc_id)
    while True:
        failures: list[JavaDocumentRecord] = []
        all_indexed = True
        for manifest_doc_id, uploaded in uploaded_by_doc_id.items():
            current = client.get_document(uploaded.id)
            latest[manifest_doc_id] = current
            status = current.status.upper()
            if status == INDEXED_STATUS:
                continue
            all_indexed = False
            if status in FAILED_STATUSES:
                failures.append(current)

        if failures:
            details = ", ".join(
                f"{record.title or record.id}: {record.status}"
                + (f" ({record.failure_reason})" if record.failure_reason else "")
                for record in failures
            )
            raise SeedCorpusError(f"Seed indexing failed: {details}")
        if all_indexed:
            return latest
        if monotonic() >= deadline:
            statuses = ", ".join(f"{doc_id}={record.status}" for doc_id, record in latest.items())
            raise SeedCorpusError(f"Timed out waiting for seed indexing: {statuses}")
        sleep(max(interval_seconds, 0.0))


def build_document_id_map(
    manifest: CorpusManifest,
    records_by_doc_id: Mapping[str, JavaDocumentRecord],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for entry in manifest.documents:
        record = records_by_doc_id[entry.doc_id]
        rows.append(
            {
                "manifest_doc_id": entry.doc_id,
                "indexed_document_id": record.id,
                "title": record.title or entry.title,
            }
        )
    return rows


def write_seed_evidence(
    config: SeedRunConfig,
    manifest: CorpusManifest,
    records_by_doc_id: Mapping[str, JavaDocumentRecord],
    *,
    qdrant_check: StoreCheck,
    neo4j_check: StoreCheck,
    extra_java_documents: Sequence[JavaDocumentRecord] = (),
) -> dict[str, Any]:
    all_indexed = len(records_by_doc_id) == len(manifest.documents) and all(
        record.status.upper() == INDEXED_STATUS for record in records_by_doc_id.values()
    )
    success = all_indexed and qdrant_check.ok and neo4j_check.ok and not extra_java_documents
    payload: dict[str, Any] = {
        "success": success,
        "corpus_version": manifest.corpus_version,
        "document_count": len(records_by_doc_id),
        "expected_document_count": len(manifest.documents),
        "compose_targets": config.public_targets(),
        "document_id_map": build_document_id_map(manifest, records_by_doc_id),
        "java_documents": [
            records_by_doc_id[entry.doc_id].to_evidence(manifest_doc_id=entry.doc_id)
            for entry in manifest.documents
            if entry.doc_id in records_by_doc_id
        ],
        "non_seed_java_documents": [record.to_evidence() for record in extra_java_documents],
        "stores": {
            "qdrant": qdrant_check.to_dict(),
            "neo4j": neo4j_check.to_dict(),
        },
    }
    write_json(config.evidence_json_path, payload)
    config.evidence_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    config.evidence_markdown_path.write_text(render_markdown_evidence(payload), encoding="utf-8")
    return payload


def render_markdown_evidence(payload: Mapping[str, Any]) -> str:
    stores = payload.get("stores") if isinstance(payload.get("stores"), Mapping) else {}
    lines = [
        "# Phase 8 Seed Corpus Evidence",
        "",
        f"- Success: `{str(payload.get('success')).lower()}`",
        f"- Corpus version: `{payload.get('corpus_version')}`",
        f"- Documents: `{payload.get('document_count')}/{payload.get('expected_document_count', payload.get('document_count'))}`",
        "",
        "## Compose Targets",
        "",
    ]
    targets = payload.get("compose_targets") if isinstance(payload.get("compose_targets"), Mapping) else {}
    for key, value in targets.items():
        lines.append(f"- `{key}`: `{value}`")

    lines.extend(
        [
            "",
            "## Java Documents",
            "",
            "| Manifest ID | Java ID | Title | Status | Chunks | Indexed At |",
            "|-------------|---------|-------|--------|--------|------------|",
        ]
    )
    for document in payload.get("java_documents", []):
        if not isinstance(document, Mapping):
            continue
        lines.append(
            "| {manifest_doc_id} | {id} | {title} | {status} | {chunk_count} | {indexed_at} |".format(
                manifest_doc_id=document.get("manifest_doc_id", ""),
                id=document.get("id", ""),
                title=document.get("title", ""),
                status=document.get("status", ""),
                chunk_count=document.get("chunk_count", ""),
                indexed_at=document.get("indexed_at", ""),
            )
        )

    lines.extend(
        [
            "",
            "## Store Checks",
            "",
            "| Store | Status | OK | Details |",
            "|-------|--------|----|---------|",
        ]
    )
    for name in ("qdrant", "neo4j"):
        check = stores.get(name, {}) if isinstance(stores, Mapping) else {}
        details = check.get("details", {}) if isinstance(check, Mapping) else {}
        lines.append(
            f"| {name.capitalize()} | {check.get('status')} | {'yes' if check.get('ok') else 'no'} | "
            f"`{json.dumps(details, ensure_ascii=False, sort_keys=True)}` |"
        )

    extra = payload.get("non_seed_java_documents") or []
    if extra:
        lines.extend(["", "## Non-Seed Java Documents", ""])
        for document in extra:
            if isinstance(document, Mapping):
                lines.append(f"- `{document.get('id')}` {document.get('title')} ({document.get('status')})")
    lines.append("")
    return "\n".join(lines)


def check_qdrant_store(
    *,
    expected_document_ids: Sequence[str],
    qdrant_url: str,
    collection_name: str,
) -> StoreCheck:
    try:
        from qdrant_client import QdrantClient, models

        client = QdrantClient(url=qdrant_url)
        counts: Counter[str] = Counter()
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=collection_name,
                limit=256,
                offset=offset,
                with_payload=["documentId"],
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                document_id = payload.get("documentId")
                if document_id:
                    counts[str(document_id)] += 1
            if offset is None:
                break
        client.close()
    except Exception as exc:  # pragma: no cover - live dependency errors vary
        return StoreCheck(ok=False, status="blocked", details={"error": exc.__class__.__name__, "message": str(exc)})

    expected = set(expected_document_ids)
    actual = set(counts)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    ok = not missing and not extra and len(actual) == len(expected)
    return StoreCheck(
        ok=ok,
        status="passed" if ok else "failed",
        details={
            "document_count": len(actual),
            "point_count": sum(counts.values()),
            "missing_document_ids": missing,
            "extra_document_ids": extra,
            "points_by_document_id": dict(sorted(counts.items())),
        },
    )


def check_neo4j_store(
    *,
    records_by_doc_id: Mapping[str, JavaDocumentRecord],
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    neo4j_database: str,
) -> StoreCheck:
    try:
        from neo4j import GraphDatabase

        with GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password)) as driver:
            with driver.session(database=neo4j_database) as session:
                result = session.run(
                    """
                    MATCH (d:Document)
                    OPTIONAL MATCH (e:Entity)-[:MENTIONED_IN]->(d)
                    RETURN d.id AS document_id,
                           d.title AS title,
                           count(DISTINCT e) AS entity_count
                    ORDER BY d.id
                    """
                )
                rows = [dict(record) for record in result]
    except Exception as exc:  # pragma: no cover - live dependency errors vary
        return StoreCheck(ok=False, status="blocked", details={"error": exc.__class__.__name__, "message": str(exc)})

    expected_documents = [
        ExpectedDocument(document_id=record.id, title=record.title)
        for record in records_by_doc_id.values()
    ]
    java_documents = [
        JavaDocumentState(
            document_id=record.id,
            title=record.title,
            status=record.status,
            neo4j_entity_count=None,
        )
        for record in records_by_doc_id.values()
    ]
    report = compare_corpus_graph_state(
        expected_documents=expected_documents,
        neo4j_documents=rows,
        java_documents=java_documents,
    )
    return StoreCheck(ok=report.ok, status="passed" if report.ok else "failed", details=report.to_dict())


def run_seed_reset(config: SeedRunConfig) -> dict[str, Any]:
    manifest = load_manifest(config.manifest_path)
    if len(manifest.documents) != EXPECTED_DEMO_DOCUMENT_COUNT:
        raise SeedCorpusError(
            f"Demo seed reset requires exactly {EXPECTED_DEMO_DOCUMENT_COUNT} manifest documents, "
            f"found {len(manifest.documents)}"
        )
    if not config.password:
        raise SeedCorpusError("Admin password is required via --password or DEMO_ADMIN_PASSWORD")

    with JavaDocumentApiClient(config.java_base_url, timeout_seconds=config.http_timeout_seconds) as client:
        client.login(config.username, config.password)
        existing_documents = client.list_documents()
        existing_seed_docs = find_seed_documents(existing_documents, manifest)
        for documents in existing_seed_docs.values():
            for document in documents:
                client.delete_document(document.id)

        uploaded: dict[str, JavaDocumentRecord] = {}
        for entry in manifest.documents:
            uploaded[entry.doc_id] = client.upload_document(manifest, entry, config.corpus_dir)

        indexed = poll_indexing_complete(
            client,
            uploaded,
            timeout_seconds=config.timeout_seconds,
            interval_seconds=config.poll_interval_seconds,
        )
        final_documents = client.list_documents()

    seed_ids = {record.id for record in indexed.values()}
    extra_documents = tuple(record for record in final_documents if record.id not in seed_ids)
    indexed_document_ids = [record.id for record in indexed.values()]
    qdrant_check = check_qdrant_store(
        expected_document_ids=indexed_document_ids,
        qdrant_url=config.qdrant_url,
        collection_name=config.qdrant_collection,
    )
    neo4j_check = check_neo4j_store(
        records_by_doc_id=indexed,
        neo4j_uri=config.neo4j_uri,
        neo4j_user=config.neo4j_user,
        neo4j_password=config.neo4j_password,
        neo4j_database=config.neo4j_database,
    )
    return write_seed_evidence(
        config,
        manifest,
        indexed,
        qdrant_check=qdrant_check,
        neo4j_check=neo4j_check,
        extra_java_documents=extra_documents,
    )


def parse_args(argv: Sequence[str] | None = None) -> SeedRunConfig:
    parser = argparse.ArgumentParser(
        description="Reset the Phase 8 demo corpus through the Java document API and write seed evidence."
    )
    parser.add_argument("--java-base-url", default=os.getenv("DEMO_JAVA_BASE_URL", DEFAULT_JAVA_BASE_URL))
    parser.add_argument("--username", default=os.getenv("DEMO_ADMIN_USERNAME", "admin"))
    parser.add_argument("--password", default=os.getenv("DEMO_ADMIN_PASSWORD"))
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--evidence-json", type=Path, default=DEFAULT_EVIDENCE_JSON)
    parser.add_argument("--evidence-markdown", type=Path, default=DEFAULT_EVIDENCE_MARKDOWN)
    parser.add_argument("--poll-interval-seconds", type=float, default=5.0)
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument("--http-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--qdrant-url", default=os.getenv("QDRANT_URL", DEFAULT_QDRANT_URL))
    parser.add_argument("--qdrant-collection", default=os.getenv("QDRANT_COLLECTION", DEFAULT_QDRANT_COLLECTION))
    parser.add_argument("--neo4j-uri", default=os.getenv("NEO4J_URI", DEFAULT_NEO4J_URI))
    parser.add_argument("--neo4j-user", default=os.getenv("NEO4J_USER", DEFAULT_NEO4J_USER))
    parser.add_argument("--neo4j-password", default=os.getenv("NEO4J_PASSWORD", DEFAULT_NEO4J_PASSWORD))
    parser.add_argument("--neo4j-database", default=os.getenv("NEO4J_DATABASE", DEFAULT_NEO4J_DATABASE))
    args = parser.parse_args(argv)
    return SeedRunConfig(
        java_base_url=args.java_base_url,
        username=args.username,
        password=args.password,
        corpus_dir=args.corpus_dir,
        manifest_path=args.manifest_path,
        evidence_json_path=args.evidence_json,
        evidence_markdown_path=args.evidence_markdown,
        poll_interval_seconds=args.poll_interval_seconds,
        timeout_seconds=args.timeout_seconds,
        http_timeout_seconds=args.http_timeout_seconds,
        qdrant_url=args.qdrant_url,
        qdrant_collection=args.qdrant_collection,
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        neo4j_database=args.neo4j_database,
    )


def main(argv: Sequence[str] | None = None) -> int:
    config = parse_args(argv)
    try:
        evidence = run_seed_reset(config)
    except SeedCorpusError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"Wrote seed evidence: {config.evidence_json_path}")
    print(f"Wrote seed evidence: {config.evidence_markdown_path}")
    return 0 if evidence.get("success") else 1


def _raise_for_status(response: httpx.Response, operation: str) -> None:
    if response.status_code < 400:
        return
    try:
        payload = response.json()
    except ValueError:
        payload = {"detail": response.text}
    detail = payload.get("detail") or payload.get("title") or response.reason_phrase
    error_code = payload.get("errorCode")
    suffix = f" ({error_code})" if error_code else ""
    raise SeedCorpusError(f"Java API {operation} failed with HTTP {response.status_code}{suffix}: {detail}")


def _content_type(path: Path) -> str:
    return "text/markdown; charset=utf-8" if path.suffix.lower() in {".md", ".markdown"} else "application/octet-stream"


def _document_value(document: JavaDocumentRecord | Mapping[str, Any], *names: str) -> str | None:
    if isinstance(document, JavaDocumentRecord):
        for name in names:
            value = getattr(document, name, None)
            if value is not None:
                return str(value)
        return None
    return _optional_string(document, *names)


def _first_present(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    raise ValueError(f"row must contain one of: {', '.join(keys)}")


def _optional_string(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        if key in row and row[key] is not None:
            return str(row[key])
    return None


def _optional_int(row: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = row.get(key)
        if value is not None:
            return int(value)
    return None


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            if any(token in key_text.lower() for token in ("password", "secret", "token", "key")):
                result[key_text] = "[redacted]"
            else:
                result[key_text] = _redact(nested)
        return result
    if isinstance(value, list | tuple):
        return [_redact(item) for item in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
