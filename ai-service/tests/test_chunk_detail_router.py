from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from corp_rag_ai.adapters.rest.chunks import ChunkDetailRecord, chunk_detail_from_payload, router


DOCUMENT_ID = UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
CHUNK_ID = UUID("11111111-1111-4111-8111-111111111042")
PARENT_ID = UUID("22222222-2222-4222-8222-222222222017")


def test_chunk_detail_route_maps_internal_record_to_contract_response() -> None:
    app = FastAPI()
    app.include_router(router)
    app.state.chunk_detail_service = _ChunkService(
        ChunkDetailRecord(
            document_id=DOCUMENT_ID,
            chunk_id=CHUNK_ID,
            parent_chunk_id=PARENT_ID,
            content="Parent context body",
            page_number=4,
            section_path=("HR", "Leave"),
            language="en",
            access_level="INTERNAL",
            department="HR",
            doc_type="POLICY",
        )
    )

    response = TestClient(app).get(f"/v1/documents/{DOCUMENT_ID}/chunks/{CHUNK_ID}")

    assert response.status_code == 200
    assert response.json() == {
        "documentId": str(DOCUMENT_ID),
        "chunkId": str(CHUNK_ID),
        "parentChunkId": str(PARENT_ID),
        "content": "Parent context body",
        "pageNumber": 4,
        "sectionTitle": "Leave",
        "language": "en",
        "accessLevel": "INTERNAL",
        "department": "HR",
        "docType": "POLICY",
    }


def test_chunk_detail_route_returns_404_for_missing_chunk() -> None:
    app = FastAPI()
    app.include_router(router)
    app.state.chunk_detail_service = _ChunkService(None)

    response = TestClient(app).get(f"/v1/documents/{DOCUMENT_ID}/chunks/{CHUNK_ID}")

    assert response.status_code == 404


def test_chunk_detail_from_payload_prefers_parent_content_when_available() -> None:
    detail = chunk_detail_from_payload(
        {
            "documentId": str(DOCUMENT_ID),
            "chunkId": str(CHUNK_ID),
            "parentChunkId": str(PARENT_ID),
            "content": "Child content",
            "page": 4,
            "sectionPath": ["HR", "Leave"],
            "language": "en",
            "accessLevel": "INTERNAL",
            "department": "HR",
            "docType": "POLICY",
        },
        parent_content="Parent content",
    )

    assert detail.content == "Parent content"
    assert detail.section_path == ("HR", "Leave")
    assert detail.parent_chunk_id == PARENT_ID


class _ChunkService:
    def __init__(self, detail: ChunkDetailRecord | None) -> None:
        self.detail = detail

    async def get_chunk_detail(self, document_id: UUID, chunk_id: UUID) -> ChunkDetailRecord | None:
        assert document_id == DOCUMENT_ID
        assert chunk_id == CHUNK_ID
        return self.detail
