"""E015 evaluation: structural as-of-T minutes (v2am_s) vs V1.

Usage:
    python -m engine.harness_v2am_s
    python -m engine.harness_v2am_s --season 2025-26

Hard gate: XI 0-min must not worsen vs V1 on any season.
Production default is minutes_version=v2am_s (E015 promote / V2A-M freeze).
"""
from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path

from engine.harness import SUPPORTED_SEASONS, build_snapshot, ensure_vaastav, gw_actuals
from engine.metrics import record_path, safe_float
from engine.optimize import solve_squad
from engine.project import project_all

OUT_DIR = Path("records") / "historical"


def _mae(preds, acts):
    if not preds:
        return float("nan")
    return statistics.mean(abs(a - p) for p, a in zip(preds, acts))


def upper_tail_gap(pairs: list[tuple[float, int]], min_p: float = 0.75):
    ps = [p for p, y in pairs if p >= min_p]
    ys = [y for p, y in pairs if p >= min_p]
    if not ps:
        return float("nan"), float("nan"), float("nan"), 0
    mp, my = statistics.mean(ps), statistics.mean(ys)
    return mp, my, abs(mp - my), len(ps)


def p90_rate(pairs: list[tuple[float, int]]):
    g = [y for p, y in pairs if p >= 0.90]
    if not g:
        return float("nan"), 0
    return 100.0 * sum(g) / len(g), len(g)


def load_v1_xi(season: str) -> dict[int, list[int]]:
    path = OUT_DIR / season / "decision_decomp.csv"
    by = {}
    if not path.exists():
        return by
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("in_v1_xi") == "1":
                by.setdefault(int(r["gw"]), []).append(int(r["player_id"]))
    return by


def xi0(season, xi_by_gw):
    z = n = 0
    for gw, pids in xi_by_gw.items():
        act = gw_actuals(season, gw)
        for pid in pids:
            mins = float(act.get(pid, {}).get("actual_minutes", 0) or 0)
            n += 1
            z += int(mins == 0)
    return (100.0 * z / n if n else float("nan")), z, n


