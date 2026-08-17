"""V1 CLI: live projections + £100m squad / XI / captain.

Usage:
    python fpl.py --horizon 6 --strategy balanced
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python fpl.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.api import load_snapshot
from engine.display import render
from engine.optimize import solve_squad
from engine.project import STRATEGIES, project_all


def main() -> int:
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


if __name__ == "__main__":
    raise SystemExit(main())
