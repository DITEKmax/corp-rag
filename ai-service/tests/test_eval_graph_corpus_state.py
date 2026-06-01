from __future__ import annotations

import json

from eval.graph_corpus_state import ExpectedDocument, compare_corpus_graph_state, load_expected_documents


def test_load_expected_documents_reads_golden_metadata_map(tmp_path) -> None:
    metadata_path = tmp_path / "golden_ru.meta.json"
    metadata_path.write_text(
        json.dumps(
            {
                "indexed_document_ids": ["doc-a", "doc-b"],
                "indexed_document_map": [
                    {
                        "manifest_doc_id": "CORP-RU-001",
                        "indexed_document_id": "doc-b",
                        "title": "Документ Б",
                    },
                    {
                        "manifest_doc_id": "CORP-RU-002",
                        "indexed_document_id": "doc-a",
                        "title": "Документ А",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    assert load_expected_documents(metadata_path) == (
        ExpectedDocument(document_id="doc-a", title="Документ А"),
        ExpectedDocument(document_id="doc-b", title="Документ Б"),
    )


def test_compare_corpus_graph_state_reports_missing_extra_and_zero_counts() -> None:
    report = compare_corpus_graph_state(
        expected_documents=(
            ExpectedDocument(document_id="doc-a", title="Документ А"),
            ExpectedDocument(document_id="doc-b", title="Документ Б"),
            ExpectedDocument(document_id="doc-c", title="Документ В"),
        ),
        neo4j_documents=[
            {"id": "doc-a", "title": "Документ А", "entity_count": 2, "relation_count": 1, "mention_count": 3},
            {"documentId": "doc-b", "title": "Документ Б", "entityCount": 0},
            {"document_id": "stale-doc", "title": "Старый документ", "entities": 4},
        ],
    )

    assert not report.ok
    assert [item.document_id for item in report.missing] == ["doc-c"]
    assert [item.document_id for item in report.extra] == ["stale-doc"]
    assert [item.document_id for item in report.entity_count_zero] == ["doc-b"]
    assert report.to_dict()["missing"] == [{"document_id": "doc-c", "title": "Документ В"}]


def test_compare_corpus_graph_state_cross_checks_java_rows() -> None:
    report = compare_corpus_graph_state(
        expected_documents=(
            ExpectedDocument(document_id="doc-a", title="Документ А"),
            ExpectedDocument(document_id="doc-b", title="Документ Б"),
            ExpectedDocument(document_id="doc-c", title="Документ В"),
        ),
        neo4j_documents=[
            {"id": "doc-a", "title": "Документ А", "entity_count": 2},
            {"id": "doc-b", "title": "Документ Б", "entity_count": 1},
            {"id": "doc-c", "title": "Документ В", "entity_count": 3},
        ],
        java_documents=[
            {"id": "doc-a", "title": "Документ А", "status": "INDEXED", "neo4j_entity_count": 2},
            {"id": "doc-b", "title": "Документ Б", "status": "INDEXING_FAILED", "neo4j_entity_count": 0},
        ],
    )

    assert [item.document_id for item in report.java_missing] == ["doc-c"]
    assert [item.document_id for item in report.java_entity_count_zero] == ["doc-b"]
    assert [item.document_id for item in report.java_status_not_indexed] == ["doc-b"]
    assert report.java_neo4j_count_mismatch == (
        {
            "document_id": "doc-b",
            "title": "Документ Б",
            "neo4j_entity_count": 1,
            "java_neo4j_entity_count": 0,
        },
    )
