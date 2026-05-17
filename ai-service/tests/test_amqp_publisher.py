from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from corp_rag_ai.adapters.amqp.messages import CORRELATION_ID_HEADER, resolve_correlation_id
from corp_rag_ai.adapters.amqp.publisher import DocumentResultPublisher
from corp_rag_ai.adapters.amqp.topology import AmqpTopology
from corp_rag_ai.domain.exceptions import INDEXING_PIPELINE_ERROR, IndexingStage, stage_failure


TOPOLOGY = AmqpTopology(
    documents_exchange="corp-rag.documents",
    document_uploaded_queue="ai.document.uploaded",
    document_deleted_queue="ai.document.deleted",
    document_indexed_routing_key="document.indexed",
    document_indexing_failed_routing_key="document.indexing.failed",
)


class _Exchange:
    def __init__(self) -> None:
        self.published = []

    async def publish(self, message, *, routing_key: str) -> None:
        self.published.append((message, routing_key))


class _Channel:
    def __init__(self) -> None:
        self.exchange = _Exchange()
        self.exchange_declarations = []

    async def declare_exchange(self, name, exchange_type, *, durable: bool, passive: bool):
        self.exchange_declarations.append(
            {
                "name": name,
                "exchange_type": exchange_type,
                "durable": durable,
                "passive": passive,
            }
        )
        return self.exchange


@pytest.mark.asyncio
async def test_document_indexed_publisher_uses_generated_topology_and_headers() -> None:
    channel = _Channel()
    publisher = DocumentResultPublisher(
        channel,
        topology=TOPOLOGY,
        event_version="1.0.0",
        source_service="corp-rag-ai",
    )
    correlation_id = uuid4()
    document_id = uuid4()

    await publisher.publish_document_indexed(
        document_id=document_id,
        chunk_count=4,
        qdrant_collection="documents_chunks",
        neo4j_entity_count=2,
        duration_ms=1250,
        correlation_id=correlation_id,
        indexed_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
    )

    message, routing_key = channel.exchange.published[0]
    envelope = json.loads(message.body.decode("utf-8"))

    assert channel.exchange_declarations[0]["name"] == "corp-rag.documents"
    assert channel.exchange_declarations[0]["passive"] is True
    assert routing_key == "document.indexed"
    assert message.headers["x-correlation-id"] == str(correlation_id)
    assert message.headers["x-event-type"] == "document.indexed"
    assert message.headers["x-event-version"] == "1.0.0"
    assert envelope["metadata"]["eventType"] == "document.indexed"
    assert envelope["metadata"]["sourceService"] == "corp-rag-ai"
    assert envelope["metadata"]["correlationId"] == str(correlation_id)
    assert envelope["payload"]["documentId"] == str(document_id)
    assert envelope["payload"]["chunkCount"] == 4


@pytest.mark.asyncio
async def test_document_indexing_failed_publisher_defaults_retry_count_to_zero() -> None:
    channel = _Channel()
    publisher = DocumentResultPublisher(channel, topology=TOPOLOGY)
    correlation_id = uuid4()

    await publisher.publish_document_indexing_failed(
        document_id=uuid4(),
        stage="PARSING",
        error_code="INVALID_FILE_FORMAT",
        error_message="Parsing failed: ValueError.",
        retryable=False,
        correlation_id=correlation_id,
        failed_at=datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
    )

    message, routing_key = channel.exchange.published[0]
    envelope = json.loads(message.body.decode("utf-8"))

    assert routing_key == "document.indexing.failed"
    assert message.headers["x-event-type"] == "document.indexing.failed"
    assert envelope["payload"]["retryCount"] == 0
    assert envelope["payload"]["stage"] == "PARSING"
    assert envelope["payload"]["errorCode"] == "INVALID_FILE_FORMAT"


def test_correlation_id_resolution_prefers_header_then_metadata_then_generated() -> None:
    header_id = uuid4()
    metadata_id = uuid4()

    assert resolve_correlation_id({CORRELATION_ID_HEADER: str(header_id)}, {"correlationId": str(metadata_id)}) == header_id
    assert resolve_correlation_id({}, {"correlationId": str(metadata_id)}) == metadata_id
    assert isinstance(resolve_correlation_id({}, None), UUID)


@pytest.mark.asyncio
async def test_stage_failure_publisher_uses_failed_payload_builder() -> None:
    channel = _Channel()
    publisher = DocumentResultPublisher(channel, topology=TOPOLOGY)
    correlation_id = uuid4()

    await publisher.publish_stage_failure(
        document_id=uuid4(),
        failure=stage_failure(
            stage=IndexingStage.EMBEDDING,
            error_code=INDEXING_PIPELINE_ERROR,
            retryable=False,
            exception_class=RuntimeError("secret model path"),
        ),
        correlation_id=correlation_id,
    )

    message, routing_key = channel.exchange.published[0]
    envelope = json.loads(message.body.decode("utf-8"))

    assert routing_key == "document.indexing.failed"
    assert envelope["payload"]["retryCount"] == 0
    assert "FlagEmbedding" in envelope["payload"]["errorMessage"]
    assert "secret model path" not in envelope["payload"]["errorMessage"]
