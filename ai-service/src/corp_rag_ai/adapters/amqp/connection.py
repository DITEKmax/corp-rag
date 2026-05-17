from __future__ import annotations

from dataclasses import dataclass

import aio_pika
from aio_pika.abc import AbstractRobustChannel, AbstractRobustConnection


@dataclass(slots=True)
class AmqpConnectionManager:
    url: str
    prefetch_count: int = 1
    connection: AbstractRobustConnection | None = None
    channel: AbstractRobustChannel | None = None

    async def connect(self) -> AbstractRobustChannel:
        self.connection = await aio_pika.connect_robust(self.url)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=self.prefetch_count)
        return self.channel

    async def close(self) -> None:
        if self.channel is not None and not self.channel.is_closed:
            await self.channel.close()
        if self.connection is not None and not self.connection.is_closed:
            await self.connection.close()
        self.channel = None
        self.connection = None

