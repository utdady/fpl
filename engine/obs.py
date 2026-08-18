"""Observational diagnostics E008 / E009 / conditional MAE.

Read-only against historical records and Vaastav. Does not import or call
project_all / solve_squad. Cannot change Friday's squad.

Usage:
    python -m engine.obs --season 2025-26
    python -m engine.obs --season 2024-25
"""
from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path

from engine.harness import (
    PREV_SEASON,
    SUPPORTED_SEASONS,
    _i,
    _read_csv,
    ensure_vaastav,
    gw_actuals,
    gw_xp,
    season_dir,
)
from engine.metrics import record_path, safe_float, spearman

# Pre-registered 2026-08-18, before looking at per-GW xP-vs-actual tables.
LEAKAGE_SPEARMAN = 0.70

BUCKETS = [
    ("0.90-1.00", 0.90, 1.01),
    ("0.80-0.90", 0.80, 0.90),
    ("0.70-0.80", 0.70, 0.80),
    ("0.60-0.70", 0.60, 0.70),
    ("<0.60", 0.00, 0.60),
]


def new_club_ids(season: str) -> set[int]:
    prev = PREV_SEASON.get(season)
    if not prev:
        return set()
    old_team: dict[int, int] = {}
    for row in _read_csv(season_dir(prev) / "players_raw.csv"):
        code = _i(row.get("code"))
        if code:
            old_team[code] = _i(row.get("team"))
    out: set[int] = set()
    for row in _read_csv(season_dir(season) / "players_raw.csv"):
        eid = _i(row.get("id"))
        code = _i(row.get("code"))
        team = _i(row.get("team"))
        if not eid or not code:
            continue
        if code not in old_team or old_team[code] != team:
            out.add(eid)
    return out


def _mae_bias(preds: list[float], acts: list[float]) -> tuple[float, float]:
    err = [a - p for p, a in zip(preds, acts)]
    if not err:
        return float("nan"), float("nan")
    mae = statistics.mean(abs(e) for e in err)
    bias = statistics.mean(err)
    return mae, bias


def run_e008(season: str) -> list[dict]:
    rows = []
    n_flag = 0
    for gw in range(1, 39):
        xp = gw_xp(season, gw)
        act = gw_actuals(season, gw)
        xs, ys = [], []
        for pid, pred in xp.items():
            a = act.get(pid)
            if a is None:
                continue
            xs.append(pred)
            ys.append(float(a["actual_points"]))
        if len(xs) < 10:
            sp = mae = bias = float("nan")
            n = len(xs)
        else:
            n = len(xs)
            sp = spearman(xs, ys)
            mae, bias = _mae_bias(xs, ys)
        flagged = int(sp == sp and sp > LEAKAGE_SPEARMAN)
        n_flag += flagged
        rows.append({
            "season": season,
            "gw": gw,
            "n": n,
            "spearman": round(sp, 4) if sp == sp else "",
            "mae": round(mae, 4) if mae == mae else "",
            "bias": round(bias, 4) if bias == bias else "",
            "leakage_flag": flagged,
        })
    path = Path("records") / "historical" / season / "b0_leakage.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    sps = [float(r["spearman"]) for r in rows if r["spearman"] != ""]
    print(f"=== E008 {season}  threshold Spearman(xP,actual) > {LEAKAGE_SPEARMAN} ===")
    print(f"  GWs flagged: {n_flag}/38")
    if sps:
        print(f"  Spearman mean/median: {statistics.mean(sps):.3f} / {statistics.median(sps):.3f}")
        print(f"  min/max: {min(sps):.3f} / {max(sps):.3f}")
    flagged_gws = [r["gw"] for r in rows if r["leakage_flag"]]
    print(f"  flagged GWs: {flagged_gws or '-'}")
    print(f"  wrote {path}")
    print()
    return rows


def _load_v1_rows(season: str) -> list[dict]:
    out = []
    for gw in range(1, 39):
        path = record_path(gw, season=season)
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row["_gw"] = gw
                out.append(row)
    return out


def _bucket(p: float) -> str:
    for name, lo, hi in BUCKETS:
        if lo <= p < hi:
            return name
    return "<0.60"


def _cal_table(rows: list[dict], label: str) -> None:
    print(f"  P(start) calibration — {label}")
    print(f"  {'bucket':12} {'n':>6} {'start%':>8} {'0min%':>8} {'avg pts':>8}")
    by: dict[str, list] = {b[0]: [] for b in BUCKETS}
    for r in rows:
        ps = safe_float(r.get("p_start"))
        if ps is None:
            continue
        by[_bucket(ps)].append(r)
    for name, _, _ in BUCKETS:
        grp = by[name]
        if not grp:
            print(f"  {name:12} {0:6}")
            continue
        n = len(grp)
        starts = sum(1 for r in grp if int(float(r.get("did_start") or 0)))
        zmin = sum(1 for r in grp if float(r.get("actual_minutes") or 0) == 0)
        pts = [float(r.get("actual_points") or 0) for r in grp]
        print(f"  {name:12} {n:6} {100*starts/n:7.1f}% {100*zmin/n:7.1f}% {statistics.mean(pts):8.2f}")
    print()


