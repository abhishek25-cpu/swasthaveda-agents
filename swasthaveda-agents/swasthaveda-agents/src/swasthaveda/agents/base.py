"""BaseAgent: one LLM tool-use loop, per-agent tool allowlists, and an offline fallback."""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from ..blackboard import Blackboard
from ..bus import Message, MessageBus
from ..config import Settings
from ..domain import BRAND_BRIEF
from ..llm import LLMClient
from ..tools import ToolContext, ToolRegistry

log = logging.getLogger("swasthaveda")

PROTOCOL = """You are one of three autonomous agents in a marketing swarm:
  tracker   -> senses the market (metrics, trends, competitor prices)
  predictor -> forecasts demand, inventory runway and the impact of budget moves
  commander -> the ONLY agent that acts (budgets, promos, content, human alerts)
Rules:
- Communicate with other agents only via send_message; bulky data lives on the blackboard.
- Never invent numbers. Every figure you state must come from a tool result.
- Guardrails are enforced in code. If a tool rejects an action, accept it and report it.
- Prefer small, reversible actions. When unsure, notify_human.
- Finish with a 1-2 sentence summary of what you did."""


def _short(obj: Any, n: int = 110) -> str:
    text = json.dumps(obj, default=str)
    return text if len(text) <= n else text[: n - 1] + "…"


def latest(inbox: list[Message], topic: str) -> Message | None:
    matches = [m for m in inbox if m.topic == topic]
    return matches[-1] if matches else None


class BaseAgent(ABC):
    name: str = "agent"
    mission: str = ""
    tools: tuple[str, ...] = ()

    def __init__(self, llm: LLMClient, registry: ToolRegistry, bus: MessageBus,
                 board: Blackboard, settings: Settings) -> None:
        self.llm, self.registry, self.bus, self.board, self.settings = llm, registry, bus, board, settings
        self._ctx = ToolContext(agent=self.name, bus=bus, board=board, settings=settings)

    @property
    def system_prompt(self) -> str:
        return f"{BRAND_BRIEF}\n\n{PROTOCOL}\n\nYou are the {self.name.upper()}.\n{self.mission}"

    # -- tools ---------------------------------------------------------------------------
    def call_tool(self, tool_name: str, args: dict | None = None) -> Any:
        args = args or {}
        if tool_name not in self.tools:
            result: Any = {"error": f"agent '{self.name}' is not permitted to use '{tool_name}'"}
        else:
            result = self.registry.call(tool_name, args, self._ctx)
        log.info("[%s] %s(%s) -> %s", self.name, tool_name, _short(args), _short(result))
        return result

    # -- execution -----------------------------------------------------------------------
    def step(self) -> str | None:
        """Process everything in the inbox. Returns a summary, or None if there was nothing to do."""
        inbox = self.bus.drain(self.name)
        if not inbox:
            return None
        return self._run_llm(inbox) if self.llm.online else self.run_offline(inbox)

    @abstractmethod
    def run_offline(self, inbox: list[Message]) -> str:
        """Deterministic heuristic policy used when no API key is configured."""

    def _run_llm(self, inbox: list[Message]) -> str:
        rendered = json.dumps(
            [{"from": m.sender, "topic": m.topic, "payload": m.payload} for m in inbox], indent=2, default=str
        )
        messages: list[dict] = [{
            "role": "user",
            "content": f"New messages:\n{rendered}\n\nDo your job now using your tools.",
        }]
        specs = self.registry.specs(self.tools)
        for _ in range(self.settings.max_tool_turns):
            resp = self.llm.create(system=self.system_prompt, messages=messages, tools=specs)
            messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason != "tool_use":
                return "".join(b.text for b in resp.content if b.type == "text").strip()
            results = [
                {
                    "type": "tool_result",
                    "tool_use_id": b.id,
                    "content": json.dumps(self.call_tool(b.name, dict(b.input)), default=str),
                }
                for b in resp.content
                if b.type == "tool_use"
            ]
            messages.append({"role": "user", "content": results})
        return "(stopped: max tool turns reached)"
