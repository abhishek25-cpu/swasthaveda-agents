"""In-process message bus: the agents' only direct line to each other."""
from __future__ import annotations

import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Message:
    sender: str
    recipient: str
    topic: str
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


class MessageBus:
    def __init__(self) -> None:
        self._queues: dict[str, deque[Message]] = defaultdict(deque)
        self.history: list[Message] = []

    def send(self, msg: Message) -> None:
        self._queues[msg.recipient].append(msg)
        self.history.append(msg)

    def pending(self, recipient: str) -> int:
        return len(self._queues[recipient])

    def drain(self, recipient: str) -> list[Message]:
        q = self._queues[recipient]
        out = list(q)
        q.clear()
        return out
