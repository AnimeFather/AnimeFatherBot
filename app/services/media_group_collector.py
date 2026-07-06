import asyncio
from collections import defaultdict

from aiogram.types import Message


class MediaGroupCollector:
    def __init__(self, wait_time: float = 1.5) -> None:
        self._buffer: dict[str, list[Message]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._wait_time = wait_time

    async def collect(self, message: Message) -> list[Message] | None:
        if not message.media_group_id:
            return None

        mg_id = message.media_group_id

        async with self._lock:
            if mg_id in self._buffer:
                self._buffer[mg_id].append(message)
                return None
            self._buffer[mg_id] = [message]

        await asyncio.sleep(self._wait_time)

        async with self._lock:
            messages = self._buffer.pop(mg_id, [])

        if not messages:
            return None

        messages.sort(key=lambda m: m.message_id)
        return messages
