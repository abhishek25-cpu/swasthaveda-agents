"""Sensing tools (used by the Tracker). Results are also written to the blackboard so the
downstream agents never depend on the LLM relaying raw numbers correctly."""
from __future__ import annotations

import statistics
from datetime import date

from .. import domain as d
from ..data_sources import get_source
from .registry import ToolContext, registry


@registry.tool
def fetch_channel_metrics(channel: str, days: int = 7, *, ctx: ToolContext) -> dict:
    """Fetch spend, revenue, ROAS, CTR, CVR and CPA for one marketing channel over the last N days."""
    if channel not in d.CHANNEL_DAILY_BUDGET_INR:
        return {"error": f"unknown channel; choose from {sorted(d.CHANNEL_DAILY_BUDGET_INR)}"}
    return get_source().channel_metrics(channel, days)


@registry.tool
def scan_all_channels(days: int = 7, *, ctx: ToolContext) -> dict:
    """Pull metrics for every channel, compute blended ROAS and flag channels whose ROAS deviates
    from target by more than the anomaly threshold (underperforming / outperforming)."""
    src = get_source()
    channels = {c: src.channel_metrics(c, days) for c in d.CHANNEL_DAILY_BUDGET_INR}
    anomalies = []
    for c, m in channels.items():
        delta = (m["roas"] / d.ROAS_TARGET[c] - 1) * 100
        if abs(delta) < d.ANOMALY_THRESHOLD_PCT:
            continue
        anomalies.append({
            "channel": c,
            "status": "underperforming" if delta < 0 else "outperforming",
            "roas": m["roas"],
            "target_roas": d.ROAS_TARGET[c],
            "delta_pct": round(delta, 1),
        })
    spend = sum(m["spend_inr"] for m in channels.values())
    revenue = sum(m["revenue_inr"] for m in channels.values())
    result = {
        "as_of": date.today().isoformat(),
        "days": days,
        "blended_roas": round(revenue / spend, 2) if spend else 0.0,
        "channels": channels,
        "anomalies": anomalies,
    }
    ctx.board.set("tracker.channels", result, ctx.agent)
    return result


@registry.tool
def fetch_search_trends(keywords: list[str], *, ctx: ToolContext) -> dict:
    """Get search-interest index and week-over-week change for a list of keywords."""
    trends = get_source().search_trends(keywords)
    if not trends:
        return {"error": "no keywords given"}
    top = max(trends, key=lambda k: trends[k]["wow_change_pct"])
    result = {
        "trends": trends,
        "top_rising": top,
        "avg_wow_change_pct": round(statistics.mean(t["wow_change_pct"] for t in trends.values()), 1),
    }
    ctx.board.set("tracker.trends", result, ctx.agent)
    return result


@registry.tool
def fetch_competitor_prices(*, ctx: ToolContext) -> dict:
    """Compare our flagship SKU price to competitors; returns the percentage price gap."""
    rows = get_source().competitor_prices()
    ours = d.SKU_PRICE_INR[d.FLAGSHIP_SKU]
    median = statistics.median(r["price_inr"] for r in rows)
    result = {
        "sku": d.FLAGSHIP_SKU,
        "our_price_inr": ours,
        "competitor_median_inr": median,
        "gap_pct": round((ours / median - 1) * 100, 1),  # positive = we are pricier
        "competitors": rows,
    }
    ctx.board.set("tracker.pricing", result, ctx.agent)
    return result
