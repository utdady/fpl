"""V2A-M evaluation: LOSO minutes recalibration vs frozen V1 control.

Usage:
    python -m engine.harness_v2am
    python -m engine.harness_v2am --season 2025-26

Does not change production defaults. project_all(..., minutes_version='v1') remains default.
"""
from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path

from engine.harness import SUPPORTED_SEASONS, build_snapshot, ensure_vaastav, gw_actuals
from engine.minutes_v2am import fit_loso_map, mapping_report, recalibrate_minutes, bucket_name
from engine.metrics import record_path, safe_float
from engine.optimize import solve_squad
from engine.project import project_all

OUT_DIR = Path("records") / "historical"


def _mae(preds: list[float], acts: list[float]) -> float:
    if not preds:
        return float("nan")
    return statistics.mean(abs(a - p) for p, a in zip(preds, acts))


def upper_tail_gap(rows: list[dict], min_p: float = 0.75) -> tuple[float, float, float, int]:
    """Return (mean_pred, mean_actual_start, abs_gap, n) for p_start >= min_p."""
    ps, ys = [], []
    for r in rows:
        p = safe_float(r.get("p_start"))
        if p is None or p < min_p:
            continue
        if r.get("did_start") in (None, ""):
            continue
        ps.append(p)
        ys.append(float(int(float(r["did_start"]))))
    if not ps:
        return float("nan"), float("nan"), float("nan"), 0
    mp, my = statistics.mean(ps), statistics.mean(ys)
    return mp, my, abs(mp - my), len(ps)


def p90_start_rate(rows: list[dict]) -> tuple[float, int]:
    g = []
    for r in rows:
        p = safe_float(r.get("p_start"))
        if p is None or p < 0.90:
            continue
        if r.get("did_start") in (None, ""):
            continue
        g.append(int(float(r["did_start"])))
    if not g:
        return float("nan"), 0
    return 100.0 * sum(g) / len(g), len(g)


def load_v1_xi_from_decomp(season: str) -> dict[int, list[int]]:
    """gw -> list of player_ids in V1 XI from decision_decomp."""
    path = OUT_DIR / season / "decision_decomp.csv"
    by_gw: dict[int, list[int]] = {}
    if not path.exists():
        return by_gw
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("in_v1_xi") != "1":
                continue
            gw = int(r["gw"])
            by_gw.setdefault(gw, []).append(int(r["player_id"]))
    return by_gw


def xi_zero_min_rate(season: str, xi_by_gw: dict[int, list[int]]) -> tuple[float, int, int]:
    z = n = 0
    for gw, pids in xi_by_gw.items():
        act = gw_actuals(season, gw)
        for pid in pids:
            mins = float(act.get(pid, {}).get("actual_minutes", 0) or 0)
            n += 1
            z += int(mins == 0)
    return (100.0 * z / n if n else float("nan")), z, n


def xi_cap_points(season: str, xi: list, captain_id: int) -> float:
    act = None
    # caller passes gw via closure - better take gw
    raise NotImplementedError


