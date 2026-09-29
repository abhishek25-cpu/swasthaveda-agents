"""Runtime configuration: environment in, one immutable Settings object out."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_dotenv(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Guardrails:
    """Hard limits enforced inside the tools, so no prompt can talk its way past them."""

    max_budget_shift_pct: float = 20.0  # of the source channel's daily budget
    max_discount_pct: float = 15.0
    approval_threshold_inr: float = 2_500.0  # larger shifts need a human


@dataclass(frozen=True)
class Settings:
    api_key: str | None = None
    model: str = "claude-sonnet-5-5"
    max_tokens: int = 2048
    max_tool_turns: int = 8  # tool-use rounds per agent step
    max_hops: int = 8  # agent hand-offs per cycle (loop breaker)
    dry_run: bool = True
    state_dir: Path | None = Path(".state")
    guardrails: Guardrails = field(default_factory=Guardrails)

    @classmethod
    def from_env(cls) -> Settings:
        _load_dotenv()
        state = os.getenv("SWASTHAVEDA_STATE_DIR", ".state")
        return cls(
            api_key=os.getenv("ANTHROPIC_API_KEY") or None,
            model=os.getenv("SWASTHAVEDA_MODEL", "claude-sonnet-5-5"),
            dry_run=_flag("SWASTHAVEDA_DRY_RUN", True),
            state_dir=Path(state) if state else None,
        )
