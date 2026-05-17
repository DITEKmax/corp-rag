from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from corp_rag_ai.adapters.amqp.messages import InboundEvent, resolve_correlation_id
from corp_rag_ai.adapters.minio import FetchedObject, MinioObjectNotFound, MinioObjectRef
from corp_rag_ai.domain.chunks import ChunkingResult, ParentChunk
from corp_rag_ai.domain.document import ParsedDocument
from corp_rag_ai.domain.exceptions import (
    DOCUMENT_NOT_FOUND,
    INDEXING_PIPELINE_ERROR,
    INVALID_FILE_FORMAT,
    IndexingStage,
    StageFailure,
    stage_failure,
)
from corp_rag_ai.domain.ingestion_state import DocumentIndexState, IndexStatus, ParentChunkRecord
from corp_rag_ai.pipeline.indexing.embedding import EmbeddingVector
from corp_rag_ai.pipeline.indexing.entity_extractor import (
    EntityExtractionSource,
    ParentEntityExtraction,
    build_graph_document_index,
)
from corp_rag_ai.pipeline.indexing.graph_indexer import GraphDocument, GraphDocumentIndex
from corp_rag_ai.pipeline.indexing.vector_indexer import COLLECTION_NAME, VectorIndexChunk
from corp_rag_ai.pipeline.ingestion.chunker import DocumentChunker
from corp_rag_ai.pipeline.ingestion.corpus_sanitizer import CorpusSanitizer, SanitizedChildChunk
from corp_rag_ai.pipeline.ingestion.events import (
    UploadedDocumentMetadata,
    deleted_metadata_from_event,
    uploaded_metadata_from_event,
)

logger = logging.getLogger(__name__)

_BREADCRUMB_SEPARATOR = " \u203a "
_ROLLBACK_STAGES = {
    IndexingStage.VECTOR_UPSERT,
    IndexingStage.ENTITY_EXTRACTION,
    IndexingStage.GRAPH_UPSERT,
}


class ObjectStore(Protocol):
    async def fetch(self, object_ref: MinioObjectRef) -> FetchedObject:
        ...


class DocumentParser(Protocol):
    async def parse(
        self,
        *,
        document_id: UUID,
        content: bytes,
        mime_type: str,
        language: str,
    ) -> ParsedDocument:
        ...


class ProcessedEvents(Protocol):
    async def has_processed(self, event_id: UUID) -> bool:
        ...

    async def insert_terminal(self, event_id: UUID, event_type: str) -> bool:
        ...


class DocumentStates(Protocol):
    async def get(self, document_id: UUID) -> DocumentIndexState | None:
        ...

    async def mark_indexing(self, document_id: UUID) -> None:
        ...

    async def mark_indexed(self, document_id: UUID, event_id: UUID) -> None:
        ...

    async def mark_failed(
        self,
        document_id: UUID,
        stage: str,
        error_code: str,
        failed_at: datetime | None = None,
    ) -> None:
        ...

    async def mark_deleted(self, document_id: UUID) -> None:
        ...


class ParentChunks(Protocol):
    async def replace_for_document(self, document_id: UUID, chunks: Sequence[ParentChunkRecord]) -> None:
        ...

    async def delete_by_document(self, document_id: UUID) -> None:
        ...


class VectorIndex(Protocol):
    async def replace_document_chunks(self, document_id: UUID | str, chunks: Sequence[VectorIndexChunk]) -> None:
        ...

    async def delete_document(self, document_id: UUID | str) -> None:
        ...


class EntityExtractor(Protocol):
    async def extract_parent(
        self,
        source: EntityExtractionSource,
        *,
        document_title: str,
        language: str,
    ) -> ParentEntityExtraction:
        ...


class EntityEmbedder(Protocol):
    def embed_texts(self, texts: Sequence[str]) -> tuple[EmbeddingVector, ...]:
        ...


class GraphIndex(Protocol):
    async def replace_document_graph(self, document_graph: GraphDocumentIndex) -> None:
        ...

    async def cleanup_document(self, document_id: UUID | str) -> None:
        ...


class ResultPublisher(Protocol):
    async def publish_document_indexed(
        self,
        *,
        document_id: UUID,
        chunk_count: int,
        qdrant_collection: str,
        neo4j_entity_count: int,
        duration_ms: int,
        correlation_id: UUID,
        indexed_at: datetime | None = None,
    ) -> UUID:
        ...

    async def publish_stage_failure(
        self,
        *,
        document_id: UUID,
        failure: StageFailure,
        correlation_id: UUID,
        failed_at: datetime | None = None,
        retry_count: int = 0,
    ) -> UUID:
        ...