def eval_season(season: str, all_seasons: tuple[str, ...], strategy: str = "balanced") -> dict:
    ensure_vaastav((season,))
    pmap = fit_loso_map(season, all_seasons)
    print(f"\n=== {season} ===")
    print(mapping_report(pmap))

    v1_xi = load_v1_xi_from_decomp(season)
    v1_zrate, v1_z, v1_n = xi_zero_min_rate(season, v1_xi)

    # Player-level from existing V1 records + remapped p_start (calibration only)
    v1_rows = []
    v2_cal_rows = []
    for gw in range(1, 39):
        path = record_path(gw, season=season)
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("actual_points") in (None, ""):
                    continue
                v1_rows.append(row)
                ps = safe_float(row.get("p_start"))
                if ps is None:
                    continue
                new_ps, _, _ = recalibrate_minutes(ps, float(row.get("p_sub") or 0), pmap)
                v2_cal_rows.append({
                    "p_start": new_ps,
                    "did_start": row.get("did_start"),
                    "actual_points": row.get("actual_points"),
                    "actual_minutes": row.get("actual_minutes"),
                    "mu": row.get("mu"),  # V1 mu — replaced below for MAE_60+
                })

    v1_p90, v1_p90n = p90_start_rate(v1_rows)
    v2_p90, v2_p90n = p90_start_rate(v2_cal_rows)
    v1_ut = upper_tail_gap(v1_rows, 0.75)
    v2_ut = upper_tail_gap(v2_cal_rows, 0.75)

    # Decision-level: re-project V2A-M and solve XI each GW (horizon=1, matches E006)
    v2_xi_by_gw: dict[int, list[int]] = {}
    v2_xicap = []
    v1_xicap = []
    v2_mae60_preds: list[float] = []
    v2_mae60_acts: list[float] = []
    v1_mae60_preds: list[float] = []
    v1_mae60_acts: list[float] = []

    # V1 MAE_60+ from records
    for r in v1_rows:
        mins = float(r.get("actual_minutes") or 0)
        if mins < 60:
            continue
        mu = safe_float(r.get("mu"))
        act = safe_float(r.get("actual_points"))
        if mu is None or act is None:
            continue
        v1_mae60_preds.append(mu)
        v1_mae60_acts.append(act)

    # V1 XI+Cap from E006 horizon=1 compare (xi_points already includes captain double)
    v1_cap_by_gw: dict[int, float] = {}
    cmp_path = OUT_DIR / season / "b0_b3_comparison.csv"
    if cmp_path.exists():
        with cmp_path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("model") == "B3_v1" and r.get("xi_points") not in (None, ""):
                    v1_cap_by_gw[int(r["gw"])] = float(r["xi_points"])

    for gw in range(1, 39):
        if gw not in v1_xi and not record_path(gw, season=season).exists():
            continue
        print(f"  [{season}] GW{gw} V2A-M project+solve ...")
        snap = build_snapshot(season, as_of_gw=gw)
        actuals = gw_actuals(season, gw)
        if not actuals:
            continue
        projs = project_all(
            snap, horizon=1, strategy=strategy,
            minutes_version="v2am", p_start_map=pmap,
        )
        by_id = {p.player.id: p for p in projs}
        try:
            sol = solve_squad(snap, projs, strategy=strategy, objective="next")
        except RuntimeError as e:
            print(f"    solver fail GW{gw}: {e}")
            continue
        v2_xi_by_gw[gw] = [p.id for p in sol.xi]
        total = 0.0
        for p in sol.xi:
            total += float(actuals.get(p.id, {}).get("actual_points", 0) or 0)
        total += float(actuals.get(sol.captain.id, {}).get("actual_points", 0) or 0)
        v2_xicap.append(total)
        if gw in v1_cap_by_gw:
            v1_xicap.append(v1_cap_by_gw[gw])

        for pid, proj in by_id.items():
            a = actuals.get(pid)
            if not a:
                continue
            mins = float(a.get("actual_minutes", 0) or 0)
            if mins < 60:
                continue
            v2_mae60_preds.append(proj.next_mu)
            v2_mae60_acts.append(float(a.get("actual_points", 0) or 0))

    v2_zrate, v2_z, v2_n = xi_zero_min_rate(season, v2_xi_by_gw)

    result = {
        "season": season,
        "map": pmap,
        "v1_p90": v1_p90, "v1_p90_n": v1_p90n,
        "v2_p90": v2_p90, "v2_p90_n": v2_p90n,
        "v1_ut_pred": v1_ut[0], "v1_ut_act": v1_ut[1], "v1_ut_gap": v1_ut[2], "v1_ut_n": v1_ut[3],
        "v2_ut_pred": v2_ut[0], "v2_ut_act": v2_ut[1], "v2_ut_gap": v2_ut[2], "v2_ut_n": v2_ut[3],
        "v1_xi0": v1_zrate, "v1_xi0_z": v1_z, "v1_xi0_n": v1_n,
        "v2_xi0": v2_zrate, "v2_xi0_z": v2_z, "v2_xi0_n": v2_n,
        "v1_xicap_mean": statistics.mean(v1_xicap) if v1_xicap else float("nan"),
        "v2_xicap_mean": statistics.mean(v2_xicap) if v2_xicap else float("nan"),
        "v1_mae60": _mae(v1_mae60_preds, v1_mae60_acts),
        "v2_mae60": _mae(v2_mae60_preds, v2_mae60_acts),
        "n_gw_v2": len(v2_xicap),
    }

    print(f"  Upper-tail (p>=0.75): V1 gap={v1_ut[2]:.3f} (pred {v1_ut[0]:.3f} vs act {v1_ut[1]:.3f}, n={v1_ut[3]})")
    print(f"                        V2 gap={v2_ut[2]:.3f} (pred {v2_ut[0]:.3f} vs act {v2_ut[1]:.3f}, n={v2_ut[3]})")
    print(f"  p90 start% (n): V1 {v1_p90:.1f}% ({v1_p90n}) | V2 {v2_p90:.1f}% ({v2_p90n})  [V2 n~0 expected if remapped below 0.90]")
    print(f"  XI 0-min: V1 {v1_zrate:.1f}% ({v1_z}/{v1_n}) | V2 {v2_zrate:.1f}% ({v2_z}/{v2_n})")
    print(f"  XI+Cap mean: V1 {result['v1_xicap_mean']:.2f} | V2 {result['v2_xicap_mean']:.2f}  (n_gw={result['n_gw_v2']})")
    print(f"  MAE_60+: V1 {result['v1_mae60']:.3f} | V2 {result['v2_mae60']:.3f}")
    return result


def write_summary(results: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "season",
        "v1_ut_gap", "v2_ut_gap", "v1_ut_n", "v2_ut_n",
        "v1_p90", "v1_p90_n", "v2_p90", "v2_p90_n",
        "v1_xi0", "v2_xi0", "v1_xi0_n", "v2_xi0_n",
        "v1_xicap_mean", "v2_xicap_mean",
        "v1_mae60", "v2_mae60",
        "n_gw_v2",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in results:
            row = {k: (round(r[k], 4) if isinstance(r.get(k), float) else r.get(k)) for k in fields}
            w.writerow(row)
    print(f"\nWrote {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate V2A-M LOSO minutes recalibration vs V1.")
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    parser.add_argument("--strategy", default="balanced")
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[v2am] Control = V1. Treatment = LOSO bucket recalibration of p_start only.")
    print("[v2am] No new-club prior. Production minutes_version default remains v1.")
    results = [eval_season(s, SUPPORTED_SEASONS, strategy=args.strategy) for s in seasons]
    write_summary(results, OUT_DIR / "v2am_loso_summary.csv")

    # Gate verdict printout
    print("\n=== GATE SUMMARY ===")
    print(f"{'season':8} {'ut_gap V1->V2':16} {'XI0 V1->V2':18} {'XI+Cap V1->V2':18} {'MAE60 V1->V2':16}")
    for r in results:
        print(
            f"{r['season']:8} "
            f"{r['v1_ut_gap']:.3f}->{r['v2_ut_gap']:.3f}     "
            f"{r['v1_xi0']:.1f}->{r['v2_xi0']:.1f}%        "
            f"{r['v1_xicap_mean']:.1f}->{r['v2_xicap_mean']:.1f}      "
            f"{r['v1_mae60']:.3f}->{r['v2_mae60']:.3f}"
        )


if __name__ == "__main__":
    main()
