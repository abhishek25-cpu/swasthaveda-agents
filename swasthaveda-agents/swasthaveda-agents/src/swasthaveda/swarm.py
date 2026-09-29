"""Orchestrator. It owns no logic about marketing: it only wires the agents together and
keeps running whoever has mail until the cycle is complete (or the hop limit trips)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from . import domain as d
from .agents import CommanderAgent, PredictorAgent, TrackerAgent
from .blackboard import Blackboard
from .bus import Message, MessageBus
from .config import Settings
from .llm import LLMClient
from .tools import registry

log = logging.getLogger("swasthaveda")


@dataclass
class CycleReport:
    cycle: int
    mode: str
    completed: bool
    transcript: list[tuple[str, str]] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)


class Swarm:
    def __init__(self, settings: Settings | None = None, llm: LLMClient | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.llm = llm or LLMClient(self.settings)
        self.bus = MessageBus()
        self.board = Blackboard(self.settings.state_dir)
        if self.board.get("budgets") is None:
            self.board.set("budgets", dict(d.CHANNEL_DAILY_BUDGET_INR))
        self.agents = {
            cls.name: cls(self.llm, registry, self.bus, self.board, self.settings)
            for cls in (TrackerAgent, PredictorAgent, CommanderAgent)
        }
        self._cycle = 0

    def run_cycle(self) -> CycleReport:
        self._cycle += 1
        report = CycleReport(self._cycle, "llm" if self.llm.online else "offline", completed=False)
        history_start = len(self.bus.history)
        actions_start = len(self.board.get("commander.actions", []))

        self.bus.send(Message("system", "tracker", "cycle_start", {"cycle": self._cycle}))
        for _ in range(self.settings.max_hops):
            progressed = False
            for agent in self.agents.values():
                try:
                    summary = agent.step()
                except Exception as exc:  # noqa: BLE001 - one bad agent must not kill the supervisor
                    log.exception("agent %s failed", agent.name)
                    summary = f"ERROR: {type(exc).__name__}: {exc}"
                if summary is not None:
                    report.transcript.append((agent.name, summary))
                    progressed = True
            if not progressed:
                break

        report.completed = any(m.topic == "cycle_complete" for m in self.bus.drain("system"))
        report.messages = self.bus.history[history_start:]
        report.actions = self.board.get("commander.actions", [])[actions_start:]
        return report

    def run_forever(self, cycles: int, interval_s: float = 0.0):
        for i in range(cycles):
            yield self.run_cycle()
            if interval_s and i < cycles - 1:
                time.sleep(interval_s)
