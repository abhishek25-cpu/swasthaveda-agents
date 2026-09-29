"""Data adapters. Implement `DataSource` against Meta/Google Ads, Shopify, GA4, Amazon, etc.,
then call `set_source(MyRealSource())`. The default is a deterministic simulator."""
from __future__ import annotations

import random
from datetime import date
from typing import Protocol

from . import domain as d


class DataSource(Protocol):
    def channel_metrics(self, channel: str, days: int) -> dict: ...
    def search_trends(self, keywords: list[str]) -> dict[str, dict]: ...
    def competitor_prices(self) -> list[dict]: ...
    def inventory(self) -> dict[str, dict]: ...


class SimulatedSource:
    """Synthetic but stable-per-day data so the whole swarm runs end to end offline."""

    @staticmethod
    def _rng(*parts: object) -> random.Random:
        return random.Random("|".join([date.today().isoformat(), *map(str, parts)]))

    def channel_metrics(self, channel: str, days: int) -> dict:
        rng = self._rng("metrics", channel, days)
        spend = d.CHANNEL_DAILY_BUDGET_INR[channel] * days * rng.uniform(0.9, 1.05)
        roas = d.ROAS_TARGET[channel] * rng.uniform(0.6, 1.4)
        revenue = spend * roas
        orders = max(1, round(revenue / d.AOV_INR))
        impressions = int(spend / rng.uniform(80, 160) * 1000)
        clicks = max(1, int(impressions * rng.uniform(0.008, 0.03)))
        return {
            "channel": channel,
            "days": days,
            "spend_inr": round(spend),
            "revenue_inr": round(revenue),
            "orders": orders,
            "impressions": impressions,
            "clicks": clicks,
            "roas": round(roas, 2),
            "ctr_pct": round(clicks / impressions * 100, 2) if impressions else 0.0,
            "cvr_pct": round(orders / clicks * 100, 2),
            "cpa_inr": round(spend / orders),
        }

    def search_trends(self, keywords: list[str]) -> dict[str, dict]:
        out = {}
        for kw in keywords:
            rng = self._rng("trend", kw)
            out[kw] = {"interest": rng.randint(30, 100), "wow_change_pct": round(rng.uniform(-15, 40), 1)}
        return out

    def competitor_prices(self) -> list[dict]:
        base = d.SKU_PRICE_INR[d.FLAGSHIP_SKU]
        return [
            {
                "competitor": f"Competitor {c}",
                "sku": d.FLAGSHIP_SKU,
                "price_inr": round(base * self._rng("price", c).uniform(0.85, 1.2)),
            }
            for c in "ABC"
        ]

    def inventory(self) -> dict[str, dict]:
        out = {}
        for sku in d.SKU_PRICE_INR:
            rng = self._rng("inventory", sku)
            out[sku] = {"units_on_hand": rng.randint(300, 4000), "daily_run_rate": rng.randint(20, 120)}
        return out


_source: DataSource = SimulatedSource()


def get_source() -> DataSource:
    return _source


def set_source(source: DataSource) -> None:
    global _source
    _source = source
