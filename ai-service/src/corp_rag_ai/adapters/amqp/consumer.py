from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from aio_pika.abc import AbstractChannel, AbstractIncomingMessage, AbstractQueue

from corp_rag_ai.adapters.amqp.messages import InboundEvent, decode_inbound_event
from corp_rag_ai.adapters.amqp.topology import AmqpTopology, load_generated_topology
from corp_rag_ai.repositories.ingestion_state import ProcessedEventRepository

EventHandler = Callable[[InboundEvent], Awaitable[None]]


class InfrastructureRetry(Exception):
    """Raised when the message should be requeued before a terminal outcome."""


class TopologyMissingError(RuntimeError):
    """Raised when Java-owned RabbitMQ topology is not present."""


@dataclass(frozen=True, slots=True)
class ConsumerBinding:
    queue_name: str
    handler: EventHandler


class IdempotentEventDispatcher:
    def __init__(
        self,
        processed_events: ProcessedEventRepository,
        business_handler: EventHandler,
    ) -> None:
        self._processed_events = processed_events
        self._business_handler = business_handler

    async def __call__(self, event: InboundEvent) -> None:
        if await self._processed_events.has_processed(event.metadata.event_id):
            return
        await self._business_handler(event)


class ManualAckConsumer:
    def __init__(self, handler: EventHandler) -> None:
        self._handler = handler

    async def __call__(self, message: AbstractIncomingMessage) -> None:
        try:
            event = decode_inbound_event(message.body, message.headers or {})
            await self._handler(event)
        except InfrastructureRetry:
            await message.nack(requeue=True)
            return
        except Exception:
            await message.nack(requeue=True)
            raise
        await message.ack()


class DocumentEventConsumerRuntime:
    def __init__(
        self,
        channel: AbstractChannel,
        *,
        uploaded_handler: EventHandler,
        deleted_handler: EventHandler,
        topology: AmqpTopology | None = None,
    ) -> None:
        self._channel = channel
        self._uploaded_handler = uploaded_handler
        self._deleted_handler = deleted_handler
        self._topology = topology or load_generated_topology()
        self._queues: list[AbstractQueue] = []

    async def start(self) -> None:
        await self._consume(
            ConsumerBinding(
                queue_name=self._topology.document_uploaded_queue,
                handler=self._uploaded_handler,
            )
        )
        await self._consume(
            ConsumerBinding(
                queue_name=self._topology.document_deleted_queue,
                handler=self._deleted_handler,
            )
        )

    async def _consume(self, binding: ConsumerBinding) -> None:
        try:
            queue = await self._channel.declare_queue(
                binding.queue_name,
                durable=True,
                passive=True,
            )
        except Exception as exc:
            raise TopologyMissingError(f"RabbitMQ queue is missing: {binding.queue_name}") from exc
        await queue.consume(ManualAckConsumer(binding.handler), no_ack=False)
        self._queues.append(queue)

    async def close(self) -> None:
        for queue in self._queues:
            close = getattr(queue, "close", None)
            if close is not None:
                result = close()
                if _is_awaitable(result):
                    await result
        self._queues.clear()


def _is_awaitable(value: Any) -> bool:
    return hasattr(value, "__await__")
