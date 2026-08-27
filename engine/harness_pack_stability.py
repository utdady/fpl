"""E027 evaluation: H-PACK1 stability-aware selection vs production control.

Usage:
    python scripts/calibrate_hpack1_epsilon.py   # once, control-only
    python -m engine.harness_pack_stability
    python -m engine.harness_pack_stability --season 2025-26

Control:  v2am_s + rates=v1 + fixtures=v1 (production)
Treat:    packaged rates_v2b (E024 treatment, unconstrained)
PACK1:    packaged rates_v2b + U0 >= U0* - ε (ε frozen from control calibration)

Gates vs control: Cap primary; XI0 non-regress; MAE secondary (not required).
Diagnostics: bind rate vs unconstrained treat; U0 slack.
PASS != auto-promote.
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from pathlib import Path

from engine.harness import SUPPORTED_SEASONS, build_snapshot, ensure_vaastav, gw_actuals, recent_minutes_by_element
from engine.metrics import record_path
from engine.minutes_struct import RECENT_WINDOW
from engine.optimize import solve_squad
from engine.packaging import apply_packaged_next_utility
from engine.project import project_all
from engine.stability_selection import load_epsilon, solve_squad_stability

OUT_DIR = Path("records") / "historical"
SEED = 7


def _mae(preds, acts):
    if not preds:
        return float("nan")
    return statistics.mean(abs(a - p) for p, a in zip(preds, acts))


def xi0(season, xi_by_gw):
    z = n = 0
    for gw, pids in xi_by_gw.items():
        act = gw_actuals(season, gw)
        for pid in pids:
            mins = float(act.get(pid, {}).get("actual_minutes", 0) or 0)
            n += 1
            z += int(mins == 0)
    return (100.0 * z / n if n else float("nan")), z, n


def eval_season(season: str, epsilon: float, strategy: str = "balanced") -> dict:
    ensure_vaastav((season,))
    print(f"\n=== {season} E027 H-PACK1 stability vs production ===")

    ctrl_xi: dict[int, list[int]] = {}
    treat_xi: dict[int, list[int]] = {}
    pack_xi: dict[int, list[int]] = {}
    ctrl_xicap: list[float] = []
    treat_xicap: list[float] = []
    pack_xicap: list[float] = []
    ctrl_mae_p, ctrl_mae_a = [], []
    treat_mae_p, treat_mae_a = [], []
    bind_n = n_gw = 0
    u0_slack: list[float] = []

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        print(f"  [{season}] GW{gw}")
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue

        recent = recent_minutes_by_element(season, gw, window=RECENT_WINDOW)
        v1 = project_all(
            snap, horizon=1, strategy=strategy, seed=SEED,
            minutes_version="v2am_s", rates_version="v1", fixtures_version="v1",
        )
        v2b = project_all(
            snap, horizon=1, strategy=strategy, seed=SEED,
            minutes_version="v2am_s", rates_version="v2b", fixtures_version="v1",
        )
        packaged = apply_packaged_next_utility(
            v2b, v1, recent_minutes=recent, as_of_gw=gw, strategy=strategy,
        )

        try:
            sol_c = solve_squad(snap, v1, strategy=strategy, objective="next")
            sol_t = solve_squad(snap, packaged, strategy=strategy, objective="next")
            sol_p, u0_val, _u1_val = solve_squad_stability(
                snap, v1, packaged, strategy=strategy, epsilon=epsilon, objective="next",
            )
        except RuntimeError as e:
            print(f"    solver fail: {e}")
            continue

        n_gw += 1
        c_ids = {p.id for p in sol_c.xi}
        t_ids = {p.id for p in sol_t.xi}
        p_ids = {p.id for p in sol_p.xi}
        ctrl_xi[gw] = list(c_ids)
        treat_xi[gw] = list(t_ids)
        pack_xi[gw] = list(p_ids)

        if p_ids != t_ids:
            bind_n += 1
        u0_slack.append(u0_val)

        def xicap(sol):
            total = sum(float(act.get(p.id, {}).get("actual_points", 0) or 0) for p in sol.xi)
            total += float(act.get(sol.captain.id, {}).get("actual_points", 0) or 0)
            return total

        ctrl_xicap.append(xicap(sol_c))
        treat_xicap.append(xicap(sol_t))
        pack_xicap.append(xicap(sol_p))

        by_v1 = {p.player.id: p for p in v1}
        by_v2b = {p.player.id: p for p in v2b}
        for pid, a in act.items():
            mins = float(a.get("actual_minutes", 0) or 0)
            pts = float(a.get("actual_points", 0) or 0)
            if mins < 60:
                continue
            if pid in by_v1:
                ctrl_mae_p.append(by_v1[pid].next_mu)
                ctrl_mae_a.append(pts)
            if pid in by_v2b:
                treat_mae_p.append(by_v2b[pid].next_mu)
                treat_mae_a.append(pts)

    c_xi0, _, c_n = xi0(season, ctrl_xi)
    t_xi0, _, _ = xi0(season, treat_xi)
    p_xi0, _, p_n = xi0(season, pack_xi)
    c_mae = _mae(ctrl_mae_p, ctrl_mae_a)
    t_mae = _mae(treat_mae_p, treat_mae_a)
    c_cap = statistics.mean(ctrl_xicap) if ctrl_xicap else float("nan")
    t_cap = statistics.mean(treat_xicap) if treat_xicap else float("nan")
    p_cap = statistics.mean(pack_xicap) if pack_xicap else float("nan")
    bind_pct = 100.0 * bind_n / n_gw if n_gw else float("nan")

    cap_ok = (not math.isnan(p_cap)) and (not math.isnan(c_cap)) and p_cap + 1e-9 >= c_cap
    xi0_ok = (not math.isnan(p_xi0)) and (not math.isnan(c_xi0)) and p_xi0 <= c_xi0 + 1e-9
    mae_ok = (not math.isnan(t_mae)) and (not math.isnan(c_mae)) and t_mae <= c_mae + 1e-9

    r = {
        "season": season,
        "epsilon": epsilon,
        "ctrl_mae60": c_mae,
        "treat_mae60": t_mae,
        "ctrl_xicap_mean": c_cap,
        "treat_xicap_mean": t_cap,
        "pack_xicap_mean": p_cap,
        "ctrl_xi0": c_xi0,
        "treat_xi0": t_xi0,
        "pack_xi0": p_xi0,
        "pack_xi0_n": p_n,
        "bind_pct": bind_pct,
        "n_gw": n_gw,
        "mae60_ok": mae_ok,
        "xicap_ok": cap_ok,
        "xi0_ok": xi0_ok,
    }
    print(
        f"  MAE60 ctrl={c_mae:.3f} treat={t_mae:.3f} | "
        f"Cap ctrl={c_cap:.1f} treat={t_cap:.1f} pack={p_cap:.1f} "
        f"{'OK' if cap_ok else 'FAIL'} | "
        f"XI0 ctrl={c_xi0:.1f}% treat={t_xi0:.1f}% pack={p_xi0:.1f}% "
        f"{'OK' if xi0_ok else 'FAIL'} | bind={bind_pct:.1f}%"
    )
    return r


def write_summary(results: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "season", "epsilon",
        "ctrl_mae60", "treat_mae60",
        "ctrl_xicap_mean", "treat_xicap_mean", "pack_xicap_mean",
        "ctrl_xi0", "treat_xi0", "pack_xi0", "pack_xi0_n",
        "bind_pct", "n_gw",
        "mae60_ok", "xicap_ok", "xi0_ok",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            row = {}
            for k in fields:
                v = r.get(k)
                if isinstance(v, float):
                    row[k] = round(v, 6) if not math.isnan(v) else ""
                else:
                    row[k] = v
            w.writerow(row)
    print(f"\nWrote {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="E027: H-PACK1 stability vs production.")
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    parser.add_argument("--strategy", default="balanced")
    args = parser.parse_args()
    epsilon = load_epsilon()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print(f"[e027] ε={epsilon:.6f} (frozen from control calibration)")
    print("[e027] Control = production v2am_s + rates=v1")
    print("[e027] PACK1 = packaged rates_v2b + stability constraint vs control U0")
    print("[e027] Gates vs control: Cap primary; XI0; MAE secondary. PASS != promote.")
    results = [eval_season(s, epsilon, args.strategy) for s in seasons]
    write_summary(results, OUT_DIR / "pack_stability_summary.csv")
    print("\n=== GATE SUMMARY (PACK1 vs control) ===")
    for r in results:
        ok = all(r[k] for k in ("xicap_ok", "xi0_ok"))
        print(
            f"{r['season']:8} "
            f"Cap {r['ctrl_xicap_mean']:.1f}->{r['pack_xicap_mean']:.1f} "
            f"(treat {r['treat_xicap_mean']:.1f}) "
            f"XI0 {r['ctrl_xi0']:.1f}->{r['pack_xi0']:.1f}% "
            f"bind {r['bind_pct']:.1f}% "
            f"[{'PASS' if ok else 'FAIL'}]"
        )


if __name__ == "__main__":
    main()
