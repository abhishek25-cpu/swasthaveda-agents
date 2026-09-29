from __future__ import annotations

from datetime import date, timedelta

from ..bus import Message
from .base import BaseAgent, latest


class CommanderAgent(BaseAgent):
    name = "commander"
    mission = (
        "You ACT; you are the only agent allowed to. On an 'action_brief': execute each recommended "
        "shift with reallocate_budget; launch the promo (if any) with launch_promo, but skip it when "
        "risks mention low_stock; schedule_content on the best-performing channel about the top "
        "rising keyword (read 'tracker.channels' and 'tracker.trends' from the blackboard); "
        "notify_human about warnings, guardrail rejections and approvals needed. Finally send "
        "'system' the topic 'cycle_complete' with payload {actions_taken, skipped, reasons}. "
        "Guardrail rejections are final; never retry them with tweaked arguments."
    )
    tools = ("reallocate_budget", "launch_promo", "schedule_content", "notify_human",
             "send_message", "read_blackboard", "write_blackboard")

    def run_offline(self, inbox: list[Message]) -> str:
        msg = latest(inbox, "action_brief")
        if msg is None:
            return "No action brief received; idle."
        brief = msg.payload
        done, skipped = [], []

        def track(result: dict) -> None:
            (done if result["status"] in {"executed", "dry_run"} else skipped).append(result)

        for s in brief.get("recommended_shifts", []):
            track(self.call_tool("reallocate_budget", {
                "from_channel": s["from_channel"], "to_channel": s["to_channel"],
                "amount_inr": s["amount_inr"]}))
        if brief.get("promo"):
            track(self.call_tool("launch_promo", dict(brief["promo"])))

        channels = (self.board.get("tracker.channels") or {}).get("channels", {})
        keyword = (self.board.get("tracker.trends") or {}).get("top_rising")
        if channels and keyword:
            best = max(channels.values(), key=lambda m: m["roas"])["channel"]
            track(self.call_tool("schedule_content", {
                "channel": best,
                "theme": f"Educational content around '{keyword}'",
                "publish_on": (date.today() + timedelta(days=1)).isoformat()}))

        if brief.get("risks") or skipped:
            self.call_tool("notify_human", {
                "severity": "warning",
                "message": f"Risks: {brief.get('risks') or 'none'}; "
                           f"{len(skipped)} action(s) rejected or awaiting approval."})

        self.call_tool("send_message", {
            "to": "system",
            "topic": "cycle_complete",
            "payload": {"actions_taken": len(done), "skipped": len(skipped)},
        })
        return f"{len(done)} action(s) {'simulated' if self.settings.dry_run else 'executed'}, {len(skipped)} skipped."
