"""E037 diagnostic: portfolio value alignment (V_A vs V_B).

Pre-registered in docs/PORTFOLIO_VALUE_SPEC.md and docs/LAB_LOG.md.

Descriptive only — squads chosen with frozen objective=next ILP; score post-hoc.

Per GW (treat vs ctrl squads, same mu):
  V_A = next-GW XI utility + captain (sol.next_xi_utility)
  V_B = squad-weighted horizon_utility post XI-solve on horizon U
  delta_cap = realized treat Cap - ctrl Cap

Primary: corr(delta_V_A, delta_cap) vs corr(delta_V_B, delta_cap) on FAIL seasons.

Frozen: v2am_s + packaged rates_v2b vs rates=v1; balanced; seed=7.

Usage:
    python scripts/e037_portfolio_value_alignment.py
    python scripts/e037_portfolio_value_alignment.py --season 2023-24
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from pathlib import Path

import pulp

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
from engine.models import Player
from engine.optimize import BENCH_WEIGHT, solve_squad, solve_xi
from engine.packaging import apply_packaged_next_utility
from engine.project import project_all

OUT = Path("records") / "historical" / "e037_portfolio_value_alignment_gw.csv"
OUT_TXT = Path("records") / "historical" / "e037_portfolio_value_alignment_summary.txt"
SEED = 7
SQUAD_OBJECTIVE = "next"
STRATEGY = "balanced"
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}


def _pts(act: dict, pid: int) -> float:
    return float(act.get(pid, {}).get("actual_points", 0) or 0)


def cap_points(sol, act: dict) -> float:
    total = sum(_pts(act, p.id) for p in sol.xi)
    total += _pts(act, sol.captain.id)
    return total


def solve_xi_horizon(snap, squad: list[Player], by_id: dict) -> tuple[list[Player], list[Player]]:
    """XI maximizing horizon_utility (V_B scoring only)."""
    rules = snap.squad
    ids = [p.id for p in squad]
    pos = {p.id: p.position for p in squad}
    util = {p.id: by_id[p.id].horizon_utility for p in squad}

    prob = pulp.LpProblem("fpl_xi_horizon", pulp.LpMaximize)
    y = pulp.LpVariable.dicts("y", ids, 0, 1, pulp.LpInteger)
    prob += pulp.lpSum(util[i] * y[i] for i in ids)
    prob += pulp.lpSum(y[i] for i in ids) == rules.squad_play
    for pcode in rules.min_play:
        n_pos = pulp.lpSum(y[i] for i in ids if pos[i] == pcode)
        prob += n_pos >= rules.min_play[pcode], f"min_{pcode}"
        prob += n_pos <= rules.max_play[pcode], f"max_{pcode}"

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=10))
    start_ids = [i for i in ids if y[i].value() and y[i].value() > 0.5]
    if len(start_ids) != rules.squad_play:
        raise RuntimeError(f"XI horizon solver failed ({pulp.LpStatus[status]})")

    order = {"GKP": 0, "DEF": 1, "MID": 2, "FWD": 3}
    xi = sorted(
        [p for p in squad if p.id in start_ids],
        key=lambda p: (order[p.position], -by_id[p.id].horizon_mu),
    )
    bench = sorted(
        [p for p in squad if p.id not in start_ids],
        key=lambda p: (0 if p.position == "GKP" else 1, -by_id[p.id].horizon_mu),
    )
    return xi, bench


def squad_weighted_horizon(squad: list[Player], xi: list[Player], by_id: dict) -> float:
    xi_ids = {p.id for p in xi}
    total = 0.0
    for p in squad:
        u = by_id[p.id].horizon_utility
        w = (1.0 - BENCH_WEIGHT) if p.id in xi_ids else BENCH_WEIGHT
        total += w * u
    return total


def v_b_score(snap, squad: list[Player], by_id: dict) -> float:
    xi, _ = solve_xi_horizon(snap, squad, by_id)
    return squad_weighted_horizon(squad, xi, by_id)


def g_treat_score(snap, sol_c, sol_t, by_t: dict) -> float:
    xi_ctrl, _ = solve_xi(snap, sol_c.players, by_t)
    u_full = squad_weighted_next(sol_t.players, sol_t.xi, by_t)
    u_ctrl_comp = squad_weighted_next(sol_c.players, xi_ctrl, by_t)
    return u_full - u_ctrl_comp


def squad_weighted_next(squad: list[Player], xi: list[Player], by_id: dict) -> float:
    xi_ids = {p.id for p in xi}
    total = 0.0
    for p in squad:
        u = by_id[p.id].next_utility
        w = (1.0 - BENCH_WEIGHT) if p.id in xi_ids else BENCH_WEIGHT
        total += w * u
    return total


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


def mann_whitney_u(pos_scores: list[float], neg_scores: list[float]) -> float:
    if not pos_scores or not neg_scores:
        return float("nan")
    tagged = [(s, 1) for s in pos_scores] + [(s, 0) for s in neg_scores]
    tagged.sort(key=lambda x: x[0])
    ranks = [0.0] * len(tagged)
    i = 0
    while i < len(tagged):
        j = i
        while j < len(tagged) and tagged[j][0] == tagged[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[k] = avg_rank
        i = j
    n1 = len(pos_scores)
    r1 = sum(r for r, (_, lbl) in zip(ranks, tagged) if lbl == 1)
    return r1 - n1 * (n1 + 1) / 2.0


def auroc(pos_scores: list[float], neg_scores: list[float]) -> float:
    u = mann_whitney_u(pos_scores, neg_scores)
    if u != u:
        return float("nan")
    return u / (len(pos_scores) * len(neg_scores))


def analyze_season(season: str) -> list[dict]:
    ensure_vaastav((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E037 portfolio value alignment gate={gate} ===")
    rows: list[dict] = []

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue

        recent = recent_minutes_by_element(season, gw, window=RECENT_WINDOW)
        v1 = project_all(
            snap, horizon=1, strategy=STRATEGY, seed=SEED,
            minutes_version="v2am_s", rates_version="v1", fixtures_version="v1",
        )
        v2b = project_all(
            snap, horizon=1, strategy=STRATEGY, seed=SEED,
            minutes_version="v2am_s", rates_version="v2b", fixtures_version="v1",
        )
        packaged = apply_packaged_next_utility(
            v2b, v1, recent_minutes=recent, as_of_gw=gw, strategy=STRATEGY,
        )
        by_c = {p.player.id: p for p in v1}
        by_t = {p.player.id: p for p in packaged}

        try:
            sol_c = solve_squad(snap, v1, strategy=STRATEGY, objective=SQUAD_OBJECTIVE)
            sol_t = solve_squad(snap, packaged, strategy=STRATEGY, objective=SQUAD_OBJECTIVE)
        except RuntimeError:
            continue

        v_a_ctrl = sol_c.next_xi_utility
        v_a_treat = sol_t.next_xi_utility
        try:
            v_b_ctrl = v_b_score(snap, sol_c.players, by_c)
            v_b_treat = v_b_score(snap, sol_t.players, by_t)
        except RuntimeError:
            continue

        cap_ctrl = cap_points(sol_c, act)
        cap_treat = cap_points(sol_t, act)
        delta_cap = cap_treat - cap_ctrl
        delta_v_a = v_a_treat - v_a_ctrl
        delta_v_b = v_b_treat - v_b_ctrl
        g_treat = g_treat_score(snap, sol_c, sol_t, by_t)

        rows.append({
            "season": season,
            "e024_gate": gate,
            "gw": gw,
            "v_a_ctrl": round(v_a_ctrl, 4),
            "v_a_treat": round(v_a_treat, 4),
            "delta_v_a": round(delta_v_a, 4),
            "v_b_ctrl": round(v_b_ctrl, 4),
            "v_b_treat": round(v_b_treat, 4),
            "delta_v_b": round(delta_v_b, 4),
            "cap_ctrl": round(cap_ctrl, 4),
            "cap_treat": round(cap_treat, 4),
            "delta_cap": round(delta_cap, 4),
            "portfolio_bad": int(delta_cap < 0),
            "portfolio_good": int(delta_cap >= 0),
            "g_treat": round(g_treat, 4),
        })

    bad = sum(r["portfolio_bad"] for r in rows)
    print(f"  gw-rows={len(rows)} portfolio_bad={bad}")
    return rows


def gate_block(rows: list[dict], gate: str) -> list[str]:
    g = [r for r in rows if r["e024_gate"] == gate]
    lines: list[str] = []
    if len(g) < 3:
        lines.append(f"=== {gate} n={len(g)} (too few) ===")
        return lines
    dva = [float(r["delta_v_a"]) for r in g]
    dvb = [float(r["delta_v_b"]) for r in g]
    dcap = [float(r["delta_cap"]) for r in g]
    corr_a = _pearson(dva, dcap)
    corr_b = _pearson(dvb, dcap)
    bad = [r for r in g if r["portfolio_bad"]]
    good = [r for r in g if r["portfolio_good"]]
    auroc_a = auroc(
        [float(r["delta_v_a"]) for r in bad],
        [float(r["delta_v_a"]) for r in good],
    ) if len(bad) >= 3 and len(good) >= 3 else float("nan")
    auroc_b = auroc(
        [float(r["delta_v_b"]) for r in bad],
        [float(r["delta_v_b"]) for r in good],
    ) if len(bad) >= 3 and len(good) >= 3 else float("nan")
    lines.append(f"=== {gate} n={len(g)} portfolio_bad={len(bad)} ===")
    lines.append(f"  corr(delta_V_A, delta_cap)={corr_a:.3f}")
    lines.append(f"  corr(delta_V_B, delta_cap)={corr_b:.3f}")
    lines.append(f"  delta_corr(V_B - V_A)={corr_b - corr_a:.3f}")
    lines.append(f"  mean_delta_V_A={statistics.mean(dva):.3f} mean_delta_V_B={statistics.mean(dvb):.3f}")
    lines.append(f"  mean_delta_cap={statistics.mean(dcap):.3f}")
    if auroc_a == auroc_a:
        lines.append(f"  AUROC(delta_V_A, portfolio_bad)={auroc_a:.3f}")
    if auroc_b == auroc_b:
        lines.append(f"  AUROC(delta_V_B, portfolio_bad)={auroc_b:.3f}")

    gt = sorted(float(r["g_treat"]) for r in g)
    med = gt[len(gt) // 2]
    lo = [r for r in g if float(r["g_treat"]) <= med]
    hi = [r for r in g if float(r["g_treat"]) > med]
    if len(lo) >= 3 and len(hi) >= 3:
        lines.append(
            f"  g_treat low n={len(lo)}: corr_A={_pearson([float(r['delta_v_a']) for r in lo], [float(r['delta_cap']) for r in lo]):.3f} "
            f"corr_B={_pearson([float(r['delta_v_b']) for r in lo], [float(r['delta_cap']) for r in lo]):.3f}"
        )
        lines.append(
            f"  g_treat high n={len(hi)}: corr_A={_pearson([float(r['delta_v_a']) for r in hi], [float(r['delta_cap']) for r in hi]):.3f} "
            f"corr_B={_pearson([float(r['delta_v_b']) for r in hi], [float(r['delta_cap']) for r in hi]):.3f}"
        )
    return lines


def summarize(rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E037: portfolio value alignment V_A (next) vs V_B (horizon)")
    lines.append("primary: corr(delta_V, delta_cap); squads from frozen next ILP")
    lines.append("")
    for gate in ("FAIL", "PASS"):
        lines.extend(gate_block(rows, gate))
        lines.append("")
    text = "\n".join(lines) + "\n"
    print(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e037] V_A vs V_B alignment; descriptive only; no optimizer change")
    all_rows: list[dict] = []
    for s in seasons:
        all_rows.extend(analyze_season(s))

    fields = [
        "season", "e024_gate", "gw",
        "v_a_ctrl", "v_a_treat", "delta_v_a",
        "v_b_ctrl", "v_b_treat", "delta_v_b",
        "cap_ctrl", "cap_treat", "delta_cap",
        "portfolio_bad", "portfolio_good", "g_treat",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"Wrote {OUT} ({len(all_rows)} rows)")
    summary = summarize(all_rows)
    OUT_TXT.write_text(summary, encoding="utf-8")
    print(f"Wrote {OUT_TXT}")


if __name__ == "__main__":
    main()
