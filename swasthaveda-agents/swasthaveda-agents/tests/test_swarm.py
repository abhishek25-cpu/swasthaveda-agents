import pytest

from swasthaveda.config import Settings
from swasthaveda.swarm import Swarm
from swasthaveda.tools import ToolContext, registry


@pytest.fixture
def settings() -> Settings:
    return Settings(api_key=None, state_dir=None, dry_run=True)


def test_schema_hides_ctx_and_marks_required():
    spec = registry.specs({"reallocate_budget"})[0]
    props = spec["input_schema"]["properties"]
    assert "ctx" not in props
    assert set(spec["input_schema"]["required"]) == {"from_channel", "to_channel", "amount_inr"}


def test_offline_cycle_completes_in_order(settings):
    report = Swarm(settings).run_cycle()
    assert report.completed
    assert [a for a, _ in report.transcript] == ["tracker", "predictor", "commander"]
    topics = [m.topic for m in report.messages]
    assert topics[:3] == ["cycle_start", "market_snapshot", "action_brief"]


def test_guardrail_rejects_oversized_shift(settings):
    swarm = Swarm(settings)
    ctx = ToolContext("commander", swarm.bus, swarm.board, settings)
    out = registry.call(
        "reallocate_budget",
        {"from_channel": "meta_ads", "to_channel": "google_ads", "amount_inr": 14_000},
        ctx,
    )
    assert out["status"] == "rejected"


def test_large_but_legal_shift_needs_approval(settings):
    swarm = Swarm(settings)
    ctx = ToolContext("commander", swarm.bus, swarm.board, settings)
    out = registry.call(
        "reallocate_budget",
        {"from_channel": "meta_ads", "to_channel": "google_ads", "amount_inr": 2_900},
        ctx,
    )
    assert out["status"] == "needs_approval"


def test_agents_cannot_use_tools_outside_their_allowlist(settings):
    tracker = Swarm(settings).agents["tracker"]
    out = tracker.call_tool(
        "reallocate_budget", {"from_channel": "meta_ads", "to_channel": "google_ads", "amount_inr": 100}
    )
    assert "not permitted" in out["error"]


def test_dry_run_never_mutates_budgets(settings):
    swarm = Swarm(settings)
    before = swarm.board.get("budgets")
    swarm.run_cycle()
    assert swarm.board.get("budgets") == before
