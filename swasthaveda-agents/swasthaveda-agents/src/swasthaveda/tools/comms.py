"""Shared communication tools available to every agent."""
from __future__ import annotations

from ..bus import Message
from .registry import ToolContext, registry

_RECIPIENTS = {"tracker", "predictor", "commander", "system"}


@registry.tool
def send_message(to: str, topic: str, payload: dict, *, ctx: ToolContext) -> dict:
    """Send a structured message to another agent (tracker, predictor, commander) or 'system'.
    Keep payloads compact and factual; put bulky data on the blackboard instead."""
    if to not in _RECIPIENTS:
        return {"error": f"unknown recipient '{to}'; choose from {sorted(_RECIPIENTS)}"}
    msg = Message(sender=ctx.agent, recipient=to, topic=topic, payload=payload)
    ctx.bus.send(msg)
    ctx.board.log_event("message", sender=ctx.agent, to=to, topic=topic)
    return {"delivered": msg.id, "to": to, "topic": topic}


@registry.tool
def write_blackboard(key: str, value: dict, *, ctx: ToolContext) -> dict:
    """Store a JSON object on the shared blackboard so other agents can read it."""
    ctx.board.set(key, value, ctx.agent)
    return {"stored": key}


@registry.tool
def read_blackboard(key: str, *, ctx: ToolContext) -> dict:
    """Read a JSON object from the shared blackboard (e.g. 'tracker.channels', 'budgets')."""
    return {"key": key, "value": ctx.board.get(key)}
