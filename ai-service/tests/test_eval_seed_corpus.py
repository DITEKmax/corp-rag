from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.schema import CorpusManifest
from eval.seed_corpus import (
    JavaDocumentRecord,
    SeedCorpusError,
    SeedRunConfig,
    StoreCheck,
    build_document_id_map,
    build_seed_marker,
    build_upload_fields,
    document_matches_seed_entry,
    poll_indexing_complete,
    render_markdown_evidence,
    write_seed_evidence,
)


def _manifest() -> CorpusManifest:
    return CorpusManifest.model_validate(
        {
            "corpus_version": "ru-demo-v1",
            "language": "ru",
            "documents": [
                {
                    "doc_id": "CORP-RU-001",
                    "title": "Регламент передачи рейса",
                    "path": "documents/flight.md",
                    "language": "ru",
                    "department": "OPS",
                    "doc_type": "POLICY",
                    "access_level": "INTERNAL",
                    "summary": "Правила передачи рейса.",
                },
                {
                    "doc_id": "CORP-RU-002",
                    "title": "Памятка по грузу",
                    "path": "documents/cargo.md",
                    "language": "ru",
                    "department": "LOGISTICS",
                    "doc_type": "GUIDE",
                    "access_level": "PUBLIC",
                    "summary": "Правила обработки груза.",
                },
            ],
        }
    )


def test_marker_and_metadata_preserve_manifest_identity() -> None:
    manifest = _manifest()
    entry = manifest.documents[0]

    marker = build_seed_marker(manifest.corpus_version, entry.doc_id)
    fields = build_upload_fields(manifest, entry)

    assert marker == "corp-rag-demo-seed:ru-demo-v1:CORP-RU-001"
    assert fields == {
        "title": "Регламент передачи рейса",
        "accessLevel": "INTERNAL",
        "department": "OPS",
        "docType": "POLICY",
        "language": "ru",
        "description": "corp-rag-demo-seed:ru-demo-v1:CORP-RU-001",
    }


def test_document_matching_uses_description_marker_or_exact_seed_metadata() -> None:
    manifest = _manifest()
    entry = manifest.documents[0]

    by_marker = {
        "title": "Old title",
        "originalFilename": "old.md",
        "description": f"previous {build_seed_marker(manifest.corpus_version, entry.doc_id)}",
    }
    by_metadata = {
        "title": entry.title,
        "originalFilename": "flight.md",
        "description": "",
        "accessLevel": entry.access_level,
        "department": entry.department,
        "docType": entry.doc_type,
        "language": entry.language,
    }
    wrong_department = {**by_metadata, "department": "HR"}

    assert document_matches_seed_entry(by_marker, manifest, entry) is True
    assert document_matches_seed_entry(by_metadata, manifest, entry) is True
    assert document_matches_seed_entry(wrong_department, manifest, entry) is False


def test_polling_accepts_all_indexed_and_surfaces_failures() -> None:
    pending = JavaDocumentRecord(
        id="doc-1",
        title="Регламент передачи рейса",
        status="UPLOADED",
        chunk_count=None,
        indexed_at=None,
        failure_reason=None,
    )
    indexed = JavaDocumentRecord(
        id="doc-1",
        title="Регламент передачи рейса",
        status="INDEXED",
        chunk_count=4,
        indexed_at="2026-06-01T10:00:00Z",
        failure_reason=None,
    )

    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        def get_document(self, document_id: str) -> JavaDocumentRecord:
            self.calls += 1
            assert document_id == "doc-1"
            return indexed if self.calls > 1 else pending

    records = poll_indexing_complete(
        FakeClient(),
        {"CORP-RU-001": pending},
        timeout_seconds=1,
        interval_seconds=0,
        sleep=lambda _: None,
    )

    assert records["CORP-RU-001"].status == "INDEXED"
    assert records["CORP-RU-001"].chunk_count == 4


def test_polling_raises_on_failed_indexing() -> None:
    failed = JavaDocumentRecord(
        id="doc-1",
        title="Регламент передачи рейса",
        status="INDEXING_FAILED",
        chunk_count=None,
        indexed_at=None,
        failure_reason="parser failed",
    )

    class FakeClient:
        def get_document(self, document_id: str) -> JavaDocumentRecord:
            return failed

    with pytest.raises(SeedCorpusError, match="parser failed"):
        poll_indexing_complete(
            FakeClient(),
            {"CORP-RU-001": failed},
            timeout_seconds=1,
            interval_seconds=0,
            sleep=lambda _: None,
        )


def test_evidence_output_contains_ids_statuses_store_checks_and_no_secrets(tmp_path: Path) -> None:
    manifest = _manifest()
    config = SeedRunConfig(
        java_base_url="http://localhost:8080",
        username="admin",
        password="super-secret-password",
        corpus_dir=tmp_path / "corpus",
        manifest_path=tmp_path / "manifest.json",
        evidence_json_path=tmp_path / "seed.json",
        evidence_markdown_path=tmp_path / "seed.md",
    )
    records = {
        "CORP-RU-001": JavaDocumentRecord(
            id="doc-1",
            title="Регламент передачи рейса",
            status="INDEXED",
            chunk_count=4,
            indexed_at="2026-06-01T10:00:00Z",
            failure_reason=None,
        ),
        "CORP-RU-002": JavaDocumentRecord(
            id="doc-2",
            title="Памятка по грузу",
            status="INDEXED",
            chunk_count=3,
            indexed_at="2026-06-01T10:01:00Z",
            failure_reason=None,
        ),
    }

    payload = write_seed_evidence(
        config,
        manifest,
        records,
        qdrant_check=StoreCheck(ok=True, status="passed", details={"document_count": 2, "point_count": 7}),
        neo4j_check=StoreCheck(ok=True, status="passed", details={"document_count": 2, "missing": []}),
    )

    written = json.loads(config.evidence_json_path.read_text(encoding="utf-8"))
    markdown = config.evidence_markdown_path.read_text(encoding="utf-8")

    assert build_document_id_map(manifest, records) == [
        {"manifest_doc_id": "CORP-RU-001", "indexed_document_id": "doc-1", "title": "Регламент передачи рейса"},
        {"manifest_doc_id": "CORP-RU-002", "indexed_document_id": "doc-2", "title": "Памятка по грузу"},
    ]
    assert payload["success"] is True
    assert written["java_documents"][0]["chunk_count"] == 4
    assert "super-secret-password" not in json.dumps(written, ensure_ascii=False)
    assert "doc-1" in markdown
    assert "Qdrant" in markdown
    assert "Neo4j" in markdown


def test_render_markdown_marks_blocked_store_checks() -> None:
    manifest = _manifest()
    markdown = render_markdown_evidence(
        {
            "success": False,
            "corpus_version": manifest.corpus_version,
            "document_count": 2,
            "compose_targets": {"java_base_url": "http://localhost:8080"},
            "java_documents": [],
            "stores": {
                "qdrant": {"ok": False, "status": "blocked", "details": {"error": "connection refused"}},
                "neo4j": {"ok": True, "status": "passed", "details": {}},
            },
        }
    )

    assert "| Qdrant | blocked | no |" in markdown
    assert "connection refused" in markdown
