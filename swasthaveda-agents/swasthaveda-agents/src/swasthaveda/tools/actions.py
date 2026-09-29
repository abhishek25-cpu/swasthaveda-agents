"""Execution tools (Commander only). Every guardrail lives HERE, in code, not in the prompt.
All actions are recorded on the blackboard; in dry-run mode (default) nothing is applied."""
from __future__ import annotations

import logging
from typing import Any

from .. import domain as d
from .registry import ToolContext, registry

log = logging.getLogger("swasthaveda")


def _record(ctx: ToolContext, kind: str, status: str, **detail: Any) -> dict:
    entry = {"kind": kind, "status": status, "agent": ctx.agent, "dry_run": ctx.settings.dry_run, **detail}
    actions = ctx.board.get("commander.actions", [])
    actions.append(entry)
    ctx.board.set("commander.actions", actions, ctx.agent)
    ctx.board.log_event("action", **entry)
    return entry


def _ok_status(ctx: ToolContext) -> str:
    return "dry_run" if ctx.settings.dry_run else "executed"


@registry.tool
def reallocate_budget(from_channel: str, to_channel: str, amount_inr: float, *, ctx: ToolContext) -> dict:
    """Move daily ad budget (INR) from one channel to another. Guardrails: capped as a percentage
    of the source budget, and larger moves need human approval."""
    g = ctx.settings.guardrails
    budgets = ctx.board.get("budgets") or {}
    args = {"from_channel": from_channel, "to_channel": to_channel, "amount_inr": amount_inr}
    if from_channel not in budgets or to_channel not in budgets or from_channel == to_channel:
        return _record(ctx, "reallocate_budget", "rejected", reason="invalid channels", **args)
    if amount_inr <= 0:
        return _record(ctx, "reallocate_budget", "rejected", reason="amount must be positive", **args)
    cap = budgets[from_channel] * g.max_budget_shift_pct / 100
    if amount_inr > cap:
        return _record(ctx, "reallocate_budget", "rejected",
                       reason=f"exceeds guardrail: max INR {cap:.0f}/day ({g.max_budget_shift_pct}% of source)", **args)
    if amount_inr > g.approval_threshold_inr:
        return _record(ctx, "reallocate_budget", "needs_approval",
                       reason=f"above INR {g.approval_threshold_inr:.0f} approval threshold", **args)
    status = _ok_status(ctx)
    if status == "executed":
        budgets[from_channel] -= amount_inr
        budgets[to_channel] += amount_inr
        ctx.board.set("budgets", budgets, ctx.agent)
    return _record(ctx, "reallocate_budget", status, **args)


@registry.tool
def launch_promo(sku: str, discount_pct: float, duration_days: int = 3, *, ctx: ToolContext) -> dict:
    """Launch a time-boxed discount on a SKU. Guardrail: discount is capped."""
    g = ctx.settings.guardrails
    args = {"sku": sku, "discount_pct": discount_pct, "duration_days": duration_days}
    if sku not in d.SKU_PRICE_INR:
        return _record(ctx, "launch_promo", "rejected", reason="unknown sku", **args)
    if not 0 < discount_pct <= g.max_discount_pct:
        return _record(ctx, "launch_promo", "rejected",
                       reason=f"discount must be in (0, {g.max_discount_pct}]%", **args)
    return _record(ctx, "launch_promo", _ok_status(ctx), **args)


@registry.tool
def schedule_content(channel: str, theme: str, publish_on: str, *, ctx: ToolContext) -> dict:
    """Schedule a content piece (theme brief) on a channel for a given ISO date (YYYY-MM-DD)."""
    args = {"channel": channel, "theme": theme, "publish_on": publish_on}
    if channel not in d.CHANNEL_DAILY_BUDGET_INR:
        return _record(ctx, "schedule_content", "rejected", reason="unknown channel", **args)
    return _record(ctx, "schedule_content", _ok_status(ctx), **args)


@registry.tool
def notify_human(severity: str, message: str, *, ctx: ToolContext) -> dict:
    """Notify the human marketing owner. severity: info | warning | critical.
    Use for anything needing approval, any guardrail rejection, or stock risk."""
    log.warning("HUMAN NOTIFICATION [%s] %s", severity, message)
    return _record(ctx, "notify_human", "sent", severity=severity, message=message)
