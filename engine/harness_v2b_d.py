"""E017 evaluation: v2am_s + rates_v2b_d (α=0.50) vs v2am_s + rates_v1.

Usage:
    python -m engine.harness_v2b_d
    python -m engine.harness_v2b_d --season 2025-26

Both arms: minutes_version=v2am_s, seed=7.
Control rates_version=v1; treatment rates_version=v2b_d.
Production rates_version default remains v1 until an explicit promote.
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from pathlib import Path

from engine.harness import SUPPORTED_SEASONS, build_snapshot, ensure_vaastav, gw_actuals
from engine.metrics import record_path
from engine.optimize import solve_squad
from engine.project import project_all

OUT_DIR = Path("records") / "historical"
SEED = 7
TREAT_RATES = "v2b_d"


def _mae(preds, acts):
    if not preds:
        return float("nan")
    return statistics.mean(abs(a - p) for p, a in zip(preds, acts))


def _rankdata(vals: list[float]) -> list[float]:
    n = len(vals)
    order = sorted(range(n), key=lambda i: vals[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = 0.5 * ((i + 1) + (j + 1))
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return float("nan")
    rx, ry = _rankdata(xs), _rankdata(ys)
    mx = statistics.mean(rx)
    my = statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    deny = math.sqrt(sum((b - my) ** 2 for b in ry))
    if denx < 1e-12 or deny < 1e-12:
        return float("nan")
    return num / (denx * deny)


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
    print(f"\n=== {season} E017 rates_v2b_d α=0.50 (control = v2am_s + rates_v1) ===")

    ctrl_xi: dict[int, list[int]] = {}
    treat_xi: dict[int, list[int]] = {}
    ctrl_xicap: list[float] = []
    treat_xicap: list[float] = []
    ctrl_mae_p, ctrl_mae_a = [], []
    treat_mae_p, treat_mae_a = [], []
    ctrl_sp_p, ctrl_sp_a = [], []
    treat_sp_p, treat_sp_a = [], []
    entered_mu_delta: list[float] = []
    left_blank = entered_blank = 0
    left_n = entered_n = 0

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        print(f"  [{season}] GW{gw}")
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue

        ctrl = project_all(
            snap, horizon=1, strategy=strategy, seed=SEED,
            minutes_version="v2am_s", rates_version="v1",
        )
        treat = project_all(
            snap, horizon=1, strategy=strategy, seed=SEED,
            minutes_version="v2am_s", rates_version=TREAT_RATES,
        )
        by_c = {p.player.id: p for p in ctrl}
        by_t = {p.player.id: p for p in treat}

        try:
            sol_c = solve_squad(snap, ctrl, strategy=strategy, objective="next")
            sol_t = solve_squad(snap, treat, strategy=strategy, objective="next")
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
            entered_mu_delta.append(by_t[pid].next_mu - by_c[pid].next_mu)

        for proj in ctrl:
            a = act.get(proj.player.id)
            if not a:
                continue
            mins = float(a.get("actual_minutes", 0) or 0)
            pts = float(a.get("actual_points", 0) or 0)
            if mins >= 60:
                ctrl_mae_p.append(proj.next_mu)
                ctrl_mae_a.append(pts)
                ctrl_sp_p.append(proj.next_mu)
                ctrl_sp_a.append(pts)
        for proj in treat:
            a = act.get(proj.player.id)
            if not a:
                continue
            mins = float(a.get("actual_minutes", 0) or 0)
            pts = float(a.get("actual_points", 0) or 0)
            if mins >= 60:
                treat_mae_p.append(proj.next_mu)
                treat_mae_a.append(pts)
                treat_sp_p.append(proj.next_mu)
                treat_sp_a.append(pts)

    c_xi0, _, c_n = xi0(season, ctrl_xi)
    t_xi0, _, t_n = xi0(season, treat_xi)
    c_mae = _mae(ctrl_mae_p, ctrl_mae_a)
    t_mae = _mae(treat_mae_p, treat_mae_a)
    c_sp = spearman(ctrl_sp_p, ctrl_sp_a)
    t_sp = spearman(treat_sp_p, treat_sp_a)
    c_cap = statistics.mean(ctrl_xicap) if ctrl_xicap else float("nan")
    t_cap = statistics.mean(treat_xicap) if treat_xicap else float("nan")
    mean_dmu = statistics.mean(entered_mu_delta) if entered_mu_delta else float("nan")
    left_blank_pct = 100.0 * left_blank / left_n if left_n else float("nan")
    entered_blank_pct = 100.0 * entered_blank / entered_n if entered_n else float("nan")

    mae_ok = (not math.isnan(t_mae)) and (not math.isnan(c_mae)) and t_mae <= c_mae + 1e-9
    sp_ok = (math.isnan(c_sp) and math.isnan(t_sp)) or (
        not math.isnan(t_sp) and not math.isnan(c_sp) and t_sp + 1e-9 >= c_sp
    )
    cap_ok = (not math.isnan(t_cap)) and (not math.isnan(c_cap)) and t_cap + 1e-9 >= c_cap
    xi0_ok = (not math.isnan(t_xi0)) and (not math.isnan(c_xi0)) and t_xi0 <= c_xi0 + 1e-9

    r = {
        "season": season,
        "ctrl_mae60": c_mae,
        "treat_mae60": t_mae,
        "ctrl_spearman60": c_sp,
        "treat_spearman60": t_sp,
        "ctrl_xicap_mean": c_cap,
        "treat_xicap_mean": t_cap,
        "ctrl_xi0": c_xi0,
        "treat_xi0": t_xi0,
        "ctrl_xi0_n": c_n,
        "treat_xi0_n": t_n,
        "n_swaps": entered_n,
        "left_blank_pct": left_blank_pct,
        "entered_blank_pct": entered_blank_pct,
        "mean_entered_mu_delta": mean_dmu,
        "mae60_ok": mae_ok,
        "spearman60_ok": sp_ok,
        "xicap_ok": cap_ok,
        "xi0_ok": xi0_ok,
    }
    print(
        f"  MAE60 {c_mae:.3f}->{t_mae:.3f} {'OK' if mae_ok else 'FAIL'} | "
        f"Sp60 {c_sp:.3f}->{t_sp:.3f} {'OK' if sp_ok else 'FAIL'} | "
        f"XI+Cap {c_cap:.1f}->{t_cap:.1f} {'OK' if cap_ok else 'FAIL'} | "
        f"XI0 {c_xi0:.1f}->{t_xi0:.1f}% {'OK' if xi0_ok else 'FAIL'}"
    )
    print(
        f"  diag: swaps={entered_n} left_blank={left_blank_pct:.1f}% "
        f"entered_blank={entered_blank_pct:.1f}% mean_entered_μΔ={mean_dmu:.3f}"
    )
    return r


def write_summary(results: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "season",
        "ctrl_mae60", "treat_mae60",
        "ctrl_spearman60", "treat_spearman60",
        "ctrl_xicap_mean", "treat_xicap_mean",
        "ctrl_xi0", "treat_xi0", "ctrl_xi0_n", "treat_xi0_n",
        "n_swaps", "left_blank_pct", "entered_blank_pct", "mean_entered_mu_delta",
        "mae60_ok", "spearman60_ok", "xicap_ok", "xi0_ok",
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
    parser = argparse.ArgumentParser(description="E017: rates_v2b_d vs rates_v1 under frozen v2am_s.")
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    parser.add_argument("--strategy", default="balanced")
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e017] Control = minutes=v2am_s + rates=v1")
    print("[e017] Treatment = minutes=v2am_s + rates=v2b_d (α=0.50 club/cost mix)")
    print("[e017] Seed fixed. No α search. Production rates default = v1.")
    results = [eval_season(s, args.strategy) for s in seasons]
    write_summary(results, OUT_DIR / "v2b_d_rates_summary.csv")
    print("\n=== GATE SUMMARY ===")
    for r in results:
        ok = all(r[k] for k in ("mae60_ok", "spearman60_ok", "xicap_ok", "xi0_ok"))
        print(
            f"{r['season']:8} "
            f"MAE {r['ctrl_mae60']:.3f}->{r['treat_mae60']:.3f} "
            f"Sp {r['ctrl_spearman60']:.3f}->{r['treat_spearman60']:.3f} "
            f"Cap {r['ctrl_xicap_mean']:.1f}->{r['treat_xicap_mean']:.1f} "
            f"XI0 {r['ctrl_xi0']:.1f}->{r['treat_xi0']:.1f} "
            f"[{'PASS' if ok else 'FAIL'}]"
        )


if __name__ == "__main__":
    main()
