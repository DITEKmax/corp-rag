from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractExchange

from corp_rag_ai.adapters.amqp.messages import (
    CORRELATION_ID_HEADER,
    EVENT_TYPE_HEADER,
    EVENT_VERSION_HEADER,
    build_envelope,
    encode_json_bytes,
)
from corp_rag_ai.adapters.amqp.topology import AmqpTopology, load_generated_topology


class DocumentResultPublisher:
    def __init__(
        self,
        channel: AbstractChannel,
        *,
        topology: AmqpTopology | None = None,
        event_version: str = "1.0.0",
        source_service: str = "corp-rag-ai",
    ) -> None:
        self._channel = channel
        self._topology = topology or load_generated_topology()
        self._event_version = event_version
        self._source_service = source_service
        self._exchange: AbstractExchange | None = None

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
    ) -> None:
        event_type = self._topology.document_indexed_routing_key
        payload = {
            "documentId": document_id,
            "chunkCount": chunk_count,
            "indexedAt": indexed_at or datetime.now(UTC),
            "qdrantCollection": qdrant_collection,
            "neo4jEntityCount": neo4j_entity_count,
            "durationMs": duration_ms,
        }
        await self._publish(
            event_type=event_type,
            routing_key=self._topology.document_indexed_routing_key,
            payload=payload,
            correlation_id=correlation_id,
        )

    async def publish_document_indexing_failed(
        self,
        *,
        document_id: UUID,
        stage: str,
        error_code: str,
        error_message: str,
        retryable: bool,
        correlation_id: UUID,
        failed_at: datetime | None = None,
        retry_count: int = 0,
    ) -> None:
        event_type = self._topology.document_indexing_failed_routing_key
        payload = {
            "documentId": document_id,
            "stage": stage,
            "errorCode": error_code,
            "errorMessage": error_message,
            "failedAt": failed_at or datetime.now(UTC),
            "retryable": retryable,
            "retryCount": retry_count,
        }
        await self._publish(
            event_type=event_type,
            routing_key=self._topology.document_indexing_failed_routing_key,
            payload=payload,
            correlation_id=correlation_id,
        )

    async def _publish(
        self,
        *,
        event_type: str,
        routing_key: str,
        payload: dict[str, object],
        correlation_id: UUID,
    ) -> None:
        envelope = build_envelope(
            event_type=event_type,
            payload=payload,
            correlation_id=correlation_id,
            event_version=self._event_version,
            source_service=self._source_service,
        )
        message = aio_pika.Message(
            body=encode_json_bytes(envelope),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            correlation_id=str(correlation_id),
            headers={
                CORRELATION_ID_HEADER: str(correlation_id),
                EVENT_TYPE_HEADER: event_type,
                EVENT_VERSION_HEADER: self._event_version,
            },
        )
        exchange = await self._get_exchange()
        await exchange.publish(message, routing_key=routing_key)

    async def _get_exchange(self) -> AbstractExchange:
        if self._exchange is None:
            self._exchange = await self._channel.declare_exchange(
                self._topology.documents_exchange,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
                passive=True,
            )
        return self._exchange

