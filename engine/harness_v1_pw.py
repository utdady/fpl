"""E049-A evaluation: fixtures=v1_pw vs fixtures=v1 under v2am_fpla + rates=v1.

Usage:
    python -m engine.harness_v1_pw
    python -m engine.harness_v1_pw --season 2024-25

Both arms: minutes=v2am_fpla, rates=v1, seed=7.
Control fixtures=v1 (literal _str → modern overall clamps to 5).
Treatment fixtures=v1_pw (raw_to_u + piecewise ATK/CONCEDE through knots).
Same Team.strength_*; no fplcache hydrate. Production stays fixtures=v1.
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from pathlib import Path

from engine.fplcache_avail import ensure_fplcache_avail
from engine.harness import SUPPORTED_SEASONS, build_snapshot, ensure_vaastav, gw_actuals
from engine.metrics import record_path
from engine.optimize import BENCH_WEIGHT, solve_squad, solve_xi
from engine.project import project_all

OUT_DIR = Path("records") / "historical"
SEED = 7
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}


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


def _squad_u(squad, xi, by_id) -> float:
    xi_ids = {p.id for p in xi}
    total = 0.0
    for p in squad:
        u = by_id[p.id].next_utility
        w = (1.0 - BENCH_WEIGHT) if p.id in xi_ids else BENCH_WEIGHT
        total += w * u
    return total


def count_mu_delta(ctrl, treat, eps: float = 1e-9) -> int:
    by_t = {p.player.id: p for p in treat}
    n = 0
    for p in ctrl:
        q = by_t.get(p.player.id)
        if q is None:
            continue
        if abs(float(p.next_mu) - float(q.next_mu)) > eps:
            n += 1
    return n


def eval_season(season: str, strategy: str = "balanced") -> dict:
    ensure_vaastav((season,))
    ensure_fplcache_avail((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E049-A v1_pw (control=fixtures=v1) gate={gate} ===")

    ctrl_xi: dict[int, list[int]] = {}
    treat_xi: dict[int, list[int]] = {}
    ctrl_xicap: list[float] = []
    treat_xicap: list[float] = []
    ctrl_mae_p, ctrl_mae_a = [], []
    treat_mae_p, treat_mae_a = [], []
    g_treats: list[float] = []
    n_mu_delta = 0
    n_proj = 0

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
            minutes_version="v2am_fpla", rates_version="v1", fixtures_version="v1",
        )
        treat = project_all(
            snap, horizon=1, strategy=strategy, seed=SEED,
            minutes_version="v2am_fpla", rates_version="v1", fixtures_version="v1_pw",
        )
        n_mu_delta += count_mu_delta(ctrl, treat)
        n_proj += len(ctrl)
        by_t = {p.player.id: p for p in treat}

        try:
            sol_c = solve_squad(snap, ctrl, strategy=strategy, objective="next")
            sol_t = solve_squad(snap, treat, strategy=strategy, objective="next")
        except RuntimeError as e:
            print(f"    solver fail: {e}")
            continue

        ctrl_xi[gw] = [p.id for p in sol_c.xi]
        treat_xi[gw] = [p.id for p in sol_t.xi]

        def xicap(sol):
            total = sum(float(act.get(p.id, {}).get("actual_points", 0) or 0) for p in sol.xi)
            total += float(act.get(sol.captain.id, {}).get("actual_points", 0) or 0)
            return total

        ctrl_xicap.append(xicap(sol_c))
        treat_xicap.append(xicap(sol_t))

        try:
            xi_ctrl_on_treat, _ = solve_xi(snap, sol_c.players, by_t)
            g_treats.append(
                _squad_u(sol_t.players, sol_t.xi, by_t)
                - _squad_u(sol_c.players, xi_ctrl_on_treat, by_t)
            )
        except RuntimeError:
            pass

        for proj in ctrl:
            a = act.get(proj.player.id)
            if not a:
                continue
            if float(a.get("actual_minutes", 0) or 0) >= 60:
                ctrl_mae_p.append(proj.next_mu)
                ctrl_mae_a.append(float(a.get("actual_points", 0) or 0))
        for proj in treat:
            a = act.get(proj.player.id)
            if not a:
                continue
            if float(a.get("actual_minutes", 0) or 0) >= 60:
                treat_mae_p.append(proj.next_mu)
                treat_mae_a.append(float(a.get("actual_points", 0) or 0))

    c_xi0, _, c_n = xi0(season, ctrl_xi)
    t_xi0, _, t_n = xi0(season, treat_xi)
    c_mae = _mae(ctrl_mae_p, ctrl_mae_a)
    t_mae = _mae(treat_mae_p, treat_mae_a)
    c_cap = statistics.mean(ctrl_xicap) if ctrl_xicap else float("nan")
    t_cap = statistics.mean(treat_xicap) if treat_xicap else float("nan")
    c_season = sum(ctrl_xicap) if ctrl_xicap else float("nan")
    t_season = sum(treat_xicap) if treat_xicap else float("nan")
    g_mean = statistics.mean(g_treats) if g_treats else float("nan")

    xi0_ok = (not math.isnan(t_xi0)) and (not math.isnan(c_xi0)) and t_xi0 <= c_xi0 + 1e-9
    mae_ok = (not math.isnan(t_mae)) and (not math.isnan(c_mae)) and t_mae <= c_mae + 1e-9
    cap_ok = (not math.isnan(t_cap)) and (not math.isnan(c_cap)) and t_cap + 1e-9 >= c_cap

    r = {
        "season": season,
        "e024_gate": gate,
        "ctrl_mae60": c_mae,
        "treat_mae60": t_mae,
        "ctrl_xicap_mean": c_cap,
        "treat_xicap_mean": t_cap,
        "ctrl_season_cap": c_season,
        "treat_season_cap": t_season,
        "ctrl_xi0": c_xi0,
        "treat_xi0": t_xi0,
        "ctrl_xi0_n": c_n,
        "treat_xi0_n": t_n,
        "g_treat_mean": g_mean,
        "n_mu_delta": n_mu_delta,
        "n_proj": n_proj,
        "n_gw": len(ctrl_xicap),
        "xi0_ok": xi0_ok,
        "mae60_ok": mae_ok,
        "xicap_ok": cap_ok,
    }
    print(
        f"  XI0 {c_xi0:.1f}->{t_xi0:.1f}% {'OK' if xi0_ok else 'FAIL'} | "
        f"MAE60 {c_mae:.3f}->{t_mae:.3f} {'OK' if mae_ok else 'FAIL'} | "
        f"XI+Cap {c_cap:.1f}->{t_cap:.1f} {'OK' if cap_ok else 'FAIL'}"
    )
    print(
        f"  season Cap sum {c_season:.0f}->{t_season:.0f} | "
        f"g_treat mean={g_mean:.3f} | n_mu_delta={n_mu_delta}/{n_proj}"
    )
    return r


def write_summary(results: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "season", "e024_gate",
        "ctrl_mae60", "treat_mae60",
        "ctrl_xicap_mean", "treat_xicap_mean",
        "ctrl_season_cap", "treat_season_cap",
        "ctrl_xi0", "treat_xi0", "ctrl_xi0_n", "treat_xi0_n",
        "g_treat_mean", "n_mu_delta", "n_proj", "n_gw",
        "xi0_ok", "mae60_ok", "xicap_ok",
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


def gate_verdict(results: list[dict]) -> str:
    if len(results) < 4:
        return "INCOMPLETE"
    n_mu = sum(int(r["n_mu_delta"]) for r in results)
    if n_mu == 0:
        return "SURVIVES_IDENTITY_NULL"
    xi0_all = all(r["xi0_ok"] for r in results)
    mae_all = all(r["mae60_ok"] for r in results)
    fail_cap = all(r["xicap_ok"] for r in results if r["season"] in FAIL_SEASONS)
    agg_c = statistics.mean(r["ctrl_xicap_mean"] for r in results)
    agg_t = statistics.mean(r["treat_xicap_mean"] for r in results)
    agg_ok = agg_t + 1e-9 >= agg_c
    if xi0_all and mae_all and fail_cap and agg_ok:
        return "SURVIVES"
    return "KILL"


def main() -> None:
    parser = argparse.ArgumentParser(description="E049-A: fixtures=v1_pw vs v1.")
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    parser.add_argument("--strategy", default="balanced")
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e049] Control = minutes=v2am_fpla + rates=v1 + fixtures=v1 (_str)")
    print("[e049] Treatment = fixtures=v1_pw (raw_to_u + pw_lerp; STR_LO=1000 STR_HI=1350)")
    print("[e049] Same teams; continuous piecewise through ATK/CONCEDE knots. Production stays fixtures=v1.")
    results = [eval_season(s, args.strategy) for s in seasons]
    if args.season:
        write_summary(results, OUT_DIR / f"v1_pw_summary_{args.season}.csv")
    else:
        write_summary(results, OUT_DIR / "v1_pw_summary.csv")
    verdict = gate_verdict(results) if not args.season else "single-season"
    print("\n=== GATE SUMMARY ===")
    for r in results:
        print(
            f"{r['season']:8} [{r['e024_gate']:4}] "
            f"XI0 {r['ctrl_xi0']:.1f}->{r['treat_xi0']:.1f} "
            f"MAE {r['ctrl_mae60']:.3f}->{r['treat_mae60']:.3f} "
            f"Cap {r['ctrl_xicap_mean']:.1f}->{r['treat_xicap_mean']:.1f} "
            f"mu_delta={r['n_mu_delta']}"
        )
    print(f"\nVERDICT: {verdict}")


if __name__ == "__main__":
    main()
