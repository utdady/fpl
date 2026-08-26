"""Historical prediction freeze and scoring using the Vaastav harness.

Usage:
    python -m engine.harness_run --season 2025-26 --gw 1
    python -m engine.harness_run --season 2025-26 --gw 1 --score
    python -m engine.harness_run --season 2025-26 --from-gw 1 --to-gw 38 --skip-existing
    python -m engine.harness_run --season 2025-26 --from-gw 1 --to-gw 38 --score --skip-existing
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


def freeze(season: str, gw: int, skip_validate: bool = False) -> bool:
  path = record_path(gw, season=season)
  if path.exists():
    return False

  ensure_vaastav((season,))
  if not skip_validate:
    result = validate_snapshot(season, gw)
    if gw == 1 or not skip_validate:
      print(result.report())
    if not result.passed:
      print("[harness_run] Harness validation failed. Fix before freezing.")
      sys.exit(1)

  print(f"[harness_run] GW{gw}: building snapshot and projecting ...")
  snapshot = build_snapshot(season, as_of_gw=gw)
  projections: list[PlayerProjection] = project_all(
      snapshot, horizon=1, strategy="balanced", minutes_version="v1"
  )

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
  return True


def score(season: str, gw: int, quiet: bool = False) -> bool:
  path = record_path(gw, season=season)
  if not path.exists():
    if not quiet:
      print(f"[harness_run] No frozen record at {path}")
    return False

  with path.open(newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

  if rows and rows[0].get("scored_at"):
    return False

  actuals = gw_actuals(season, gw)
  if not actuals:
    if not quiet:
      print(f"[harness_run] No actuals found for {season} GW{gw}.")
    return False

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

  summary = summarize_rows(rows, gw)
  if summary:
    if not quiet:
      print(f"[harness_run] GW{gw} MAE={summary['mae']:.3f} Spearman={summary['spearman']:.3f}")
    append_scores_row(summary, season=season)
  return True


def main() -> None:
  parser = argparse.ArgumentParser(description="Historical harness freeze and score.")
  parser.add_argument("--season", required=True, choices=SUPPORTED_SEASONS)
  parser.add_argument("--gw", type=int, help="Single gameweek")
  parser.add_argument("--from-gw", type=int, dest="from_gw", help="First GW in batch")
  parser.add_argument("--to-gw", type=int, dest="to_gw", help="Last GW in batch")
  parser.add_argument("--score", action="store_true", help="Score frozen record(s)")
  parser.add_argument("--skip-validate", action="store_true", help="Skip harness validation gate")
  parser.add_argument("--skip-existing", action="store_true", help="Skip GWs that already have records")
  args = parser.parse_args()

  if args.from_gw and args.to_gw:
    gws = range(args.from_gw, args.to_gw + 1)
  elif args.gw:
    gws = [args.gw]
  else:
    parser.error("Provide --gw or --from-gw/--to-gw")

  frozen = scored = skipped = 0
  for gw in gws:
    if args.score:
      if score(args.season, gw, quiet=len(gws) > 1):
        scored += 1
      else:
        skipped += 1
    else:
      if args.skip_existing and record_path(gw, season=args.season).exists():
        skipped += 1
        continue
      validate = (gw == 1) and not args.skip_validate
      if freeze(args.season, gw, skip_validate=not validate):
        frozen += 1

  if len(gws) > 1:
    action = "scored" if args.score else "frozen"
    print(f"[harness_run] Done: {action}={scored if args.score else frozen}, skipped={skipped}")


if __name__ == "__main__":
  main()