class DocumentIngestionService:
    def __init__(
        self,
        *,
        object_store: ObjectStore,
        parser: DocumentParser,
        chunker: DocumentChunker,
        sanitizer: CorpusSanitizer,
        vector_index: VectorIndex,
        entity_extractor: EntityExtractor,
        entity_embedder: EntityEmbedder,
        graph_index: GraphIndex,
        publisher: ResultPublisher,
        processed_events: ProcessedEvents,
        document_states: DocumentStates,
        parent_chunks: ParentChunks,
    ) -> None:
        self._object_store = object_store
        self._parser = parser
        self._chunker = chunker
        self._sanitizer = sanitizer
        self._vector_index = vector_index
        self._entity_extractor = entity_extractor
        self._entity_embedder = entity_embedder
        self._graph_index = graph_index
        self._publisher = publisher
        self._processed_events = processed_events
        self._document_states = document_states
        self._parent_chunks = parent_chunks

    async def handle_uploaded(self, event: InboundEvent) -> None:
        if await self._processed_events.has_processed(event.metadata.event_id):
            return

        metadata = uploaded_metadata_from_event(event)
        correlation_id = resolve_correlation_id(event.headers, event.metadata)
        if await self._skip_if_deleted(metadata.document_id, event):
            return

        await self._document_states.mark_indexing(metadata.document_id)
        started = time.monotonic()
        qdrant_has_document = False

        try:
            fetched = await self._fetch_source(metadata, event)
            parsed = await self._parse_document(metadata, fetched)
            chunks = self._chunk_document(metadata, parsed)
            sanitized = self._sanitize_children(chunks)
            await self._parent_chunks.replace_for_document(metadata.document_id, chunks.parent_records())
            await self._vector_index.replace_document_chunks(
                metadata.document_id,
                _vector_chunks(metadata, sanitized),
            )
            qdrant_has_document = True
            graph = await self._build_graph(metadata, chunks)
            await self._graph_index.replace_document_graph(graph)
            indexed_at = datetime.now(UTC)
            result_event_id = await self._publisher.publish_document_indexed(
                document_id=metadata.document_id,
                chunk_count=len(sanitized),
                qdrant_collection=COLLECTION_NAME,
                neo4j_entity_count=len(graph.entities),
                duration_ms=_duration_ms(started),
                correlation_id=correlation_id,
                indexed_at=indexed_at,
            )
            await self._document_states.mark_indexed(metadata.document_id, result_event_id)
            await self._processed_events.insert_terminal(event.metadata.event_id, event.metadata.event_type)
        except _TerminalSkip:
            return
        except StageFailure as failure:
            await self._handle_upload_failure(
                event=event,
                document_id=metadata.document_id,
                correlation_id=correlation_id,
                failure=failure,
                qdrant_has_document=qdrant_has_document,
            )

    async def handle_deleted(self, event: InboundEvent) -> None:
        if await self._processed_events.has_processed(event.metadata.event_id):
            return

        metadata = deleted_metadata_from_event(event)
        await self._vector_index.delete_document(metadata.document_id)
        await self._graph_index.cleanup_document(metadata.document_id)
        await self._parent_chunks.delete_by_document(metadata.document_id)
        await self._document_states.mark_deleted(metadata.document_id)
        await self._processed_events.insert_terminal(event.metadata.event_id, event.metadata.event_type)

    async def _skip_if_deleted(self, document_id: UUID, event: InboundEvent) -> bool:
        state = await self._document_states.get(document_id)
        if state is None or state.status != IndexStatus.DELETED:
            return False
        await self._processed_events.insert_terminal(event.metadata.event_id, event.metadata.event_type)
        return True

    async def _fetch_source(
        self,
        metadata: UploadedDocumentMetadata,
        event: InboundEvent,
    ) -> FetchedObject:
        try:
            return await self._object_store.fetch(metadata.object_ref)
        except MinioObjectNotFound as exc:
            if await self._skip_if_deleted(metadata.document_id, event):
                raise _TerminalSkip from exc
            raise stage_failure(
                stage=IndexingStage.FETCHING,
                error_code=DOCUMENT_NOT_FOUND,
                retryable=False,
                detail="object_not_found",
            ) from exc

    async def _parse_document(self, metadata: UploadedDocumentMetadata, fetched: FetchedObject) -> ParsedDocument:
        try:
            return await self._parser.parse(
                document_id=metadata.document_id,
                content=fetched.body,
                mime_type=metadata.mime_type,
                language=metadata.language,
            )
        except StageFailure:
            raise
        except ValueError as exc:
            raise stage_failure(
                stage=IndexingStage.PARSING,
                error_code=INVALID_FILE_FORMAT,
                retryable=False,
                parser="dispatcher",
                mime_type=metadata.mime_type,
            ) from exc
        except Exception as exc:
            raise stage_failure(
                stage=IndexingStage.PARSING,
                error_code=INVALID_FILE_FORMAT,
                retryable=False,
                parser=exc.__class__.__name__,
                mime_type=metadata.mime_type,
            ) from exc

    def _chunk_document(
        self,
        metadata: UploadedDocumentMetadata,
        parsed: ParsedDocument,
    ) -> ChunkingResult:
        try:
            return self._chunker.chunk(parsed, document_title=metadata.title)
        except StageFailure:
            raise
        except Exception as exc:
            raise stage_failure(
                stage=IndexingStage.CHUNKING,
                error_code=INDEXING_PIPELINE_ERROR,
                retryable=False,
                exception_class=exc,
            ) from exc

    def _sanitize_children(self, chunks: ChunkingResult) -> tuple[SanitizedChildChunk, ...]:
        return self._sanitizer.sanitize_child_chunks(chunks.children)

    async def _build_graph(
        self,
        metadata: UploadedDocumentMetadata,
        chunks: ChunkingResult,
    ) -> GraphDocumentIndex:
        children_by_parent = {child.parent_chunk_id: child for child in chunks.children}
        parent_extractions: list[ParentEntityExtraction] = []
        for parent in chunks.parents:
            child = children_by_parent.get(parent.parent_chunk_id)
            if child is None:
                continue
            parent_extractions.append(
                await self._entity_extractor.extract_parent(
                    _entity_source(parent, child.chunk_id),
                    document_title=metadata.title,
                    language=metadata.language,
                )
            )
        return build_graph_document_index(
            document=GraphDocument(
                document_id=metadata.document_id,
                title=metadata.title,
                access_level=metadata.access_level,
                department=metadata.department,
                doc_type=metadata.doc_type,
                language=metadata.language,
            ),
            parent_extractions=parent_extractions,
            embedder=self._entity_embedder,
        )

    async def _handle_upload_failure(
        self,
        *,
        event: InboundEvent,
        document_id: UUID,
        correlation_id: UUID,
        failure: StageFailure,
        qdrant_has_document: bool,
    ) -> None:
        if qdrant_has_document or failure.stage in _ROLLBACK_STAGES:
            await self._best_effort_qdrant_rollback(document_id)
        if failure.stage == IndexingStage.GRAPH_UPSERT:
            await self._best_effort_graph_cleanup(document_id)

        failed_at = datetime.now(UTC)
        await self._publisher.publish_stage_failure(
            document_id=document_id,
            failure=failure,
            correlation_id=correlation_id,
            failed_at=failed_at,
        )
        await self._document_states.mark_failed(
            document_id,
            failure.stage.value,
            failure.error_code,
            failed_at,
        )
        await self._processed_events.insert_terminal(event.metadata.event_id, event.metadata.event_type)

    async def _best_effort_qdrant_rollback(self, document_id: UUID) -> None:
        try:
            await self._vector_index.delete_document(document_id)
        except Exception:
            logger.exception("Qdrant rollback failed after indexing failure", extra={"document_id": str(document_id)})

    async def _best_effort_graph_cleanup(self, document_id: UUID) -> None:
        try:
            await self._graph_index.cleanup_document(document_id)
        except Exception:
            logger.exception("Neo4j cleanup failed after graph failure", extra={"document_id": str(document_id)})


