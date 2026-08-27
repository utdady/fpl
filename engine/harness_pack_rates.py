"""E024 evaluation: packaged rates_v2b vs production rates_v1.

Usage:
    python -m engine.harness_pack_rates
    python -m engine.harness_pack_rates --season 2025-26

Control:  minutes=v2am_s + rates=v1 + fixtures=v1, ILP on raw mu_v1
Treatment: minutes=v2am_s + rates=v2b + fixtures=v1, ILP on packaged U
           U=(1-q)*mu_v1+q*mu_v2b; q frozen from E022
MAE_60+: control on mu_v1; treatment on mu_v2b
Named risk: XI0. PASS != auto-promote.
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


def eval_season(season: str, strategy: str = "balanced") -> dict:
    ensure_vaastav((season,))
    print(f"\n=== {season} E024 packaged rates_v2b vs production rates_v1 ===")

    ctrl_xi: dict[int, list[int]] = {}
    treat_xi: dict[int, list[int]] = {}
    ctrl_xicap: list[float] = []
    treat_xicap: list[float] = []
    ctrl_mae_p, ctrl_mae_a = [], []
    treat_mae_p, treat_mae_a = [], []
    entered_blank = left_blank = 0
    entered_n = left_n = 0

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
        # apply_packaged_next_utility(treat, ctrl, ...): keeps treat next_mu for MAE
        packaged = apply_packaged_next_utility(
            v2b, v1, recent_minutes=recent, as_of_gw=gw, strategy=strategy,
        )

        try:
            sol_c = solve_squad(snap, v1, strategy=strategy, objective="next")
            sol_t = solve_squad(snap, packaged, strategy=strategy, objective="next")
        except RuntimeError as e:
            print(f"    solver fail: {e}")
            continue

        c_ids = {p.id for p in sol_c.xi}
        t_ids = {p.id for p in sol_t.xi}
        ctrl_xi[gw] = list(c_ids)
        treat_xi[gw] = list(t_ids)

        def xicap(sol):
            total = sum(float(act.get(p.id, {}).get("actual_points", 0) or 0) for p in sol.xi)
            total += float(act.get(sol.captain.id, {}).get("actual_points", 0) or 0)
            return total

        ctrl_xicap.append(xicap(sol_c))
        treat_xicap.append(xicap(sol_t))

        for pid in c_ids - t_ids:
            left_n += 1
            mins = float(act.get(pid, {}).get("actual_minutes", 0) or 0)
            left_blank += int(mins == 0)
        for pid in t_ids - c_ids:
            entered_n += 1
            mins = float(act.get(pid, {}).get("actual_minutes", 0) or 0)
            entered_blank += int(mins == 0)

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
    t_xi0, _, t_n = xi0(season, treat_xi)
    c_mae = _mae(ctrl_mae_p, ctrl_mae_a)
    t_mae = _mae(treat_mae_p, treat_mae_a)
    c_cap = statistics.mean(ctrl_xicap) if ctrl_xicap else float("nan")
    t_cap = statistics.mean(treat_xicap) if treat_xicap else float("nan")
    left_blank_pct = 100.0 * left_blank / left_n if left_n else float("nan")
    entered_blank_pct = 100.0 * entered_blank / entered_n if entered_n else float("nan")

    mae_ok = (not math.isnan(t_mae)) and (not math.isnan(c_mae)) and t_mae <= c_mae + 1e-9
    cap_ok = (not math.isnan(t_cap)) and (not math.isnan(c_cap)) and t_cap + 1e-9 >= c_cap
    xi0_ok = (not math.isnan(t_xi0)) and (not math.isnan(c_xi0)) and t_xi0 <= c_xi0 + 1e-9

    r = {
        "season": season,
        "ctrl_mae60": c_mae,
        "treat_mae60": t_mae,
        "ctrl_xicap_mean": c_cap,
        "treat_xicap_mean": t_cap,
        "ctrl_xi0": c_xi0,
        "treat_xi0": t_xi0,
        "ctrl_xi0_n": c_n,
        "treat_xi0_n": t_n,
        "n_swaps": entered_n,
        "left_blank_pct": left_blank_pct,
        "entered_blank_pct": entered_blank_pct,
        "mae60_ok": mae_ok,
        "xicap_ok": cap_ok,
        "xi0_ok": xi0_ok,
    }
    print(
        f"  MAE60 {c_mae:.3f}->{t_mae:.3f} {'OK' if mae_ok else 'FAIL'} | "
        f"XI+Cap {c_cap:.1f}->{t_cap:.1f} {'OK' if cap_ok else 'FAIL'} | "
        f"XI0 {c_xi0:.1f}->{t_xi0:.1f}% {'OK' if xi0_ok else 'FAIL'}"
    )
    print(
        f"  diag: swaps={entered_n} left_blank={left_blank_pct:.1f}% "
        f"entered_blank={entered_blank_pct:.1f}%"
    )
    return r


def write_summary(results: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "season",
        "ctrl_mae60", "treat_mae60",
        "ctrl_xicap_mean", "treat_xicap_mean",
        "ctrl_xi0", "treat_xi0", "ctrl_xi0_n", "treat_xi0_n",
        "n_swaps", "left_blank_pct", "entered_blank_pct",
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
    parser = argparse.ArgumentParser(description="E024: packaged rates_v2b vs production rates_v1.")
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    parser.add_argument("--strategy", default="balanced")
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e024] Control = minutes=v2am_s + rates=v1 + fixtures=v1 (production)")
    print("[e024] Treatment = rates=v2b + packaged U (q frozen from E022)")
    print("[e024] Named risk: XI0. Seed fixed. PASS != auto-promote.")
    results = [eval_season(s, args.strategy) for s in seasons]
    write_summary(results, OUT_DIR / "pack_rates_summary.csv")
    print("\n=== GATE SUMMARY ===")
    for r in results:
        ok = all(r[k] for k in ("mae60_ok", "xicap_ok", "xi0_ok"))
        print(
            f"{r['season']:8} "
            f"MAE {r['ctrl_mae60']:.3f}->{r['treat_mae60']:.3f} "
            f"Cap {r['ctrl_xicap_mean']:.1f}->{r['treat_xicap_mean']:.1f} "
            f"XI0 {r['ctrl_xi0']:.1f}->{r['treat_xi0']:.1f} "
            f"[{'PASS' if ok else 'FAIL'}]"
        )


if __name__ == "__main__":
    main()
