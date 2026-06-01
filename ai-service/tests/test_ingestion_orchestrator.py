from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from corp_rag_ai.adapters.amqp.messages import InboundEvent, EventMetadata
from corp_rag_ai.adapters.minio import FetchedObject, MinioObjectNotFound, MinioObjectRef
from corp_rag_ai.domain.document import ParsedBlock, ParsedDocument
from corp_rag_ai.domain.exceptions import DEPENDENCY_UNAVAILABLE, IndexingStage, stage_failure
from corp_rag_ai.domain.ingestion_state import DocumentIndexState, IndexStatus
from corp_rag_ai.pipeline.indexing.embedding import EmbeddingVector
from corp_rag_ai.pipeline.indexing.entity_extractor import ParentEntityExtraction
from corp_rag_ai.pipeline.ingestion.chunker import DocumentChunker
from corp_rag_ai.pipeline.ingestion.corpus_sanitizer import CorpusSanitizer
from corp_rag_ai.pipeline.ingestion.orchestrator import DocumentIngestionService


@pytest.mark.asyncio
async def test_upload_success_publishes_indexed_before_terminal_processed_event() -> None:
    calls: list[str] = []
    document_id = uuid4()
    event = _uploaded_event(document_id)
    service = _service(calls=calls)

    await service.handle_uploaded(event)

    assert "object_store.fetch:corp-rag-documents/2026/05/doc.pdf" in calls
    assert calls.index("state.mark_indexing") < calls.index("vector.replace")
    assert calls.index("publisher.indexed") < calls.index("state.mark_indexed")
    assert calls.index("state.mark_indexed") < calls.index("processed.insert")
    assert calls[-1] == "processed.insert"


@pytest.mark.asyncio
async def test_upload_graph_failure_keeps_vector_index_and_marks_indexed() -> None:
    calls: list[str] = []
    document_id = uuid4()
    graph_failure = stage_failure(
        stage=IndexingStage.GRAPH_UPSERT,
        error_code=DEPENDENCY_UNAVAILABLE,
        retryable=True,
        detail="ServiceUnavailable",
    )
    service = _service(calls=calls, graph_replace_error=graph_failure)

    await service.handle_uploaded(_uploaded_event(document_id))

    assert calls.index("vector.replace") < calls.index("graph.replace")
    assert calls.index("graph.replace") < calls.index("graph.cleanup")
    assert calls.index("graph.cleanup") < calls.index("publisher.indexed")
    assert calls.index("publisher.indexed") < calls.index("state.mark_indexed")
    assert calls.index("state.mark_indexed") < calls.index("processed.insert")
    assert "vector.delete" not in calls
    assert "publisher.failed" not in calls
    assert "state.mark_failed" not in calls


@pytest.mark.asyncio
async def test_upload_entity_extraction_failure_keeps_vector_index_and_marks_indexed(caplog) -> None:
    calls: list[str] = []
    document_id = uuid4()
    entity_failure = stage_failure(
        stage=IndexingStage.ENTITY_EXTRACTION,
        error_code=DEPENDENCY_UNAVAILABLE,
        retryable=False,
        detail="malformed_structured_output",
    )
    service = _service(calls=calls, entity_extract_error=entity_failure)
    caplog.set_level(logging.WARNING)

    await service.handle_uploaded(_uploaded_event(document_id))

    assert calls.index("vector.replace") < calls.index("entity.extract")
    assert calls.index("entity.extract") < calls.index("publisher.indexed")
    assert calls.index("publisher.indexed") < calls.index("state.mark_indexed")
    assert calls.index("state.mark_indexed") < calls.index("processed.insert")
    assert "graph.replace" not in calls
    assert "graph.cleanup" not in calls
    assert "vector.delete" not in calls
    assert "publisher.failed" not in calls
    assert "state.mark_failed" not in calls

    warning = next(
        record
        for record in caplog.records
        if record.message == "Skipping graph indexing after vector indexing succeeded"
    )
    assert warning.levelno == logging.WARNING
    assert getattr(warning, "document_id") == str(document_id)
    assert getattr(warning, "stage") == IndexingStage.ENTITY_EXTRACTION.value
    assert getattr(warning, "error_code") == DEPENDENCY_UNAVAILABLE
    assert getattr(warning, "detail") == "malformed_structured_output"


@pytest.mark.asyncio
async def test_upload_parsing_failure_publishes_failed_without_qdrant_rollback() -> None:
    calls: list[str] = []
    parsing_failure = stage_failure(
        stage=IndexingStage.PARSING,
        error_code="INVALID_FILE_FORMAT",
        retryable=False,
        parser="docling",
        mime_type="application/pdf",
    )
    service = _service(calls=calls, parser_error=parsing_failure)

    await service.handle_uploaded(_uploaded_event(uuid4()))

    assert "vector.replace" not in calls
    assert "vector.delete" not in calls
    assert calls.index("publisher.failed") < calls.index("state.mark_failed")
    assert calls.index("state.mark_failed") < calls.index("processed.insert")


