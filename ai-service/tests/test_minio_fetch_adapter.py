from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from corp_rag_ai.adapters.amqp.messages import InboundEvent, EventMetadata
from corp_rag_ai.adapters.minio import MinioDocumentStore, MinioObjectNotFound, MinioObjectRef
from corp_rag_ai.domain.exceptions import DEPENDENCY_UNAVAILABLE, IndexingStage, StageFailure
from corp_rag_ai.pipeline.ingestion.events import uploaded_metadata_from_event


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body
        self.closed = False
        self.released = False

    def read(self) -> bytes:
        return self._body

    def close(self) -> None:
        self.closed = True

    def release_conn(self) -> None:
        self.released = True


class _Client:
    def __init__(self, response: _Response | None = None, error: Exception | None = None) -> None:
        self.response = response or _Response(b"document bytes")
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def get_object(self, bucket: str, key: str) -> _Response:
        self.calls.append((bucket, key))
        if self.error is not None:
            raise self.error
        return self.response


class _MinioError(Exception):
    def __init__(self, *, status_code: int | None = None, code: str = "") -> None:
        super().__init__(code or str(status_code))
        self.status_code = status_code
        self.code = code


@pytest.mark.asyncio
async def test_minio_fetch_uses_payload_bucket_key_and_releases_response() -> None:
    response = _Response(b"source")
    client = _Client(response=response)
    store = MinioDocumentStore(client)

    fetched = await store.fetch(MinioObjectRef(bucket="docs", key="2026/file.pdf"))

    assert fetched.body == b"source"
    assert fetched.object_ref == MinioObjectRef(bucket="docs", key="2026/file.pdf")
    assert client.calls == [("docs", "2026/file.pdf")]
    assert response.closed is True
    assert response.released is True


@pytest.mark.asyncio
async def test_minio_fetch_maps_404_to_delete_race_signal() -> None:
    store = MinioDocumentStore(_Client(error=_MinioError(status_code=404, code="NoSuchKey")))

    with pytest.raises(MinioObjectNotFound):
        await store.fetch(MinioObjectRef(bucket="docs", key="missing.pdf"))


@pytest.mark.asyncio
async def test_minio_fetch_maps_403_to_non_retryable_fetch_failure() -> None:
    store = MinioDocumentStore(_Client(error=_MinioError(status_code=403, code="AccessDenied")))

    with pytest.raises(StageFailure) as exc_info:
        await store.fetch(MinioObjectRef(bucket="docs", key="forbidden.pdf"))

    failure = exc_info.value
    assert failure.stage == IndexingStage.FETCHING
    assert failure.error_code == DEPENDENCY_UNAVAILABLE
    assert failure.retryable is False


def test_uploaded_event_metadata_maps_minio_reference_without_java_lookup() -> None:
    document_id = uuid4()
    event = InboundEvent(
        metadata=EventMetadata(
            event_id=uuid4(),
            event_type="document.uploaded",
            event_version="1.0.0",
            occurred_at=datetime(2026, 5, 17, tzinfo=UTC),
            correlation_id=uuid4(),
            source_service="corp-rag-backend",
        ),
        payload={
            "documentId": str(document_id),
            "title": "HR Policy",
            "language": "en",
            "docType": "POLICY",
            "department": "HR",
            "accessLevel": "INTERNAL",
            "mimeType": "application/pdf",
            "minioBucket": "corp-rag-documents",
            "minioObjectKey": "2026/05/hr-policy.pdf",
        },
        headers={},
    )

    metadata = uploaded_metadata_from_event(event)

    assert metadata.document_id == document_id
    assert metadata.object_ref == MinioObjectRef(
        bucket="corp-rag-documents",
        key="2026/05/hr-policy.pdf",
    )
    assert isinstance(metadata.document_id, UUID)
