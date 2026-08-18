"""Historical prediction freeze and scoring using the Vaastav harness.

Usage:
    python -m engine.harness_run --season 2025-26 --gw 1
    python -m engine.harness_run --season 2025-26 --gw 1 --score
    python -m engine.harness_run --season 2025-26 --from-gw 1 --to-gw 3
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone

from engine.harness import SUPPORTED_SEASONS, build_snapshot, ensure_vaastav, gw_actuals
from engine.harness_validate import validate_snapshot
from engine.metrics import (
    PRED_COLUMNS,
    append_scores_row,
    print_summary,
    record_path,
    summarize_rows,
)
from engine.models import GWProjection, PlayerProjection
from engine.project import project_all


def freeze(season: str, gw: int, skip_validate: bool = False) -> None:
    path = record_path(gw, season=season)
    if path.exists():
        print(f"[harness_run] Record already exists: {path}")
        print("[harness_run] Delete it first if you want to re-freeze.")
        sys.exit(1)

    ensure_vaastav((season,))
    if not skip_validate:
        result = validate_snapshot(season, gw)
        print(result.report())
        if not result.passed:
            print("[harness_run] Harness validation failed. Fix before freezing.")
            sys.exit(1)

    print(f"[harness_run] Building as-of GW{gw} snapshot for {season} ...")
    snapshot = build_snapshot(season, as_of_gw=gw)
    print(f"[harness_run] Projecting GW {gw} (balanced) ...")
    projections: list[PlayerProjection] = project_all(snapshot, horizon=1, strategy="balanced")

    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for proj in projections:
        gw_proj: GWProjection | None = proj.by_gw.get(gw)
        if gw_proj is None:
            continue
        rows.append({
            "gw": gw,
            "player_id": proj.player.id,
            "web_name": proj.player.web_name,
            "team_id": proj.player.team_id,
            "position": proj.player.position,
            "now_cost": proj.player.now_cost,
            "mu": round(gw_proj.mu, 4),
            "sigma": round(gw_proj.sigma, 4),
            "p_start": round(gw_proj.p_start, 4),
            "p_sub": round(gw_proj.p_sub, 4),
            "p_60": round(gw_proj.p_60, 4),
            "p_10_plus": round(gw_proj.p_10_plus, 4),
            "n_fixtures": gw_proj.n_fixtures,
            "actual_points": "",
            "actual_minutes": "",
            "did_start": "",
            "captured_at": now,
            "scored_at": "",
        })

    if not rows:
        print(f"[harness_run] No projections for GW {gw}.")
        sys.exit(1)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[harness_run] Froze {len(rows)} rows -> {path}")


def score(season: str, gw: int) -> None:
    path = record_path(gw, season=season)
    if not path.exists():
        print(f"[harness_run] No frozen record at {path}")
        sys.exit(1)

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if rows and rows[0].get("scored_at"):
        print(f"[harness_run] GW {gw} already scored for {season}.")
        summary = summarize_rows(rows, gw)
        if summary:
            print_summary(summary)
        return

    actuals = gw_actuals(season, gw)
    if not actuals:
        print(f"[harness_run] No actuals found for {season} GW{gw}.")
        sys.exit(1)

    now = datetime.now(timezone.utc).isoformat()
    for row in rows:
        pid = int(row["player_id"])
        act = actuals.get(pid)
        if not act:
            continue
        row["actual_points"] = act["actual_points"]
        row["actual_minutes"] = act["actual_minutes"]
        row["did_start"] = act["did_start"]
        row["scored_at"] = now

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[harness_run] Scored {len(rows)} rows -> {path}")
    summary = summarize_rows(rows, gw)
    if summary:
        print_summary(summary)
        out = append_scores_row(summary, season=season)
        print(f"[harness_run] Summary appended -> {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Historical harness freeze and score.")
    parser.add_argument("--season", required=True, choices=SUPPORTED_SEASONS)
    parser.add_argument("--gw", type=int, help="Single gameweek")
    parser.add_argument("--from-gw", type=int, dest="from_gw", help="First GW in batch")
    parser.add_argument("--to-gw", type=int, dest="to_gw", help="Last GW in batch")
    parser.add_argument("--score", action="store_true", help="Score frozen record(s)")
    parser.add_argument("--skip-validate", action="store_true", help="Skip harness validation gate")
    args = parser.parse_args()

    if args.from_gw and args.to_gw:
        gws = range(args.from_gw, args.to_gw + 1)
    elif args.gw:
        gws = [args.gw]
    else:
        parser.error("Provide --gw or --from-gw/--to-gw")

    for gw in gws:
        if args.score:
            score(args.season, gw)
        else:
            freeze(args.season, gw, skip_validate=args.skip_validate)


if __name__ == "__main__":
    main()
