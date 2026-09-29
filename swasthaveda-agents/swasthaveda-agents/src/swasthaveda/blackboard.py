"""Shared memory for the swarm: a JSON-persisted key-value store plus an append-only event log."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Blackboard:
    def __init__(self, state_dir: Path | None = None) -> None:
        self._data: dict[str, Any] = {}
        self._data_path: Path | None = None
        self._events_path: Path | None = None
        if state_dir is not None:
            state_dir.mkdir(parents=True, exist_ok=True)
            self._data_path = state_dir / "blackboard.json"
            self._events_path = state_dir / "events.jsonl"
            if self._data_path.exists():
                try:
                    self._data = json.loads(self._data_path.read_text())
                except json.JSONDecodeError:
                    self._data = {}

    def get(self, key: str, default: Any = None) -> Any:
        return copy.deepcopy(self._data.get(key, default))

    def set(self, key: str, value: Any, author: str = "system") -> None:
        self._data[key] = value
        if self._data_path is not None:
            self._data_path.write_text(json.dumps(self._data, indent=2, default=str))
        self.log_event("blackboard_set", key=key, author=author)

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    def log_event(self, event: str, /, **data: Any) -> None:
        if self._events_path is None:
            return
        row = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event, **data}
        with self._events_path.open("a") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