def _conditional_mae(rows: list[dict], label: str) -> None:
    def mae(grp):
        err = []
        for r in grp:
            mu = safe_float(r.get("mu"))
            act = safe_float(r.get("actual_points"))
            if mu is None or act is None:
                continue
            err.append(abs(act - mu))
        return statistics.mean(err) if err else float("nan"), len(err)

    ge60 = [r for r in rows if float(r.get("actual_minutes") or 0) >= 60]
    lt60 = [r for r in rows if float(r.get("actual_minutes") or 0) < 60]
    m60, n60 = mae(ge60)
    mlt, nlt = mae(lt60)
    print(f"  Conditional MAE — {label}")
    print(f"    minutes>=60: n={n60:6}  MAE={m60:.3f}")
    print(f"    minutes<60:  n={nlt:6}  MAE={mlt:.3f}")
    print()


def run_e009(season: str, new_ids: set[int]) -> None:
    rows = _load_v1_rows(season)
    scored = [r for r in rows if r.get("actual_points") not in (None, "")]
    print(f"=== E009 {season} minutes / conditional MAE ===")
    _cal_table(scored, "all players")
    est = [r for r in scored if int(r["player_id"]) not in new_ids]
    neu = [r for r in scored if int(r["player_id"]) in new_ids]
    _cal_table(est, "established club (same team code as prior season)")
    _cal_table(neu, "new club / no prior-season team")
    _conditional_mae(scored, "all players")
    _conditional_mae(est, "established")
    _conditional_mae(neu, "new club")

    # XI 0-minute rate from decision_decomp + actuals
    decomp = Path("records") / "historical" / season / "decision_decomp.csv"
    gw_status = {}
    gw_path = Path("records") / "historical" / season / "decision_gw.csv"
    if gw_path.exists():
        with gw_path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                gw_status[int(r["gw"])] = r.get("evaluation_status")
    xi_rows = []
    if decomp.exists():
        with decomp.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("in_v1_xi") != "1":
                    continue
                gw = int(r["gw"])
                act = gw_actuals(season, gw)
                pid = int(r["player_id"])
                mins = float(act.get(pid, {}).get("actual_minutes", 0) or 0)
                xi_rows.append({
                    "gw": gw,
                    "status": gw_status.get(gw, ""),
                    "new_club": int(pid in new_ids),
                    "p_start": r.get("v1_p_start"),
                    "minutes": mins,
                    "points": r.get("actual_points"),
                })
    def xi_summary(subset, label):
        if not subset:
            print(f"  V1 XI 0-min — {label}: n=0")
            return
        n = len(subset)
        z = sum(1 for r in subset if r["minutes"] == 0)
        print(f"  V1 XI 0-min — {label}: n={n} slots, 0-min={z} ({100*z/n:.1f}%)")

    print("  V1 XI occupancy (11 slots x GWs):")
    xi_summary(xi_rows, "ALL GWs")
    xi_summary([r for r in xi_rows if r["status"] == "clean"], "CLEAN GWs")
    xi_summary([r for r in xi_rows if r["new_club"]], "new-club slots ALL")
    xi_summary([r for r in xi_rows if not r["new_club"]], "established slots ALL")
    print()

    out = Path("records") / "historical" / season / "minutes_cal.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["season", "split", "bucket", "n", "start_pct", "zero_min_pct", "avg_pts"],
        )
        w.writeheader()
        for split, grp in [("all", scored), ("established", est), ("new_club", neu)]:
            by: dict[str, list] = {b[0]: [] for b in BUCKETS}
            for r in grp:
                ps = safe_float(r.get("p_start"))
                if ps is None:
                    continue
                by[_bucket(ps)].append(r)
            for name, _, _ in BUCKETS:
                g = by[name]
                n = len(g)
                if n == 0:
                    w.writerow({"season": season, "split": split, "bucket": name, "n": 0,
                                "start_pct": "", "zero_min_pct": "", "avg_pts": ""})
                    continue
                starts = sum(1 for r in g if int(float(r.get("did_start") or 0)))
                zmin = sum(1 for r in g if float(r.get("actual_minutes") or 0) == 0)
                pts = statistics.mean(float(r.get("actual_points") or 0) for r in g)
                w.writerow({
                    "season": season, "split": split, "bucket": name, "n": n,
                    "start_pct": round(100 * starts / n, 2),
                    "zero_min_pct": round(100 * zmin / n, 2),
                    "avg_pts": round(pts, 3),
                })
    print(f"  wrote {out}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="E008/E009 observational diagnostics (no V1 code change).")
    parser.add_argument("--season", required=True, choices=SUPPORTED_SEASONS)
    args = parser.parse_args()
    ensure_vaastav((args.season,))
    print(f"[obs] {args.season}  LEAKAGE_SPEARMAN pre-registered at {LEAKAGE_SPEARMAN}")
    print("[obs] Results may not modify V1.0, frozen gw01_v1.0.csv, or Friday default squad.")
    print()
    run_e008(args.season)
    run_e009(args.season, new_club_ids(args.season))


if __name__ == "__main__":
    main()
