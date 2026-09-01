"""E033 diagnostic: squad-pool / mu-inflation (wrong 15 vs wrong ranking).

After E032: mu tracks dU but realized XI inverts on FAIL. Locates whether toxicity is:
  A) wrong 15 — bad entrants into the squad pool
  B) wrong ranking — treat utility mis-ranks even on control 15

Frozen: control v2am_s+rates=v1 vs packaged rates_v2b; objective=next; seed=7.
Strategies: balanced, safe — existing objectives only.

GW metrics:
  squad_overlap, n_entered, n_left
  mean_mu_lift / mean_u_lift / mean_actual on entrants and leavers
  delta_xi_picked           treat XI - ctrl XI (realized)
  delta_xi_cf_ctrl_pool     treat-ranked XI on ctrl 15 - ctrl XI
  delta_xi_cf_treat_pool    ctrl-ranked XI on treat 15 - ctrl XI

Branch:
  cf_treat_pool_ctrl > picked  -> wrong 15 (pool)
  cf_ctrl_pool_treat > picked  -> wrong ranking (mu/utility on same pool)

No new utility. No lambda. Diagnostic only.

Usage:
    python scripts/e033_squad_pool_diagnostic.py
    python scripts/e033_squad_pool_diagnostic.py --season 2023-24
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.harness import (
    SUPPORTED_SEASONS,
    build_snapshot,
    ensure_vaastav,
    gw_actuals,
    recent_minutes_by_element,
)
from engine.metrics import record_path
from engine.minutes_struct import RECENT_WINDOW
from engine.models import PlayerProjection
from engine.optimize import solve_squad, solve_xi
from engine.packaging import apply_packaged_next_utility
from engine.project import project_all

OUT_GW = Path("records") / "historical" / "e033_squad_pool_gw.csv"
OUT_MOVERS = Path("records") / "historical" / "e033_squad_pool_movers.csv"
OUT_TXT = Path("records") / "historical" / "e033_squad_pool_summary.txt"
SEED = 7
OBJECTIVE = "next"
STRATEGIES = ("balanced", "safe")
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}


def _pts(act: dict, pid: int) -> float:
    return float(act.get(pid, {}).get("actual_points", 0) or 0)


def player_lookup(projections: list[PlayerProjection]) -> dict[int, PlayerProjection]:
    return {p.player.id: p for p in projections}


def xi_points_ids(xi_ids: set[int], act: dict) -> float:
    return sum(_pts(act, pid) for pid in xi_ids)


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return float("nan")
    return num / (den_x * den_y)


def _mean(vals: list[float]) -> float:
    return statistics.mean(vals) if vals else float("nan")


def analyze_season(season: str) -> tuple[list[dict], list[dict]]:
    ensure_vaastav((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E033 squad pool gate={gate} ===")
    gw_rows: list[dict] = []
    mover_rows: list[dict] = []

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue

        recent = recent_minutes_by_element(season, gw, window=RECENT_WINDOW)
        v1 = project_all(
            snap, horizon=1, strategy="balanced", seed=SEED,
            minutes_version="v2am_s", rates_version="v1", fixtures_version="v1",
        )
        v2b = project_all(
            snap, horizon=1, strategy="balanced", seed=SEED,
            minutes_version="v2am_s", rates_version="v2b", fixtures_version="v1",
        )
        by_v1_bal = player_lookup(v1)

        for strategy in STRATEGIES:
            packaged = apply_packaged_next_utility(
                v2b, v1, recent_minutes=recent, as_of_gw=gw, strategy=strategy,
            )
            v1_s = project_all(
                snap, horizon=1, strategy=strategy, seed=SEED,
                minutes_version="v2am_s", rates_version="v1", fixtures_version="v1",
            )
            by_c = player_lookup(v1_s)
            by_t = player_lookup(packaged)
            by_v2b = player_lookup(v2b)

            try:
                sol_c = solve_squad(snap, v1_s, strategy=strategy, objective=OBJECTIVE)
                sol_t = solve_squad(snap, packaged, strategy=strategy, objective=OBJECTIVE)
            except RuntimeError:
                continue

            c_squad = {p.id for p in sol_c.players}
            t_squad = {p.id for p in sol_t.players}
            c_xi = {p.id for p in sol_c.xi}
            t_xi = {p.id for p in sol_t.xi}
            entered = t_squad - c_squad
            left = c_squad - t_squad
            overlap = len(c_squad & t_squad)

            cf_ctrl_xi, _ = solve_xi(snap, sol_c.players, by_t)
            cf_treat_xi, _ = solve_xi(snap, sol_t.players, by_c)
            cf_ctrl_ids = {p.id for p in cf_ctrl_xi}
            cf_treat_ids = {p.id for p in cf_treat_xi}

            ctrl_xi_pts = xi_points_ids(c_xi, act)
            delta_xi_picked = xi_points_ids(t_xi, act) - ctrl_xi_pts
            delta_xi_cf_ctrl_pool = xi_points_ids(cf_ctrl_ids, act) - ctrl_xi_pts
            delta_xi_cf_treat_pool = xi_points_ids(cf_treat_ids, act) - ctrl_xi_pts

            ent_mu_lift: list[float] = []
            ent_u_lift: list[float] = []
            ent_v2b_lift: list[float] = []
            ent_actual: list[float] = []
            ent_mu_err: list[float] = []
            for pid in entered:
                mu_lift = by_t[pid].next_mu - by_c[pid].next_mu
                u_lift = by_t[pid].next_utility - by_c[pid].next_utility
                v2b_lift = by_v2b[pid].next_mu - by_v1_bal[pid].next_mu
                pts = _pts(act, pid)
                ent_mu_lift.append(mu_lift)
                ent_u_lift.append(u_lift)
                ent_v2b_lift.append(v2b_lift)
                ent_actual.append(pts)
                ent_mu_err.append(pts - by_t[pid].next_mu)
                mover_rows.append({
                    "season": season,
                    "e024_gate": gate,
                    "gw": gw,
                    "strategy": strategy,
                    "movement": "entered",
                    "player_id": pid,
                    "mu_lift": round(mu_lift, 4),
                    "u_lift": round(u_lift, 4),
                    "v2b_mu_lift": round(v2b_lift, 4),
                    "actual_pts": round(pts, 4),
                    "mu_error": round(pts - by_t[pid].next_mu, 4),
                    "treat_mu": round(by_t[pid].next_mu, 4),
                    "ctrl_mu": round(by_c[pid].next_mu, 4),
                })

            lev_mu_lift: list[float] = []
            lev_u_lift: list[float] = []
            lev_actual: list[float] = []
            for pid in left:
                mu_lift = by_t[pid].next_mu - by_c[pid].next_mu
                u_lift = by_t[pid].next_utility - by_c[pid].next_utility
                pts = _pts(act, pid)
                lev_mu_lift.append(mu_lift)
                lev_u_lift.append(u_lift)
                lev_actual.append(pts)
                mover_rows.append({
                    "season": season,
                    "e024_gate": gate,
                    "gw": gw,
                    "strategy": strategy,
                    "movement": "left",
                    "player_id": pid,
                    "mu_lift": round(mu_lift, 4),
                    "u_lift": round(u_lift, 4),
                    "v2b_mu_lift": round(by_v2b[pid].next_mu - by_v1_bal[pid].next_mu, 4),
                    "actual_pts": round(pts, 4),
                    "mu_error": round(pts - by_t[pid].next_mu, 4),
                    "treat_mu": round(by_t[pid].next_mu, 4),
                    "ctrl_mu": round(by_c[pid].next_mu, 4),
                })

            gw_rows.append({
                "season": season,
                "e024_gate": gate,
                "gw": gw,
                "strategy": strategy,
                "squad_overlap": overlap,
                "n_entered": len(entered),
                "n_left": len(left),
                "mean_mu_lift_ent": round(_mean(ent_mu_lift), 4) if ent_mu_lift else 0.0,
                "mean_u_lift_ent": round(_mean(ent_u_lift), 4) if ent_u_lift else 0.0,
                "mean_v2b_lift_ent": round(_mean(ent_v2b_lift), 4) if ent_v2b_lift else 0.0,
                "mean_actual_ent": round(_mean(ent_actual), 4) if ent_actual else 0.0,
                "mean_mu_err_ent": round(_mean(ent_mu_err), 4) if ent_mu_err else 0.0,
                "mean_actual_lev": round(_mean(lev_actual), 4) if lev_actual else 0.0,
                "delta_xi_picked": round(delta_xi_picked, 4),
                "delta_xi_cf_ctrl_pool": round(delta_xi_cf_ctrl_pool, 4),
                "delta_xi_cf_treat_pool": round(delta_xi_cf_treat_pool, 4),
                "xi_changed": int(c_xi != t_xi),
            })

    print(f"  gw-rows={len(gw_rows)} movers={len(mover_rows)}")
    return gw_rows, mover_rows


def summarize(gw_rows: list[dict], mover_rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E033: squad-pool / mu-inflation diagnostic")
    lines.append("cf_ctrl_pool = treat-ranked XI on control 15; cf_treat_pool = ctrl-ranked XI on treat 15")
    lines.append("")

    entrants = [r for r in mover_rows if r["movement"] == "entered"]
    for strategy in STRATEGIES:
        lines.append(f"=== strategy={strategy} ===")
        sr_gw = [r for r in gw_rows if r["strategy"] == strategy]
        sr_ent = [r for r in entrants if r["strategy"] == strategy]
        for gate in ("FAIL", "PASS"):
            g = [r for r in sr_gw if r["e024_gate"] == gate]
            e = [r for r in sr_ent if r["e024_gate"] == gate]
            n = len(g)
            if n < 3:
                lines.append(f"  {gate}: n={n} (too few)")
                continue

            lines.append(f"  {gate}: n={n} movers_entered={len(e)}")
            lines.append(
                f"    mean_squad_overlap={statistics.mean(int(r['squad_overlap']) for r in g):.1f} "
                f"mean_n_entered={statistics.mean(int(r['n_entered']) for r in g):.2f}"
            )
            lines.append(
                f"    mean_dXI_picked={statistics.mean(float(r['delta_xi_picked']) for r in g):.3f} "
                f"mean_dXI_cf_ctrl_pool={statistics.mean(float(r['delta_xi_cf_ctrl_pool']) for r in g):.3f} "
                f"mean_dXI_cf_treat_pool={statistics.mean(float(r['delta_xi_cf_treat_pool']) for r in g):.3f}"
            )
            pool_wins = sum(
                1 for r in g
                if float(r["delta_xi_cf_treat_pool"]) > float(r["delta_xi_picked"])
            )
            rank_wins = sum(
                1 for r in g
                if float(r["delta_xi_cf_ctrl_pool"]) > float(r["delta_xi_picked"])
            )
            lines.append(
                f"    cf_treat_pool_ctrl > picked: {pool_wins}/{n} "
                f"cf_ctrl_pool_treat > picked: {rank_wins}/{n}"
            )

            if e:
                mu_l = [float(r["mu_lift"]) for r in e]
                u_l = [float(r["u_lift"]) for r in e]
                v2b_l = [float(r["v2b_mu_lift"]) for r in e]
                act = [float(r["actual_pts"]) for r in e]
                err = [float(r["mu_error"]) for r in e]
                lines.append(
                    f"    entrants: mean_mu_lift={statistics.mean(mu_l):.3f} "
                    f"mean_u_lift={statistics.mean(u_l):.3f} "
                    f"mean_v2b_lift={statistics.mean(v2b_l):.3f} "
                    f"mean_actual={statistics.mean(act):.3f} "
                    f"mean_mu_error={statistics.mean(err):.3f}"
                )
                lines.append(
                    f"    corr(mu_lift,actual) entrants={_pearson(mu_l, act):.3f} "
                    f"corr(u_lift,actual)={_pearson(u_l, act):.3f}"
                )

        lines.append("")

    text = "\n".join(lines) + "\n"
    print(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e033] squad pool diagnostic; balanced vs safe; no new objective")
    all_gw: list[dict] = []
    all_mov: list[dict] = []
    for s in seasons:
        gw, mov = analyze_season(s)
        all_gw.extend(gw)
        all_mov.extend(mov)

    OUT_GW.parent.mkdir(parents=True, exist_ok=True)
    gw_fields = [
        "season", "e024_gate", "gw", "strategy",
        "squad_overlap", "n_entered", "n_left",
        "mean_mu_lift_ent", "mean_u_lift_ent", "mean_v2b_lift_ent",
        "mean_actual_ent", "mean_mu_err_ent", "mean_actual_lev",
        "delta_xi_picked", "delta_xi_cf_ctrl_pool", "delta_xi_cf_treat_pool",
        "xi_changed",
    ]
    with OUT_GW.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=gw_fields)
        w.writeheader()
        w.writerows(all_gw)
    print(f"Wrote {OUT_GW} ({len(all_gw)} rows)")

    mov_fields = [
        "season", "e024_gate", "gw", "strategy", "movement", "player_id",
        "mu_lift", "u_lift", "v2b_mu_lift", "actual_pts", "mu_error",
        "treat_mu", "ctrl_mu",
    ]
    with OUT_MOVERS.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=mov_fields)
        w.writeheader()
        w.writerows(all_mov)
    print(f"Wrote {OUT_MOVERS} ({len(all_mov)} rows)")

    summary = summarize(all_gw, all_mov)
    OUT_TXT.write_text(summary, encoding="utf-8")
    print(f"Wrote {OUT_TXT}")


if __name__ == "__main__":
    main()
