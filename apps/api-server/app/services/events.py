from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


TERMINAL_EVENTS = {"completed", "error"}


@dataclass
class _Channel:
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    terminal: bool = False
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)


class RequestEventBroker:
    """保存单次问答的 SSE 事件，支持完成后重放。"""

    def __init__(self, *, max_requests: int = 500) -> None:
        self.max_requests = max_requests
        self._channels: dict[str, _Channel] = {}

    def create(self, request_id: str) -> None:
        if request_id in self._channels:
            return
        if len(self._channels) >= self.max_requests:
            oldest = next(iter(self._channels))
            self._channels.pop(oldest, None)
        self._channels[request_id] = _Channel()

    def has(self, request_id: str) -> bool:
        return request_id in self._channels

    async def publish(
        self, request_id: str, event: str, data: dict[str, Any]
    ) -> None:
        channel = self._channels.setdefault(request_id, _Channel())
        async with channel.condition:
            channel.events.append((event, data))
            if event in TERMINAL_EVENTS:
                channel.terminal = True
            channel.condition.notify_all()

    async def stream(self, request_id: str) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        channel = self._channels.setdefault(request_id, _Channel())
        index = 0
        while True:
            async with channel.condition:
                while index >= len(channel.events) and not channel.terminal:
                    await channel.condition.wait()
                pending = channel.events[index:]
                index = len(channel.events)
                terminal = channel.terminal
            for item in pending:
                yield item
            if terminal and index >= len(channel.events):
                return
