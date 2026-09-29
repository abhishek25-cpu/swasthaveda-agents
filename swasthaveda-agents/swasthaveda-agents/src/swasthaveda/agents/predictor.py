from __future__ import annotations

from .. import domain as d
from ..bus import Message
from .base import BaseAgent, latest


class PredictorAgent(BaseAgent):
    name = "predictor"
    mission = (
        "You PREDICT. On a 'market_snapshot': run forecast_demand and inventory_runway, then test "
        "candidate budget moves (from an underperforming channel to an outperforming one, sized at "
        "most 15% of the source budget) with forecast_roas_shift on BOTH channels and add the "
        "revenue deltas. Keep only moves with a positive net delta. Send ONE message to 'commander', "
        "topic 'action_brief', payload {demand, risks, recommended_shifts:[{from_channel, to_channel, "
        "amount_inr, net_daily_revenue_delta_inr}], promo:{sku, discount_pct}|null, rationale}. "
        "Only propose a promo if we are priced >8% above competitors and no SKU is at stock risk."
    )
    tools = ("forecast_demand", "forecast_roas_shift", "inventory_runway",
             "send_message", "read_blackboard", "write_blackboard")

    def run_offline(self, inbox: list[Message]) -> str:
        msg = latest(inbox, "market_snapshot")
        if msg is None:
            return "No market snapshot received; idle."
        snap = msg.payload
        demand = self.call_tool("forecast_demand", {"horizon_days": 14})
        runway = self.call_tool("inventory_runway")
        budgets = self.board.get("budgets") or {}

        under = sorted((a for a in snap["anomalies"] if a["status"] == "underperforming"),
                       key=lambda a: a["delta_pct"])
        over = sorted((a for a in snap["anomalies"] if a["status"] == "outperforming"),
                      key=lambda a: -a["delta_pct"])
        shifts = []
        if under and over:
            src, dst = under[0]["channel"], over[0]["channel"]
            amount = round(budgets[src] * 0.15)
            gain = self.call_tool("forecast_roas_shift", {
                "channel": dst, "budget_change_pct": amount / budgets[dst] * 100})
            loss = self.call_tool("forecast_roas_shift", {
                "channel": src, "budget_change_pct": -amount / budgets[src] * 100})
            net = gain.get("expected_daily_revenue_delta_inr", 0) + loss.get("expected_daily_revenue_delta_inr", 0)
            if net > 0:
                shifts.append({"from_channel": src, "to_channel": dst, "amount_inr": amount,
                               "net_daily_revenue_delta_inr": net})

        at_risk = runway.get("at_risk", [])
        promo = ({"sku": d.FLAGSHIP_SKU, "discount_pct": 10}
                 if snap["price_gap_pct"] > 8 and not at_risk else None)
        self.call_tool("send_message", {
            "to": "commander",
            "topic": "action_brief",
            "payload": {
                "demand": {k: demand.get(k) for k in ("forecast_daily_orders", "forecast_total_units")},
                "risks": [f"low_stock:{s}" for s in at_risk],
                "recommended_shifts": shifts,
                "promo": promo,
                "rationale": "Shift spend from weakest to strongest channel only if net revenue "
                             "improves after diminishing returns; discount only when overpriced.",
            },
        })
        return (f"Forecast {demand.get('forecast_daily_orders')} orders/day; "
                f"{len(shifts)} budget shift(s) recommended; promo={'yes' if promo else 'no'}; "
                f"stock risks={at_risk or 'none'}.")
