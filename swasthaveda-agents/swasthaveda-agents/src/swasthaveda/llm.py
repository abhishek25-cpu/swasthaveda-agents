"""Thin wrapper over the Anthropic SDK. No API key means offline mode (agents use heuristics)."""
from __future__ import annotations

from typing import Any

from .config import Settings


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Any = None
        if settings.api_key:
            import anthropic

            self._client = anthropic.Anthropic(api_key=settings.api_key)

    @property
    def online(self) -> bool:
        return self._client is not None

    def create(self, *, system: str, messages: list[dict], tools: list[dict]) -> Any:
        kwargs: dict[str, Any] = {
            "model": self.settings.model,
            "max_tokens": self.settings.max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        return self._client.messages.create(**kwargs)
