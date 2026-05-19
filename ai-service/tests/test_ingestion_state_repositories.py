from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from corp_rag_ai.domain.ingestion_state import IndexStatus, ParentChunkRecord
from corp_rag_ai.repositories.ingestion_state import (
    DocumentIndexStateRepository,
    ParentChunkRepository,
    ProcessedEventRepository,
)
from corp_rag_ai.repositories.tables import document_chunks_parent, document_index_state, processed_events


class _ScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _MappingResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self):
        return self

    def all(self) -> list[dict[str, object]]:
        return self._rows


class _FakeDb:
    def __init__(
        self,
        *,
        scalar: object | None = None,
        rows: list[dict[str, object]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.scalar = scalar
        self.rows = rows
        self.error = error
        self.calls: list[tuple[object, object | None]] = []

    async def execute(self, statement: object, params: object | None = None) -> _ScalarResult | _MappingResult:
        self.calls.append((statement, params))
        if self.error is not None:
            raise self.error
        if self.rows is not None:
            return _MappingResult(self.rows)
        return _ScalarResult(self.scalar)


def _compiled_params(statement: object) -> dict[str, object]:
    return statement.compile(dialect=postgresql.dialect()).params


def test_ingestion_tables_match_locked_schema() -> None:
    assert set(processed_events.c.keys()) == {"event_id", "event_type", "consumed_at"}
    assert processed_events.c.event_type.type.length == 64

    assert set(document_index_state.c.keys()) == {
        "document_id",
        "status",
        "last_indexed_event_id",
        "last_failure_stage",
        "last_failure_code",
        "last_failure_at",
        "created_at",
        "updated_at",
    }
    java_owned_metadata = {
        "title",
        "owner_user_id",
        "content_sha256",
        "access_level",
        "department",
        "doc_type",
        "language",
        "mime_type",
        "size_bytes",
        "original_filename",
        "uploaded_at",
    }
    assert java_owned_metadata.isdisjoint(document_index_state.c.keys())

    document_id_indexes = [
        index for index in document_chunks_parent.indexes if "document_id" in index.columns.keys()
    ]
    assert len(document_id_indexes) == 1
    assert document_id_indexes[0].unique is False


@pytest.mark.asyncio
async def test_processed_event_duplicate_check_uses_event_id() -> None:
    event_id = uuid4()
    existing = ProcessedEventRepository(_FakeDb(scalar=event_id))
    missing = ProcessedEventRepository(_FakeDb(scalar=None))

    assert await existing.has_processed(event_id) is True
    assert await missing.has_processed(event_id) is False


@pytest.mark.asyncio
async def test_processed_event_terminal_insert_reports_unique_conflict() -> None:
    event_id = uuid4()
    duplicate_db = _FakeDb(error=IntegrityError("insert", {}, Exception("duplicate key")))
    repo = ProcessedEventRepository(duplicate_db)

    assert await repo.insert_terminal(event_id, "document.indexed") is False


@pytest.mark.asyncio
async def test_document_state_repository_builds_indexing_and_failed_upserts() -> None:
    document_id = uuid4()
    failed_at = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    db = _FakeDb()
    repo = DocumentIndexStateRepository(db)

    await repo.mark_indexing(document_id)
    await repo.mark_failed(document_id, "PARSING", "INVALID_FILE_FORMAT", failed_at)

    indexing_params = _compiled_params(db.calls[0][0])
    failed_params = _compiled_params(db.calls[1][0])

    assert indexing_params["document_id"] == document_id
    assert indexing_params["status"] == IndexStatus.INDEXING.value
    assert indexing_params["last_failure_stage"] is None
    assert failed_params["status"] == IndexStatus.FAILED.value
    assert failed_params["last_failure_stage"] == "PARSING"
    assert failed_params["last_failure_code"] == "INVALID_FILE_FORMAT"
    assert failed_params["last_failure_at"] == failed_at


@pytest.mark.asyncio
async def test_document_state_repository_builds_indexed_and_deleted_tombstone_upserts() -> None:
    document_id = uuid4()
    event_id = uuid4()
    db = _FakeDb()
    repo = DocumentIndexStateRepository(db)

    await repo.mark_indexed(document_id, event_id)
    await repo.mark_deleted(document_id)

    indexed_params = _compiled_params(db.calls[0][0])
    deleted_params = _compiled_params(db.calls[1][0])

    assert indexed_params["status"] == IndexStatus.INDEXED.value
    assert indexed_params["last_indexed_event_id"] == event_id
    assert deleted_params["document_id"] == document_id
    assert deleted_params["status"] == IndexStatus.DELETED.value
    assert deleted_params["last_indexed_event_id"] is None


@pytest.mark.asyncio
async def test_parent_chunk_repository_replaces_document_rows() -> None:
    document_id = uuid4()
    chunk = ParentChunkRecord(
        parent_chunk_id=uuid4(),
        document_id=document_id,
        section_path=("HR", "Vacations"),
        content="Policy body",
        position=0,
        token_count=17,
    )
    db = _FakeDb()
    repo = ParentChunkRepository(db)

    await repo.replace_for_document(document_id, [chunk])

    delete_statement, delete_params = db.calls[0]
    insert_statement, inserted_rows = db.calls[1]
    assert delete_params is None
    assert "DELETE FROM document_chunks_parent" in str(delete_statement.compile(dialect=postgresql.dialect()))
    assert insert_statement.table.name == "document_chunks_parent"
    assert inserted_rows == [
        {
            "parent_chunk_id": chunk.parent_chunk_id,
            "document_id": document_id,
            "section_path": ["HR", "Vacations"],
            "content": "Policy body",
            "position": 0,
            "token_count": 17,
        }
    ]


@pytest.mark.asyncio
async def test_parent_chunk_repository_reads_by_parent_ids_and_document_id() -> None:
    document_id = uuid4()
    parent_id = uuid4()
    row = {
        "parent_chunk_id": parent_id,
        "document_id": document_id,
        "section_path": ["HR", "Vacations"],
        "content": "Policy body",
        "position": 2,
        "token_count": 17,
    }
    db = _FakeDb(rows=[row])
    repo = ParentChunkRepository(db)

    by_parent = await repo.get_by_parent_ids((parent_id, parent_id))
    by_document = await repo.list_by_document(document_id)

    assert tuple(by_parent) == (parent_id,)
    assert by_parent[parent_id].content == "Policy body"
    assert by_parent[parent_id].section_path == ("HR", "Vacations")
    assert by_document[0].parent_chunk_id == parent_id
    assert "parent_chunk_id IN" in str(db.calls[0][0].compile(dialect=postgresql.dialect()))
    assert "ORDER BY document_chunks_parent.position" in str(db.calls[1][0].compile(dialect=postgresql.dialect()))