@pytest.mark.asyncio
async def test_failed_event_publish_failure_leaves_event_unprocessed_for_redelivery() -> None:
    calls: list[str] = []
    parsing_failure = stage_failure(
        stage=IndexingStage.PARSING,
        error_code="INVALID_FILE_FORMAT",
        retryable=False,
        parser="docling",
        mime_type="application/pdf",
    )
    service = _service(
        calls=calls,
        parser_error=parsing_failure,
        failed_publish_error=RuntimeError("broker unavailable"),
    )

    with pytest.raises(RuntimeError, match="broker unavailable"):
        await service.handle_uploaded(_uploaded_event(uuid4()))

    assert "publisher.failed" in calls
    assert "state.mark_failed" not in calls
    assert "processed.insert" not in calls


@pytest.mark.asyncio
async def test_upload_duplicate_redelivery_acks_without_side_effects() -> None:
    calls: list[str] = []
    service = _service(calls=calls, already_processed=True)

    await service.handle_uploaded(_uploaded_event(uuid4()))

    assert calls == ["processed.has"]


@pytest.mark.asyncio
async def test_delete_before_upload_skip_records_terminal_processed_without_failed_event() -> None:
    calls: list[str] = []
    document_id = uuid4()
    service = _service(calls=calls, existing_state=_deleted_state(document_id))

    await service.handle_uploaded(_uploaded_event(document_id))

    assert calls == ["processed.has", "state.get", "processed.insert"]


@pytest.mark.asyncio
async def test_minio_404_rechecks_deleted_tombstone_and_silently_skips_late_upload() -> None:
    calls: list[str] = []
    document_id = uuid4()
    service = _service(
        calls=calls,
        object_error=MinioObjectNotFound("missing"),
        state_sequence=[None, _deleted_state(document_id)],
    )

    await service.handle_uploaded(_uploaded_event(document_id))

    assert calls == [
        "processed.has",
        "state.get",
        "state.mark_indexing",
        "object_store.fetch:corp-rag-documents/2026/05/doc.pdf",
        "state.get",
        "processed.insert",
    ]


@pytest.mark.asyncio
async def test_delete_handler_cleans_indexes_without_touching_minio() -> None:
    calls: list[str] = []
    document_id = uuid4()
    service = _service(calls=calls)

    await service.handle_deleted(_deleted_event(document_id))

    assert calls == [
        "processed.has",
        "vector.delete",
        "graph.cleanup",
        "parent.delete",
        "state.mark_deleted",
        "processed.insert",
    ]


@pytest.mark.asyncio
async def test_delete_duplicate_redelivery_acks_without_cleanup_side_effects() -> None:
    calls: list[str] = []
    service = _service(calls=calls, already_processed=True)

    await service.handle_deleted(_deleted_event(uuid4()))

    assert calls == ["processed.has"]


def _service(
    *,
    calls: list[str],
    already_processed: bool = False,
    existing_state: DocumentIndexState | None = None,
    state_sequence: list[DocumentIndexState | None] | None = None,
    object_error: Exception | None = None,
    parser_error: Exception | None = None,
    entity_extract_error: Exception | None = None,
    graph_replace_error: Exception | None = None,
    failed_publish_error: Exception | None = None,
) -> DocumentIngestionService:
    return DocumentIngestionService(
        object_store=_ObjectStore(calls, error=object_error),
        parser=_Parser(error=parser_error),
        chunker=DocumentChunker(),
        sanitizer=CorpusSanitizer(),
        vector_index=_VectorIndex(calls),
        entity_extractor=_EntityExtractor(calls, error=entity_extract_error),
        entity_embedder=_Embedder(),
        graph_index=_GraphIndex(calls, replace_error=graph_replace_error),
        publisher=_Publisher(calls, failed_error=failed_publish_error),
        processed_events=_ProcessedEvents(calls, processed=already_processed),
        document_states=_DocumentStates(calls, existing=existing_state, sequence=state_sequence),
        parent_chunks=_ParentChunks(calls),
    )


class _ObjectStore:
    def __init__(self, calls: list[str], *, error: Exception | None = None) -> None:
        self._calls = calls
        self._error = error

    async def fetch(self, object_ref: MinioObjectRef) -> FetchedObject:
        self._calls.append(f"object_store.fetch:{object_ref.bucket}/{object_ref.key}")
        if self._error is not None:
            raise self._error
        return FetchedObject(body=b"document bytes", object_ref=object_ref)


class _Parser:
    def __init__(self, *, error: Exception | None = None) -> None:
        self._error = error

    async def parse(self, *, document_id: UUID, content: bytes, mime_type: str, language: str) -> ParsedDocument:
        if self._error is not None:
            raise self._error
        assert content == b"document bytes"
        assert mime_type == "application/pdf"
        return ParsedDocument(
            document_id=document_id,
            language=language,
            blocks=[
                ParsedBlock(
                    type="paragraph",
                    text="Employees request vacation in the HR portal.",
                    position=0,
                    section_path=["HR"],
                )
            ],
        )


