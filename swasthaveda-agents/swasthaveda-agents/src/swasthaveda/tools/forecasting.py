"""Prediction tools (used by the Predictor). They read the Tracker's output from the blackboard."""
from __future__ import annotations

from datetime import date

from .. import domain as d
from ..data_sources import get_source
from .registry import ToolContext, registry

_ELASTICITY = 0.65  # revenue ~ spend**0.65: classic diminishing returns on ad spend


@registry.tool
def forecast_demand(horizon_days: int = 14, *, ctx: ToolContext) -> dict:
    """Forecast orders and units over the next N days from the tracker baseline, seasonality
    and search-trend momentum. Requires a tracker snapshot on the blackboard."""
    snap = ctx.board.get("tracker.channels")
    if not snap:
        return {"error": "no tracker data yet; request a market snapshot from the tracker"}
    baseline = sum(m["orders"] for m in snap["channels"].values()) / snap["days"]
    seasonal = d.SEASONALITY[date.today().month]
    momentum = (ctx.board.get("tracker.trends") or {}).get("avg_wow_change_pct", 0.0)
    trend_factor = 1 + max(-0.2, min(0.3, momentum / 100 * 0.3))
    daily = baseline * seasonal * trend_factor
    total = daily * horizon_days
    result = {
        "horizon_days": horizon_days,
        "baseline_daily_orders": round(baseline, 1),
        "seasonal_multiplier": seasonal,
        "trend_factor": round(trend_factor, 3),
        "forecast_daily_orders": round(daily, 1),
        "forecast_total_orders": round(total),
        "forecast_total_units": round(total * d.UNITS_PER_ORDER),
        "range_orders": [round(total * 0.85), round(total * 1.15)],
    }
    ctx.board.set("predictor.demand", result, ctx.agent)
    return result


@registry.tool
def forecast_roas_shift(channel: str, budget_change_pct: float, *, ctx: ToolContext) -> dict:
    """Estimate ROAS and daily revenue change if a channel's budget moves by budget_change_pct
    (e.g. +15 or -10), using a diminishing-returns model."""
    snap = ctx.board.get("tracker.channels")
    if not snap or channel not in snap["channels"]:
        return {"error": "no tracker data for that channel yet"}
    if budget_change_pct <= -100:
        return {"error": "budget_change_pct must be greater than -100"}
    m = snap["channels"][channel]
    spend = m["spend_inr"] / snap["days"]
    factor = 1 + budget_change_pct / 100
    new_spend = spend * factor
    new_roas = m["roas"] * factor ** (_ELASTICITY - 1)
    delta = new_spend * new_roas - spend * m["roas"]
    return {
        "channel": channel,
        "budget_change_pct": round(budget_change_pct, 1),
        "daily_spend_inr": round(spend),
        "new_daily_spend_inr": round(new_spend),
        "current_roas": m["roas"],
        "expected_roas": round(new_roas, 2),
        "expected_daily_revenue_delta_inr": round(delta),
    }


@registry.tool
def inventory_runway(*, ctx: ToolContext) -> dict:
    """Days of stock cover per SKU under forecast demand; lists SKUs below the low-stock threshold."""
    demand = ctx.board.get("predictor.demand") or {}
    mult = demand.get("seasonal_multiplier", 1.0) * demand.get("trend_factor", 1.0)
    skus, at_risk = {}, []
    for sku, inv in get_source().inventory().items():
        cover = inv["units_on_hand"] / max(1e-9, inv["daily_run_rate"] * mult)
        skus[sku] = {**inv, "days_of_cover": round(cover, 1)}
        if cover < d.LOW_STOCK_DAYS:
            at_risk.append(sku)
    result = {"skus": skus, "at_risk": at_risk, "low_stock_threshold_days": d.LOW_STOCK_DAYS}
    ctx.board.set("predictor.inventory", result, ctx.agent)
    return result