def eval_season(season: str, strategy: str = "balanced") -> dict:
    ensure_vaastav((season,))
    print(f"\n=== {season} E015 v2am_s ===")
    v1_xi = load_v1_xi(season)
    v1_zrate, v1_z, v1_n = xi0(season, v1_xi)

    v1_pairs = []
    v1_mae60_p, v1_mae60_a = [], []
    for gw in range(1, 39):
        path = record_path(gw, season=season)
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("actual_points") in (None, ""):
                    continue
                ps = safe_float(row.get("p_start"))
                if ps is not None and row.get("did_start") not in (None, ""):
                    v1_pairs.append((ps, int(float(row["did_start"]))))
                mins = float(row.get("actual_minutes") or 0)
                mu = safe_float(row.get("mu"))
                act = safe_float(row.get("actual_points"))
                if mins >= 60 and mu is not None and act is not None:
                    v1_mae60_p.append(mu)
                    v1_mae60_a.append(act)

    v1_cap = {}
    cmp_path = OUT_DIR / season / "b0_b3_comparison.csv"
    if cmp_path.exists():
        with cmp_path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("model") == "B3_v1" and r.get("xi_points"):
                    v1_cap[int(r["gw"])] = float(r["xi_points"])

    v2_xi = {}
    v2_pairs = []
    v2_xicap, v1_xicap = [], []
    v2_mae60_p, v2_mae60_a = [], []

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        print(f"  [{season}] GW{gw}")
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue
        projs = project_all(snap, horizon=1, strategy=strategy, minutes_version="v2am_s")
        try:
            sol = solve_squad(snap, projs, strategy=strategy, objective="next")
        except RuntimeError as e:
            print(f"    solver fail: {e}")
            continue
        v2_xi[gw] = [p.id for p in sol.xi]
        total = sum(float(act.get(p.id, {}).get("actual_points", 0) or 0) for p in sol.xi)
        total += float(act.get(sol.captain.id, {}).get("actual_points", 0) or 0)
        v2_xicap.append(total)
        if gw in v1_cap:
            v1_xicap.append(v1_cap[gw])

        for proj in projs:
            a = act.get(proj.player.id)
            if not a:
                continue
            mins = float(a.get("actual_minutes", 0) or 0)
            started = int(mins >= 45)
            v2_pairs.append((proj.next_p_start, started))
            if mins >= 60:
                v2_mae60_p.append(proj.next_mu)
                v2_mae60_a.append(float(a.get("actual_points", 0) or 0))

    v2_zrate, v2_z, v2_n = xi0(season, v2_xi)
    v1_ut = upper_tail_gap(v1_pairs)
    v2_ut = upper_tail_gap(v2_pairs)
    v1_p90, v1_p90n = p90_rate(v1_pairs)
    v2_p90, v2_p90n = p90_rate(v2_pairs)

    r = {
        "season": season,
        "v1_ut_gap": v1_ut[2], "v2_ut_gap": v2_ut[2],
        "v1_ut_n": v1_ut[3], "v2_ut_n": v2_ut[3],
        "v1_p90": v1_p90, "v1_p90_n": v1_p90n,
        "v2_p90": v2_p90, "v2_p90_n": v2_p90n,
        "v1_xi0": v1_zrate, "v2_xi0": v2_zrate,
        "v1_xi0_n": v1_n, "v2_xi0_n": v2_n,
        "v1_xicap_mean": statistics.mean(v1_xicap) if v1_xicap else float("nan"),
        "v2_xicap_mean": statistics.mean(v2_xicap) if v2_xicap else float("nan"),
        "v1_mae60": _mae(v1_mae60_p, v1_mae60_a),
        "v2_mae60": _mae(v2_mae60_p, v2_mae60_a),
        "xi0_ok": v2_zrate <= v1_zrate + 1e-9,
    }
    print(
        f"  ut_gap {v1_ut[2]:.3f}->{v2_ut[2]:.3f} | "
        f"XI0 {v1_zrate:.1f}->{v2_zrate:.1f}% {'OK' if r['xi0_ok'] else 'FAIL'} | "
        f"XI+Cap {r['v1_xicap_mean']:.1f}->{r['v2_xicap_mean']:.1f} | "
        f"MAE60 {r['v1_mae60']:.3f}->{r['v2_mae60']:.3f}"
    )
    print(f"  p90 start% n: V1 {v1_p90:.1f}% ({v1_p90n}) | V2 {v2_p90:.1f}% ({v2_p90n})")
    return r


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    parser.add_argument("--strategy", default="balanced")
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e015] Structural as-of-T minutes (v2am_s). Soft max 0.85; cold/hot recent-4.")
    print("[e015] Hard gate: XI 0-min non-inferiority every season. Production default = v2am_s.")
    results = [eval_season(s, args.strategy) for s in seasons]
    path = OUT_DIR / "v2am_s_summary.csv"
    fields = [
        "season", "v1_ut_gap", "v2_ut_gap", "v1_ut_n", "v2_ut_n",
        "v1_p90", "v1_p90_n", "v2_p90", "v2_p90_n",
        "v1_xi0", "v2_xi0", "v1_xi0_n", "v2_xi0_n",
        "v1_xicap_mean", "v2_xicap_mean", "v1_mae60", "v2_mae60", "xi0_ok",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow({k: (round(r[k], 4) if isinstance(r.get(k), float) else r.get(k)) for k in fields})
    print(f"\nWrote {path}")
    print("\n=== HARD GATE (XI0 non-inferiority) ===")
    for r in results:
        print(f"  {r['season']}: {r['v1_xi0']:.1f}% -> {r['v2_xi0']:.1f}%  {'PASS' if r['xi0_ok'] else 'FAIL'}")
    if all(r["xi0_ok"] for r in results):
        print("OVERALL: XI0 hard gate PASS")
    else:
        print("OVERALL: XI0 hard gate FAIL -> reject / iterate")


if __name__ == "__main__":
    main()
