"""engine/capture.py – prediction freeze and post-GW scoring.

Usage
-----
Freeze predictions before deadline / kickoff:
    python -m engine.capture --gw 1

Score frozen predictions after GW results land:
    python -m engine.capture --gw 1 --score

Records are written to records/gw{N:02d}_v1.0.csv.
After scoring, a summary is printed and appended to records/scores.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from engine.api import load_snapshot
from engine.models import GWProjection, PlayerProjection
from engine.project import project_all

RECORDS_DIR = Path("records")
RECORDS_DIR.mkdir(exist_ok=True)

SCORES_CSV = RECORDS_DIR / "scores.csv"

PRED_COLUMNS = [
    "gw",
    "player_id",
    "web_name",
    "team_id",
    "position",
    "now_cost",
    "mu",
    "sigma",
    "p_start",
    "p_sub",
    "p_60",
    "p_10_plus",
    "n_fixtures",
    "actual_points",
    "actual_minutes",
    "did_start",
    "captured_at",
    "scored_at",
]


def _record_path(gw: int) -> Path:
    return RECORDS_DIR / f"gw{gw:02d}_v1.0.csv"


def freeze(gw: int, refresh: bool = False) -> None:
    """Serialize projections for gw to CSV before results land."""
    path = _record_path(gw)
    if path.exists():
        print(f"[capture] Record already exists: {path}")
        print("[capture] Delete it first if you want to re-freeze.")
        sys.exit(1)

    print(f"[capture] Loading snapshot (refresh={refresh}) ...")
    snapshot = load_snapshot(refresh=refresh)

    print(f"[capture] Projecting GW {gw} (balanced strategy) ...")
    projections: list[PlayerProjection] = project_all(
        snapshot, horizon=1, strategy="balanced"
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
        print(f"[capture] No projections found for GW {gw}. Check the snapshot.")
        sys.exit(1)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[capture] Froze {len(rows)} player projections -> {path}")


def _fetch_event_live(gw: int) -> dict[int, dict]:
    url = f"https://fantasy.premierleague.com/api/event/{gw}/live/"
    req = urllib.request.Request(url, headers={"User-Agent": "fpl-model/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    return {e["id"]: e for e in data.get("elements", [])}


def score(gw: int) -> None:
    """Fetch actuals and append to the frozen record, then print calibration."""
    path = _record_path(gw)
    if not path.exists():
        print(f"[capture] No frozen record found at {path}.")
        print(f"[capture] Run: python -m engine.capture --gw {gw}  first.")
        sys.exit(1)

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if rows and rows[0].get("scored_at"):
        print(f"[capture] GW {gw} already scored.")
        _print_summary(rows, gw)
        return

    print(f"[capture] Fetching live GW {gw} data ...")
    live = _fetch_event_live(gw)

    now = datetime.now(timezone.utc).isoformat()
    for row in rows:
        pid = int(row["player_id"])
        elem = live.get(pid)
        if elem is None:
            continue
        stats = elem.get("stats", {})
        row["actual_points"] = stats.get("total_points", "")
        row["actual_minutes"] = stats.get("minutes", "")
        minutes = int(stats.get("minutes", 0))
        # FPL does not expose "started" directly; >= 45 min is the proxy.
        row["did_start"] = int(minutes >= 45)
        row["scored_at"] = now

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[capture] Scored {len(rows)} rows -> {path}")
    _print_summary(rows, gw)
    _append_scores_row(rows, gw)


def _safe_float(val) -> float | None:
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _spearman(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")

    def ranks(vals):
        sorted_idx = sorted(range(n), key=lambda i: vals[i])
        r = [0.0] * n
        for rank, i in enumerate(sorted_idx, 1):
            r[i] = rank
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx = statistics.mean(rx)
    my = statistics.mean(ry)
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den = math.sqrt(
        sum((rx[i] - mx) ** 2 for i in range(n))
        * sum((ry[i] - my) ** 2 for i in range(n))
    )
    return num / den if den else 0.0


def _calibration_error(pairs: list[tuple[float, int]], n_bins: int = 5) -> float:
    if not pairs:
        return float("nan")
    bins: list[list] = [[] for _ in range(n_bins)]
    for prob, outcome in pairs:
        b = min(int(prob * n_bins), n_bins - 1)
        bins[b].append((prob, outcome))
    total = len(pairs)
    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        mean_prob = statistics.mean(p for p, _ in bucket)
        mean_out = statistics.mean(o for _, o in bucket)
        ece += (len(bucket) / total) * abs(mean_prob - mean_out)
    return ece


def _print_summary(rows: list[dict], gw: int) -> None:
    scored = [r for r in rows if r.get("actual_points") != ""]
    if not scored:
        print("[capture] No actuals available yet.")
        return

    errors, sq_errors, pairs = [], [], []
    p_start_pairs: list[tuple[float, int]] = []
    p10_pairs: list[tuple[float, int]] = []

    for r in scored:
        mu = _safe_float(r["mu"])
        act = _safe_float(r["actual_points"])
        if mu is None or act is None:
            continue
        e = act - mu
        errors.append(e)
        sq_errors.append(e ** 2)
        pairs.append((mu, act))
        p_start = _safe_float(r["p_start"])
        did_start = _safe_float(r["did_start"])
        if p_start is not None and did_start is not None:
            p_start_pairs.append((p_start, int(did_start)))
        p10 = _safe_float(r["p_10_plus"])
        if p10 is not None and act is not None:
            p10_pairs.append((p10, int(act >= 10)))

    n = len(errors)
    if n == 0:
        print("[capture] No scoreable rows.")
        return

    mae = statistics.mean(abs(e) for e in errors)
    rmse = math.sqrt(statistics.mean(sq_errors))
    bias = statistics.mean(errors)
    spearman = _spearman([mu for mu, _ in pairs], [act for _, act in pairs])
    p_start_cal = _calibration_error(p_start_pairs) if p_start_pairs else float("nan")
    p10_cal = _calibration_error(p10_pairs) if p10_pairs else float("nan")

    print()
    print(f"=== GW {gw} Prediction Scorecard (n={n}) ===")
    print(f"  MAE:              {mae:.3f}")
    print(f"  RMSE:             {rmse:.3f}")
    print(f"  Bias (mean err):  {bias:+.3f}")
    print(f"  Spearman r:       {spearman:.3f}")
    print(f"  p_start ECE:      {p_start_cal:.3f}")
    print(f"  p_10_plus ECE:    {p10_cal:.3f}")
    print()


def _append_scores_row(rows: list[dict], gw: int) -> None:
    errors, sq_errors, pairs = [], [], []
    for r in rows:
        mu = _safe_float(r.get("mu"))
        act = _safe_float(r.get("actual_points"))
        if mu is None or act is None:
            continue
        e = act - mu
        errors.append(e)
        sq_errors.append(e ** 2)
        pairs.append((mu, act))
    if not errors:
        return
    mae = statistics.mean(abs(e) for e in errors)
    rmse = math.sqrt(statistics.mean(sq_errors))
    bias = statistics.mean(errors)
    spearman = _spearman([mu for mu, _ in pairs], [act for _, act in pairs])
    columns = ["gw", "n", "mae", "rmse", "bias", "spearman", "scored_at"]
    header_needed = not SCORES_CSV.exists()
    with SCORES_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if header_needed:
            writer.writeheader()
        writer.writerow({
            "gw": gw,
            "n": len(errors),
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "bias": round(bias, 4),
            "spearman": round(spearman, 4),
            "scored_at": datetime.now(timezone.utc).isoformat(),
        })
    print(f"[capture] Summary appended -> {SCORES_CSV}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze projections before GW deadline, score after results."
    )
    parser.add_argument("--gw", type=int, required=True, help="Gameweek number")
    parser.add_argument(
        "--score",
        action="store_true",
        help="Fetch actuals and score the frozen prediction (run after results).",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force a fresh API pull when freezing.",
    )
    args = parser.parse_args()

    if args.score:
        score(args.gw)
    else:
        freeze(args.gw, refresh=args.refresh)


if __name__ == "__main__":
    main()
