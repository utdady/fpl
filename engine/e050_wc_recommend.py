"""E050-A product surface: Wildcard recommendation (frozen policy).

Usage:
    python -m engine.e050_wc_recommend
    python -m engine.e050_wc_recommend --season 2024-25
    python -m engine.e050_wc_recommend --squad myteam.json
    python -m engine.e050_wc_recommend --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.api import load_snapshot
from engine.e050_wc_policy import (
    GATE_NOTE,
    INDEPENDENCE,
    format_recommendation,
    recommend_historical,
    recommend_live,
)
from engine.suggest import parse_my_team


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="E050-A frozen Wildcard recommendation (not a chip optimizer).",
    )
    parser.add_argument(
        "--season",
        default=None,
        help="Historical season key (as-of-t path). Default: live remaining GWs.",
    )
    parser.add_argument(
        "--squad",
        default=None,
        help="Optional my-team JSON (15 picks) as sticky held for live path.",
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.season and args.squad:
        print("error: --squad applies to live path only (not --season)", file=sys.stderr)
        return 2

    if args.season:
        rec = recommend_historical(args.season)
    else:
        held_ids = None
        if args.squad:
            raw = Path(args.squad).read_text(encoding="utf-8")
            state = parse_my_team(json.loads(raw))
            held_ids = list(state.owned_ids)
        snap = load_snapshot(refresh=args.refresh)
        rec = recommend_live(snap, held_ids=held_ids)

    if args.json:
        print(
            json.dumps(
                {
                    "policy_id": rec.policy_id,
                    "t_star": rec.t_star,
                    "u_wc": rec.u_wc,
                    "n_tau": rec.n_tau,
                    "blank_ids": list(rec.blank_ids),
                    "blank_names": list(rec.blank_names),
                    "held_ids": list(rec.held_ids),
                    "held_freeze_gw": rec.held_freeze_gw,
                    "claim": rec.claim,
                    "independence": INDEPENDENCE,
                    "live_semantics": rec.live_semantics,
                    "gate_note": GATE_NOTE,
                    "n_scored_gws": len(rec.rows),
                    "rows": [
                        {
                            "gw": r.gw,
                            "u_wc": r.u_wc,
                            "n_tau": r.n_tau,
                            "blank_ids": list(r.blank_ids),
                            "excluded": r.excluded,
                            "exclude_reason": r.exclude_reason,
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