class _VectorIndex:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    async def replace_document_chunks(self, document_id, chunks) -> None:
        self._calls.append("vector.replace")
        assert chunks[0].payload_content == "Employees request vacation in the HR portal."
        assert chunks[0].content_for_embedding.startswith("HR Policy \u203a HR\n\n")

    async def delete_document(self, document_id) -> None:
        self._calls.append("vector.delete")


class _EntityExtractor:
    def __init__(self, calls: list[str], *, error: Exception | None = None) -> None:
        self._calls = calls
        self._error = error

    async def extract_parent(self, source, *, document_title: str, language: str) -> ParentEntityExtraction:
        self._calls.append("entity.extract")
        if self._error is not None:
            raise self._error
        assert source.text == "Employees request vacation in the HR portal."
        assert document_title == "HR Policy"
        return ParentEntityExtraction(entities=(), relations=())


class _Embedder:
    def embed_texts(self, texts) -> tuple[EmbeddingVector, ...]:
        return tuple(EmbeddingVector(dense=(0.1, 0.2), sparse={1: 0.5}) for _text in texts)


class _GraphIndex:
    def __init__(self, calls: list[str], *, replace_error: Exception | None = None) -> None:
        self._calls = calls
        self._replace_error = replace_error

    async def replace_document_graph(self, document_graph) -> None:
        self._calls.append("graph.replace")
        if self._replace_error is not None:
            raise self._replace_error

    async def cleanup_document(self, document_id) -> None:
        self._calls.append("graph.cleanup")


class _Publisher:
    def __init__(self, calls: list[str], *, failed_error: Exception | None = None) -> None:
        self._calls = calls
        self._failed_error = failed_error

    async def publish_document_indexed(self, **_kwargs) -> UUID:
        self._calls.append("publisher.indexed")
        return uuid4()

    async def publish_stage_failure(self, **_kwargs) -> UUID:
        self._calls.append("publisher.failed")
        if self._failed_error is not None:
            raise self._failed_error
        return uuid4()


class _ProcessedEvents:
    def __init__(self, calls: list[str], *, processed: bool = False) -> None:
        self._calls = calls
        self._processed = processed

    async def has_processed(self, _event_id) -> bool:
        self._calls.append("processed.has")
        return self._processed

    async def insert_terminal(self, _event_id, _event_type) -> bool:
        self._calls.append("processed.insert")
        return True


class _DocumentStates:
    def __init__(
        self,
        calls: list[str],
        *,
        existing: DocumentIndexState | None = None,
        sequence: list[DocumentIndexState | None] | None = None,
    ) -> None:
        self._calls = calls
        self._existing = existing
        self._sequence = list(sequence or [])

    async def get(self, _document_id) -> DocumentIndexState | None:
        self._calls.append("state.get")
        if self._sequence:
            return self._sequence.pop(0)
        return self._existing

    async def mark_indexing(self, _document_id) -> None:
        self._calls.append("state.mark_indexing")

    async def mark_indexed(self, _document_id, _event_id) -> None:
        self._calls.append("state.mark_indexed")

    async def mark_failed(self, _document_id, _stage, _error_code, _failed_at=None) -> None:
        self._calls.append("state.mark_failed")

    async def mark_deleted(self, _document_id) -> None:
        self._calls.append("state.mark_deleted")


class _ParentChunks:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    async def replace_for_document(self, _document_id, _chunks) -> None:
        self._calls.append("parent.replace")

    async def delete_by_document(self, _document_id) -> None:
        self._calls.append("parent.delete")


def _uploaded_event(document_id: UUID) -> InboundEvent:
    metadata = _metadata(event_type="document.uploaded")
    return InboundEvent(
        metadata=metadata,
        payload={
            "documentId": str(document_id),
            "title": "HR Policy",
            "language": "en",
            "docType": "POLICY",
            "department": "HR",
            "accessLevel": "INTERNAL",
            "mimeType": "application/pdf",
            "minioBucket": "corp-rag-documents",
            "minioObjectKey": "2026/05/doc.pdf",
        },
        headers={"x-correlation-id": str(metadata.correlation_id)},
    )


def _deleted_event(document_id: UUID) -> InboundEvent:
    metadata = _metadata(event_type="document.deleted")
    return InboundEvent(
        metadata=metadata,
        payload={
            "documentId": str(document_id),
            "deletedBy": str(uuid4()),
            "deletedAt": "2026-05-17T12:00:00Z",
        },
        headers={},
    )


def _metadata(*, event_type: str) -> EventMetadata:
    return EventMetadata(
        event_id=uuid4(),
        event_type=event_type,
        event_version="1.0.0",
        occurred_at=datetime(2026, 5, 17, tzinfo=UTC),
        correlation_id=uuid4(),
        source_service="corp-rag-backend",
    )


def _deleted_state(document_id: UUID) -> DocumentIndexState:
    now = datetime(2026, 5, 17, tzinfo=UTC)
    return DocumentIndexState(
        document_id=document_id,
        status=IndexStatus.DELETED,
        last_indexed_event_id=None,
        last_failure_stage=None,
        last_failure_code=None,
        last_failure_at=None,
        created_at=now,
        updated_at=now,
    )
