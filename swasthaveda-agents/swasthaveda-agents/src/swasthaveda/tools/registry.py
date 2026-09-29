"""Tool registry: decorate a plain function and it becomes an LLM tool with an auto-built JSON
schema. One registry is shared by all agents; per-agent allowlists decide who may call what."""
from __future__ import annotations

import inspect
import typing
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from ..blackboard import Blackboard
from ..bus import MessageBus
from ..config import Settings

_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean",
               dict: "object", list: "array"}


@dataclass
class ToolContext:
    """Injected into any tool that declares a keyword-only `ctx` parameter."""

    agent: str
    bus: MessageBus
    board: Blackboard
    settings: Settings


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    fn: Callable[..., Any]
    wants_ctx: bool

    def to_anthropic(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema}


def _json_type(tp: Any) -> dict:
    origin = typing.get_origin(tp)
    if origin is list:
        args = typing.get_args(tp) or (str,)
        return {"type": "array", "items": _json_type(args[0])}
    if origin is dict:
        return {"type": "object"}
    return {"type": _JSON_TYPES.get(tp, "string")}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def tool(self, fn: Callable | None = None, *, name: str | None = None):
        def wrap(f: Callable) -> Callable:
            try:
                hints = typing.get_type_hints(f)
            except Exception:
                hints = {}
            props: dict[str, dict] = {}
            required: list[str] = []
            for pname, p in inspect.signature(f).parameters.items():
                if pname == "ctx":
                    continue
                schema = _json_type(hints.get(pname, str))
                if p.default is inspect.Parameter.empty:
                    required.append(pname)
                else:
                    schema["default"] = p.default
                props[pname] = schema
            input_schema: dict[str, Any] = {"type": "object", "properties": props}
            if required:
                input_schema["required"] = required
            tname = name or f.__name__
            self._tools[tname] = Tool(
                name=tname,
                description=inspect.getdoc(f) or tname,
                input_schema=input_schema,
                fn=f,
                wants_ctx="ctx" in inspect.signature(f).parameters,
            )
            return f

        return wrap(fn) if fn else wrap

    def names(self) -> list[str]:
        return sorted(self._tools)

    def specs(self, allowed: Iterable[str]) -> list[dict]:
        allowed = set(allowed)
        return [t.to_anthropic() for n, t in self._tools.items() if n in allowed]

    def call(self, name: str, args: dict, ctx: ToolContext) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            return {"error": f"unknown tool '{name}'"}
        kwargs = dict(args)
        if tool.wants_ctx:
            kwargs["ctx"] = ctx
        try:
            return tool.fn(**kwargs)
        except TypeError as exc:  # bad arguments from the model: return as data so it can retry
            return {"error": f"bad arguments for '{name}': {exc}"}
        except Exception as exc:  # noqa: BLE001 - tools must never crash the agent loop
            return {"error": f"{type(exc).__name__}: {exc}"}


registry = ToolRegistry()