class _TerminalSkip(Exception):
    pass


def _vector_chunks(
    metadata: UploadedDocumentMetadata,
    sanitized: Sequence[SanitizedChildChunk],
) -> tuple[VectorIndexChunk, ...]:
    return tuple(
        VectorIndexChunk(
            child=item.child,
            document_title=metadata.title,
            language=metadata.language,
            doc_type=metadata.doc_type,
            department=metadata.department,
            access_level=metadata.access_level,
            is_sanitized=item.is_sanitized,
            sanitizer_flags=item.sanitizer_flags,
            payload_content=item.sanitized_text,
            content_for_embedding=_embedding_text(
                title=metadata.title,
                section_path=item.child.section_path,
                body=item.sanitized_text,
            ),
        )
        for item in sanitized
    )


def _entity_source(parent: ParentChunk, child_id: UUID) -> EntityExtractionSource:
    return EntityExtractionSource(
        text=parent.content,
        chunk_id=child_id,
        parent_chunk_id=parent.parent_chunk_id,
        section_path=parent.section_path,
    )


def _embedding_text(*, title: str, section_path: tuple[str, ...], body: str) -> str:
    breadcrumb = _BREADCRUMB_SEPARATOR.join(part for part in (title, *section_path) if part)
    return f"{breadcrumb}\n\n{body}" if breadcrumb else body


def _duration_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))
