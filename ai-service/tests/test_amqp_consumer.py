from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from corp_rag_ai.adapters.amqp.consumer import (
    DocumentEventConsumerRuntime,
    IdempotentEventDispatcher,
    InfrastructureRetry,
    ManualAckConsumer,
    TopologyMissingError,
)
from corp_rag_ai.adapters.amqp.messages import build_envelope, encode_json_bytes
from corp_rag_ai.adapters.amqp.topology import AmqpTopology


TOPOLOGY = AmqpTopology(
    documents_exchange="corp-rag.documents",
    document_uploaded_queue="ai.document.uploaded",
    document_deleted_queue="ai.document.deleted",
    document_indexed_routing_key="document.indexed",
    document_indexing_failed_routing_key="document.indexing.failed",
)


class _Message:
    def __init__(self, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.body = body
        self.headers = headers or {}
        self.acks = 0
        self.nacks: list[bool] = []

    async def ack(self) -> None:
        self.acks += 1

    async def nack(self, *, requeue: bool) -> None:
        self.nacks.append(requeue)


class _Queue:
    def __init__(self) -> None:
        self.consumer = None
        self.no_ack: bool | None = None

    async def consume(self, consumer, *, no_ack: bool) -> None:
        self.consumer = consumer
        self.no_ack = no_ack


class _Channel:
    def __init__(self, *, fail_declare: bool = False) -> None:
        self.fail_declare = fail_declare
        self.declarations: list[dict[str, object]] = []
        self.queues: list[_Queue] = []

    async def declare_queue(self, name: str, *, durable: bool, passive: bool) -> _Queue:
        self.declarations.append({"name": name, "durable": durable, "passive": passive})
        if self.fail_declare:
            raise RuntimeError("queue not found")
        queue = _Queue()
        self.queues.append(queue)
        return queue


class _ProcessedEvents:
    def __init__(self, processed: bool) -> None:
        self.processed = processed

    async def has_processed(self, _event_id) -> bool:
        return self.processed


def _message_body(event_type: str = "document.uploaded") -> bytes:
    return encode_json_bytes(
        build_envelope(
            event_type=event_type,
            payload={"documentId": str(uuid4())},
            correlation_id=uuid4(),
            event_version="1.0.0",
            source_service="corp-rag-backend",
            occurred_at=datetime(2026, 5, 17, tzinfo=UTC),
        )
    )


@pytest.mark.asyncio
async def test_manual_ack_consumer_acks_after_handler_success() -> None:
    seen = []

    async def handler(event) -> None:
        seen.append(event.metadata.event_type)

    message = _Message(_message_body())

    await ManualAckConsumer(handler)(message)

    assert seen == ["document.uploaded"]
    assert message.acks == 1
    assert message.nacks == []


@pytest.mark.asyncio
async def test_manual_ack_consumer_nacks_infrastructure_failures() -> None:
    async def handler(_event) -> None:
        raise InfrastructureRetry("postgres unavailable")

    message = _Message(_message_body())

    await ManualAckConsumer(handler)(message)

    assert message.acks == 0
    assert message.nacks == [True]


@pytest.mark.asyncio
async def test_duplicate_processed_event_acks_without_business_work() -> None:
    business_calls = 0

    async def business_handler(_event) -> None:
        nonlocal business_calls
        business_calls += 1

    dispatcher = IdempotentEventDispatcher(_ProcessedEvents(processed=True), business_handler)
    message = _Message(_message_body())

    await ManualAckConsumer(dispatcher)(message)

    assert business_calls == 0
    assert message.acks == 1
    assert message.nacks == []


@pytest.mark.asyncio
async def test_document_event_runtime_declares_java_owned_queues_passively() -> None:
    async def handler(_event) -> None:
        return None

    channel = _Channel()
    runtime = DocumentEventConsumerRuntime(
        channel,
        uploaded_handler=handler,
        deleted_handler=handler,
        topology=TOPOLOGY,
    )

    await runtime.start()

    assert channel.declarations == [
        {"name": "ai.document.uploaded", "durable": True, "passive": True},
        {"name": "ai.document.deleted", "durable": True, "passive": True},
    ]
    assert [queue.no_ack for queue in channel.queues] == [False, False]


@pytest.mark.asyncio
async def test_document_event_runtime_fails_fast_when_topology_is_missing() -> None:
    async def handler(_event) -> None:
        return None

    runtime = DocumentEventConsumerRuntime(
        _Channel(fail_declare=True),
        uploaded_handler=handler,
        deleted_handler=handler,
        topology=TOPOLOGY,
    )

    with pytest.raises(TopologyMissingError, match="ai.document.uploaded"):
        await runtime.start()

