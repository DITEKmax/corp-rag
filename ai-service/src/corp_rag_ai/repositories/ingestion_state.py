from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from corp_rag_ai.domain.ingestion_state import DocumentIndexState, IndexStatus, ParentChunkRecord
from corp_rag_ai.repositories.tables import document_chunks_parent, document_index_state, processed_events


class ProcessedEventRepository:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def has_processed(self, event_id: UUID) -> bool:
        statement = (
            sa.select(processed_events.c.event_id)
            .where(processed_events.c.event_id == event_id)
            .limit(1)
        )
        result = await self._db.execute(statement)
        return result.scalar_one_or_none() is not None

    async def insert_terminal(self, event_id: UUID, event_type: str) -> bool:
        statement = processed_events.insert().values(event_id=event_id, event_type=event_type)
        try:
            await self._db.execute(statement)
        except IntegrityError:
            return False
        return True


class DocumentIndexStateRepository:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def get(self, document_id: UUID) -> DocumentIndexState | None:
        statement = sa.select(document_index_state).where(document_index_state.c.document_id == document_id)
        result = await self._db.execute(statement)
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return DocumentIndexState(
            document_id=row["document_id"],
            status=IndexStatus(row["status"]),
            last_indexed_event_id=row["last_indexed_event_id"],
            last_failure_stage=row["last_failure_stage"],
            last_failure_code=row["last_failure_code"],
            last_failure_at=row["last_failure_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def mark_indexing(self, document_id: UUID) -> None:
        await self._upsert_state(
            document_id,
            status=IndexStatus.INDEXING,
            last_indexed_event_id=None,
            last_failure_stage=None,
            last_failure_code=None,
            last_failure_at=None,
        )

    async def mark_indexed(self, document_id: UUID, event_id: UUID) -> None:
        await self._upsert_state(
            document_id,
            status=IndexStatus.INDEXED,
            last_indexed_event_id=event_id,
            last_failure_stage=None,
            last_failure_code=None,
            last_failure_at=None,
        )

    async def mark_failed(
        self,
        document_id: UUID,
        stage: str,
        error_code: str,
        failed_at: datetime | None = None,
    ) -> None:
        await self._upsert_state(
            document_id,
            status=IndexStatus.FAILED,
            last_indexed_event_id=None,
            last_failure_stage=stage,
            last_failure_code=error_code,
            last_failure_at=failed_at or datetime.now(UTC),
        )

    async def mark_deleted(self, document_id: UUID) -> None:
        await self._upsert_state(
            document_id,
            status=IndexStatus.DELETED,
            last_indexed_event_id=None,
            last_failure_stage=None,
            last_failure_code=None,
            last_failure_at=None,
        )

    async def _upsert_state(
        self,
        document_id: UUID,
        *,
        status: IndexStatus,
        last_indexed_event_id: UUID | None,
        last_failure_stage: str | None,
        last_failure_code: str | None,
        last_failure_at: datetime | None,
    ) -> None:
        values = {
            "document_id": document_id,
            "status": status.value,
            "last_indexed_event_id": last_indexed_event_id,
            "last_failure_stage": last_failure_stage,
            "last_failure_code": last_failure_code,
            "last_failure_at": last_failure_at,
        }
        statement = insert(document_index_state).values(**values)
        update_values = {
            **values,
            "updated_at": sa.func.now(),
        }
        update_values.pop("document_id")
        await self._db.execute(
            statement.on_conflict_do_update(
                index_elements=[document_index_state.c.document_id],
                set_=update_values,
            )
        )


class ParentChunkRepository:
    def __init__(self, db: Any) -> None:
        self._db = db

    async def replace_for_document(self, document_id: UUID, chunks: Sequence[ParentChunkRecord]) -> None:
        await self.delete_by_document(document_id)
        if not chunks:
            return
        rows = [
            {
                "parent_chunk_id": chunk.parent_chunk_id,
                "document_id": chunk.document_id,
                "section_path": list(chunk.section_path),
                "content": chunk.content,
                "position": chunk.position,
                "token_count": chunk.token_count,
            }
            for chunk in chunks
        ]
        await self._db.execute(document_chunks_parent.insert(), rows)

    async def delete_by_document(self, document_id: UUID) -> None:
        statement = document_chunks_parent.delete().where(document_chunks_parent.c.document_id == document_id)
        await self._db.execute(statement)

