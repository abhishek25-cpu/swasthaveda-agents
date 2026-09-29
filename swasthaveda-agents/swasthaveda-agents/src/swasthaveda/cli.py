"""Command line entry point: `swasthaveda run --cycles 1`."""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, replace

from rich.console import Console
from rich.logging import RichHandler
from rich.markup import escape
from rich.table import Table

from .config import Settings
from .swarm import CycleReport, Swarm
from .tools import registry


def _render(report: CycleReport, console: Console) -> None:
    console.rule(f"[bold]Cycle {report.cycle}[/] | mode={report.mode} | completed={report.completed}")
    for agent, summary in report.transcript:
        console.print(f"[bold cyan]{agent:<10}[/] {escape(summary)}")
    table = Table(title="Commander actions", show_lines=True)
    for col in ("kind", "status", "detail"):
        table.add_column(col)
    for a in report.actions:
        detail = {k: v for k, v in a.items() if k not in {"kind", "status", "agent", "dry_run"}}
        table.add_row(a["kind"], a["status"], escape(json.dumps(detail, default=str)))
    console.print(table)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="swasthaveda", description="Swasthaveda Honey marketing swarm")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run the tracker -> predictor -> commander loop")
    run.add_argument("--cycles", type=int, default=1)
    run.add_argument("--interval", type=float, default=0.0, help="seconds between cycles")
    run.add_argument("--live", action="store_true", help="execute actions (default: dry-run)")
    run.add_argument("--offline", action="store_true", help="force heuristic mode (no LLM calls)")
    run.add_argument("--json", action="store_true", help="emit machine-readable reports")
    run.add_argument("-v", "--verbose", action="store_true", help="log every tool call")
    sub.add_parser("tools", help="list registered tools")
    args = parser.parse_args(argv)

    if args.cmd == "tools":
        print("\n".join(registry.names()))
        return 0

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
        handlers=[RichHandler(show_path=False, rich_tracebacks=True)],
    )
    settings = Settings.from_env()
    if args.live:
        settings = replace(settings, dry_run=False)
    if args.offline:
        settings = replace(settings, api_key=None)

    console = Console()
    swarm = Swarm(settings)
    for report in swarm.run_forever(args.cycles, args.interval):
        if args.json:
            print(json.dumps(asdict(report), default=str))
        else:
            _render(report, console)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
