from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from corp_rag_ai.adapters.amqp.messages import InboundEvent
from corp_rag_ai.adapters.minio import MinioObjectRef


@dataclass(frozen=True, slots=True)
class UploadedDocumentMetadata:
    document_id: UUID
    title: str
    language: str
    doc_type: str
    department: str
    access_level: str
    mime_type: str
    object_ref: MinioObjectRef


@dataclass(frozen=True, slots=True)
class DeletedDocumentMetadata:
    document_id: UUID


def uploaded_metadata_from_event(event: InboundEvent) -> UploadedDocumentMetadata:
    payload = event.payload
    return UploadedDocumentMetadata(
        document_id=_uuid(payload, "documentId"),
        title=_str(payload, "title"),
        language=_str(payload, "language"),
        doc_type=_str(payload, "docType"),
        department=_str(payload, "department"),
        access_level=_str(payload, "accessLevel"),
        mime_type=_str(payload, "mimeType"),
        object_ref=MinioObjectRef(
            bucket=_str(payload, "minioBucket"),
            key=_str(payload, "minioObjectKey"),
        ),
    )


def deleted_metadata_from_event(event: InboundEvent) -> DeletedDocumentMetadata:
    return DeletedDocumentMetadata(document_id=_uuid(event.payload, "documentId"))


def _str(payload: dict[str, Any], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-blank string")
    return value.strip()


def _uuid(payload: dict[str, Any], key: str) -> UUID:
    value = payload[key]
    return value if isinstance(value, UUID) else UUID(str(value))
