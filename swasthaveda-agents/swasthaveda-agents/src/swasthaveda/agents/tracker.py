from __future__ import annotations

from .. import domain as d
from ..bus import Message
from .base import BaseAgent


class TrackerAgent(BaseAgent):
    name = "tracker"
    mission = (
        "You SENSE the market. Each cycle: (1) scan_all_channels, (2) fetch_search_trends for the "
        f"brand keywords {d.TREND_KEYWORDS}, (3) fetch_competitor_prices, then (4) send ONE message to "
        "'predictor' with topic 'market_snapshot' and payload {blended_roas, anomalies, "
        "top_rising_keyword, price_gap_pct}. Report facts only; do not recommend actions."
    )
    tools = ("scan_all_channels", "fetch_channel_metrics", "fetch_search_trends",
             "fetch_competitor_prices", "send_message", "read_blackboard", "write_blackboard")

    def run_offline(self, inbox: list[Message]) -> str:
        scan = self.call_tool("scan_all_channels", {"days": 7})
        trends = self.call_tool("fetch_search_trends", {"keywords": list(d.TREND_KEYWORDS)})
        pricing = self.call_tool("fetch_competitor_prices")
        self.call_tool("send_message", {
            "to": "predictor",
            "topic": "market_snapshot",
            "payload": {
                "blended_roas": scan["blended_roas"],
                "anomalies": scan["anomalies"],
                "top_rising_keyword": trends["top_rising"],
                "price_gap_pct": pricing["gap_pct"],
            },
        })
        return (f"Scanned {len(scan['channels'])} channels (blended ROAS {scan['blended_roas']}), "
                f"{len(scan['anomalies'])} anomalies, top rising keyword '{trends['top_rising']}', "
                f"price gap {pricing['gap_pct']}% vs competitors.")
