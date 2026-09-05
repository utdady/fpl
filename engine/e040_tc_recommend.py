"""E040-A product surface: Triple Captain recommendation (frozen policy).

Usage:
    python -m engine.e040_tc_recommend
    python -m engine.e040_tc_recommend --season 2024-25
    python -m engine.e040_tc_recommend --json
"""
from __future__ import annotations

import argparse
import json
import sys

from engine.api import load_snapshot
from engine.e040_tc_policy import (
    format_recommendation,
    recommend_historical,
    recommend_live,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="E040-A frozen Triple Captain recommendation (not a chip optimizer).",
    )
    parser.add_argument(
        "--season",
        default=None,
        help="Historical season key (as-of-t path). Default: live snapshot remaining GWs.",
    )
    parser.add_argument("--refresh", action="store_true", help="bypass live API cache")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.season:
        rec = recommend_historical(args.season)
    else:
        snap = load_snapshot(refresh=args.refresh)
        rec = recommend_live(snap)

    if args.json:
        print(
            json.dumps(
                {
                    "policy_id": rec.policy_id,
                    "t_star": rec.t_star,
                    "captain_id": rec.captain_id,
                    "captain_name": rec.captain_name,
                    "u_capt": rec.u_capt,
                    "claim": rec.claim,
                    "live_semantics": rec.live_semantics,
                    "n_scored_gws": len(rec.rows),
                    "rows": [
                        {
                            "gw": r.gw,
                            "captain_id": r.captain_id,
                            "captain_name": r.captain_name,
                            "u_capt": r.u_capt,
                            "source": r.source,
                        }
                        for r in rec.rows
                    ],
                },
                indent=2,
            )
        )
    else:
        print(format_recommendation(rec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
