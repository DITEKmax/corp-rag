from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from corp_rag_ai.contracts.generated import ai_service_v1 as contract


@dataclass(frozen=True, slots=True)
class ChunkDetailRecord:
    document_id: UUID
    chunk_id: UUID
    parent_chunk_id: UUID | None
    content: str
    page_number: int | None
    section_path: tuple[str, ...]
    language: str
    access_level: str
    department: str
    doc_type: str


class ChunkDetailService(Protocol):
    async def get_chunk_detail(self, document_id: UUID, chunk_id: UUID) -> ChunkDetailRecord | None:
        ...


router = APIRouter(tags=["chunks"])


@router.get("/v1/documents/{document_id}/chunks/{chunk_id}")
async def get_chunk_detail(document_id: UUID, chunk_id: UUID, request: Request) -> contract.ChunkDetail:
    service = getattr(request.app.state, "chunk_detail_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="chunk detail service is not configured")
    detail = await service.get_chunk_detail(document_id, chunk_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="chunk not found")
    return chunk_detail_to_contract(detail)


def chunk_detail_to_contract(detail: ChunkDetailRecord) -> contract.ChunkDetail:
    return contract.ChunkDetail(
        documentId=detail.document_id,
        chunkId=detail.chunk_id,
        parentChunkId=detail.parent_chunk_id,
        content=detail.content,
        pageNumber=detail.page_number,
        sectionTitle=detail.section_path[-1] if detail.section_path else None,
        language=contract.Language(detail.language),
        accessLevel=contract.AccessLevel(detail.access_level),
        department=detail.department,
        docType=contract.DocType(detail.doc_type),
    )


def chunk_detail_from_payload(payload: dict[str, object], *, parent_content: str | None = None) -> ChunkDetailRecord:
    return ChunkDetailRecord(
        document_id=UUID(str(payload["documentId"])),
        chunk_id=UUID(str(payload["chunkId"])),
        parent_chunk_id=UUID(str(payload["parentChunkId"])) if payload.get("parentChunkId") else None,
        content=parent_content or str(payload.get("content", "")),
        page_number=int(payload["page"]) if payload.get("page") is not None else None,
        section_path=tuple(str(part) for part in payload.get("sectionPath", []) or []),
        language=str(payload.get("language", "en")),
        access_level=str(payload.get("accessLevel", "PUBLIC")),
        department=str(payload.get("department", "")),
        doc_type=str(payload.get("docType", "OTHER")),
    )
