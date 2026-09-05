"""V1 CLI: live projections + £100m squad / XI / captain.

Usage:
    python fpl.py --horizon 6 --strategy balanced
    python fpl.py suggest --squad myteam.json
    python fpl.py suggest --squad myteam.json --allow-hit --json
    python fpl.py tc
    python fpl.py tc --season 2024-25
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python fpl.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.api import load_snapshot
from engine.display import render, render_suggestions
from engine.model_config import PRODUCTION
from engine.optimize import solve_squad
from engine.project import STRATEGIES, project_all
from engine.suggest import result_to_json, suggest_from_payload


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "suggest":
        return _suggest_cli(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "tc":
        from engine.e040_tc_recommend import main as tc_main

        return tc_main(sys.argv[2:])
    return _greenfield_cli()


def _greenfield_cli() -> int:
    parser = argparse.ArgumentParser(description="FPL V1 projection + squad optimizer")
    parser.add_argument("--horizon", type=int, default=6, help="gameweeks to look ahead")
    parser.add_argument(
        "--strategy",
        choices=STRATEGIES,
        default="balanced",
        help="safe: mean - 0.4 sd; balanced: mean; aggressive: mean + 3 P(10+)",
    )
    parser.add_argument("--top", type=int, default=20, help="how many GW projections to print")
    parser.add_argument("--refresh", action="store_true", help="bypass the 30-minute API cache")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.horizon < 1 or args.horizon > 10:
        parser.error("--horizon must be between 1 and 10")

    snapshot = load_snapshot(refresh=args.refresh)
    projections = project_all(snapshot, horizon=args.horizon, strategy=args.strategy, seed=args.seed)
    solution = solve_squad(snapshot, projections, strategy=args.strategy)
    print(render(snapshot, projections, solution, top_n=args.top))
    return 0


def _suggest_cli(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        prog="fpl.py suggest",
        description="Rank transfer plans from an owned 15 (current-version, not V5/V7).",
    )
    parser.add_argument(
        "--squad",
        required=True,
        help="my-team JSON path, or - for stdin",
    )
    parser.add_argument("--allow-hit", action="store_true", help="also rank ft+1 plans with -4 deducted")
    parser.add_argument("--json", action="store_true", help="stdout JSON only (for the web API)")
    parser.add_argument("--refresh", action="store_true", help="bypass snapshot and projection caches")
    parser.add_argument(
        "--strategy",
        choices=STRATEGIES,
        default=PRODUCTION["strategy"],
    )
    parser.add_argument("--horizon", type=int, default=PRODUCTION["horizon_resolv"])
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    if args.squad == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(args.squad).read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"invalid squad JSON: {exc}", file=sys.stderr)
        return 2

    if not args.json:
        print("[suggest] loading snapshot + projections…", file=sys.stderr)
    snapshot = load_snapshot(refresh=args.refresh)
    result = suggest_from_payload(
        payload,
        snapshot=snapshot,
        strategy=args.strategy,
        horizon=args.horizon,
        seed=args.seed,
        refresh=args.refresh,
        allow_hit=args.allow_hit,
    )
    if args.json:
        print(json.dumps(result_to_json(result), separators=(",", ":")))
    else:
        print(render_suggestions(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
