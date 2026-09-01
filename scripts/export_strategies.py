"""Re-solve the three V1 strategies from the cached snapshot for the live UI.

Read-only with respect to records/ and engine/. Writes only
web/public/data/season/{live}/strategies.json.

This is not a capture.py record. Squad membership was never frozen; the board
re-runs the same ILP the audit CLI uses (horizon=6) against .cache/fpl.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.api import load_snapshot
from engine.model_config import PRODUCTION
from engine.optimize import solve_squad
from engine.project import STRATEGIES, project_all

OUT = ROOT / "web" / "public" / "data"
LIVE_SEASON = "2026-27"
HORIZON = 6

CAVEAT = (
    "Re-solved from the cached FPL snapshot with engine.optimize.solve_squad "
    "(horizon=6). capture.py never persisted squad membership, so this is a "
    "viewer of the ILP, not a frozen record. Strategy changes the utility in "
    "project_all; the constraint set is the same."
)


def export_strategies(*, refresh: bool) -> int:
    snapshot = load_snapshot(refresh=refresh)
    nxt = snapshot.next_event()
    teams = {tid: t.short_name for tid, t in snapshot.teams.items()}
    as_of = snapshot.as_of.isoformat() if snapshot.as_of else None

    squads = {}
    for strategy in STRATEGIES:
        print(f"[strategies] solving {strategy} horizon={HORIZON} ...")
        projections = project_all(snapshot, horizon=HORIZON, strategy=strategy)
        by_id = {p.player.id: p for p in projections}
        sol = solve_squad(snapshot, projections, strategy=strategy)
        xi_ids = {p.id for p in sol.xi}
        players = []
        for p in sol.players:
            proj = by_id[p.id]
            players.append(
                {
                    "id": p.id,
                    "name": p.web_name,
                    "pos": p.position,
                    "cost": p.now_cost,
                    "team": p.team_id,
                    "teamCode": teams.get(p.team_id),
                    "mu": round(proj.next_mu, 4),
                    "sigma": round(proj.next_sigma, 4),
                    "p_start": round(proj.next_p_start, 4),
                    "p10": round(proj.next_p_10, 4),
                    "xi": p.id in xi_ids,
                    "bench": p.id not in xi_ids,
                    "captain": p.id == sol.captain.id,
                    "vice": p.id == sol.vice.id,
                }
            )
        squads[strategy] = {
            "strategy": strategy,
            "cost": sol.cost,
            "bank": sol.bank,
            "next_xi_mu": round(sol.next_xi_mu, 4),
            "horizon_utility": round(sol.horizon_utility, 4),
            "captain": sol.captain.web_name,
            "vice": sol.vice.web_name,
            "players": players,
        }

    payload = {
        "season": LIVE_SEASON,
        "gw": nxt.id,
        "horizon": HORIZON,
        "snapshot_as_of": as_of,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_config": {**PRODUCTION, "role": "live_resolv", "horizon": HORIZON},
        "caveats": [CAVEAT],
        "squads": squads,
    }
    dest = OUT / "season" / LIVE_SEASON / "strategies.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[strategies] wrote {dest}")
    print(f"[strategies] snapshot_as_of={as_of}  gw={nxt.id}")
    for key, squad in squads.items():
        xi = [p["name"] for p in squad["players"] if p["xi"]]
        print(f"  {key}: C {squad['captain']}  XI {', '.join(xi)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Re-solve safe/balanced/aggressive for the live UI board."
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force a fresh FPL API fetch (ignores the 30-minute cache TTL).",
    )
    args = parser.parse_args()
    return export_strategies(refresh=args.refresh)


if __name__ == "__main__":
    raise SystemExit(main())
