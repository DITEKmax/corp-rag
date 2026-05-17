from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from corp_rag_ai.domain.ingestion_state import ParentChunkRecord


@dataclass(frozen=True, slots=True)
class ParentChunk:
    parent_chunk_id: UUID
    document_id: UUID
    section_path: tuple[str, ...]
    content: str
    position: int
    token_count: int
    source_block_positions: tuple[int, ...]
    warnings: tuple[str, ...] = ()

    def to_record(self) -> ParentChunkRecord:
        return ParentChunkRecord(
            parent_chunk_id=self.parent_chunk_id,
            document_id=self.document_id,
            section_path=self.section_path,
            content=self.content,
            position=self.position,
            token_count=self.token_count,
        )


@dataclass(frozen=True, slots=True)
class ChildChunk:
    chunk_id: UUID
    parent_chunk_id: UUID
    document_id: UUID
    section_path: tuple[str, ...]
    content: str
    content_for_embedding: str
    position: int
    position_in_parent: int
    token_count: int
    page: int | None = None
    warnings: tuple[str, ...] = ()

    def to_qdrant_payload(
        self,
        *,
        document_title: str,
        language: str,
        doc_type: str,
        department: str,
        access_level: str,
        is_sanitized: bool = True,
        sanitizer_flags: tuple[str, ...] = (),
    ) -> dict[str, object]:
        return {
            "chunkId": str(self.chunk_id),
            "parentChunkId": str(self.parent_chunk_id),
            "documentId": str(self.document_id),
            "documentTitle": document_title,
            "sectionPath": list(self.section_path),
            "position": self.position,
            "page": self.page,
            "content": self.content,
            "language": language,
            "docType": doc_type,
            "department": department,
            "accessLevel": access_level,
            "isSanitized": is_sanitized,
            "sanitizerFlags": list(sanitizer_flags),
        }


@dataclass(frozen=True, slots=True)
class ChunkingResult:
    parents: tuple[ParentChunk, ...]
    children: tuple[ChildChunk, ...]
    warnings: tuple[str, ...] = ()

    def parent_records(self) -> tuple[ParentChunkRecord, ...]:
        return tuple(parent.to_record() for parent in self.parents)
