"""E032 diagnostic: XI objective audit (oracle XI, mu vs utility, squad pipeline).

Extends E030/E031 frozen stack. Locates whether FAIL misalignment is:
  A) picked-XI / utility ranking (oracle XI on fixed squad fixes alignment)
  B) squad pool / mu inversion (oracle XI still anti-aligns)
  C) utility transform (mu aligns, utility does not)

Frozen: control v2am_s+rates=v1 vs packaged rates_v2b; objective=next; seed=7.
Strategies: balanced, safe — existing objectives only.

Metrics per GW:
  delta_xi_picked     realized pts on picked XIs (E030)
  delta_xi_oracle     oracle XI on each squad (hindsight pts as utility)
  delta_mu_xi         sum(next_mu) on picked XIs (ctrl vs treat projections)
  delta_u_xi          sum(next_utility) on picked XIs only (no captain double)
  squad_xi_agree      squad-ILP implied starters == solve_xi starters (ctrl)

No new utility. No lambda. Diagnostic only.

Usage:
    python scripts/e032_xi_objective_audit.py
    python scripts/e032_xi_objective_audit.py --season 2023-24
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

import pulp

from engine.harness import (
    SUPPORTED_SEASONS,
    build_snapshot,
    ensure_vaastav,
    gw_actuals,
    recent_minutes_by_element,
)
from engine.metrics import record_path
from engine.minutes_struct import RECENT_WINDOW
from engine.models import Player, PlayerProjection, Snapshot
from engine.optimize import BENCH_WEIGHT, solve_squad, solve_xi
from engine.packaging import apply_packaged_next_utility
from engine.project import project_all

OUT_GW = Path("records") / "historical" / "e032_xi_objective_audit_gw.csv"
OUT_TXT = Path("records") / "historical" / "e032_xi_objective_audit_summary.txt"
SEED = 7
OBJECTIVE = "next"
STRATEGIES = ("balanced", "safe")
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}


def _pts(act: dict, pid: int) -> float:
    return float(act.get(pid, {}).get("actual_points", 0) or 0)


def _fake(player: Player, score: float) -> PlayerProjection:
    return PlayerProjection(
        player=player,
        by_gw={},
        horizon_mu=score,
        horizon_sigma=0.0,
        horizon_utility=score,
        next_mu=score,
        next_sigma=0.0,
        next_p_start=1.0,
        next_p_60=1.0,
        next_p_10=0.0,
        next_utility=score,
    )


def player_lookup(projections: list[PlayerProjection]) -> dict[int, PlayerProjection]:
    return {p.player.id: p for p in projections}


def actual_by_id(snapshot: Snapshot, act: dict) -> dict[int, PlayerProjection]:
    return {p.id: _fake(p, _pts(act, p.id)) for p in snapshot.players}


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


def squad_ilp_starters(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    objective: str = OBJECTIVE,
) -> set[int]:
    """Return starter ids implied by squad ILP s[i] variables (before solve_xi re-pick)."""
    rules = snapshot.squad
    by_id = player_lookup(projections)
    eligible = [
        p
        for p in snapshot.players
        if p.id in by_id and p.can_select and by_id[p.id].horizon_utility > -20
    ]
    ids = [p.id for p in eligible]
    if objective == "next":
        util = {p.id: by_id[p.id].next_utility for p in eligible}
    else:
        util = {p.id: by_id[p.id].horizon_utility for p in eligible}
    cost = {p.id: p.now_cost for p in eligible}
    pos = {p.id: p.position for p in eligible}
    team = {p.id: p.team_id for p in eligible}

    prob = pulp.LpProblem("fpl_squad_starters", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("x", ids, 0, 1, pulp.LpInteger)
    s = pulp.LpVariable.dicts("s", ids, 0, 1, pulp.LpInteger)
    prob += pulp.lpSum(
        util[i] * (BENCH_WEIGHT * x[i] + (1.0 - BENCH_WEIGHT) * s[i]) for i in ids
    )
    for i in ids:
        prob += s[i] <= x[i]
    prob += pulp.lpSum(x[i] for i in ids) == rules.squad_size
    prob += pulp.lpSum(s[i] for i in ids) == rules.squad_play
    prob += pulp.lpSum(cost[i] * x[i] for i in ids) <= rules.budget
    for pcode, n in rules.squad_select.items():
        prob += pulp.lpSum(x[i] for i in ids if pos[i] == pcode) == n
    for pcode in rules.min_play:
        n_start = pulp.lpSum(s[i] for i in ids if pos[i] == pcode)
        prob += n_start >= rules.min_play[pcode]
        prob += n_start <= rules.max_play[pcode]
    for tid in {team[i] for i in ids}:
        prob += pulp.lpSum(x[i] for i in ids if team[i] == tid) <= rules.team_limit

    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=25))
    chosen = {i for i in ids if x[i].value() and x[i].value() > 0.5}
    starters = {i for i in ids if s[i].value() and s[i].value() > 0.5}
    if len(chosen) != rules.squad_size or len(starters) != rules.squad_play:
        raise RuntimeError("squad ILP starter extraction failed")
    return starters


def analyze_season(season: str) -> list[dict]:
    ensure_vaastav((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E032 XI objective audit gate={gate} ===")
    rows: list[dict] = []

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue

        act_index = actual_by_id(snap, act)
        recent = recent_minutes_by_element(season, gw, window=RECENT_WINDOW)
        v1 = project_all(
            snap, horizon=1, strategy="balanced", seed=SEED,
            minutes_version="v2am_s", rates_version="v1", fixtures_version="v1",
        )
        v2b = project_all(
            snap, horizon=1, strategy="balanced", seed=SEED,
            minutes_version="v2am_s", rates_version="v2b", fixtures_version="v1",
        )

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
            try:
                sol_c = solve_squad(snap, v1_s, strategy=strategy, objective=OBJECTIVE)
                sol_t = solve_squad(snap, packaged, strategy=strategy, objective=OBJECTIVE)
            except RuntimeError:
                continue

            c_xi = {p.id for p in sol_c.xi}
            t_xi = {p.id for p in sol_t.xi}

            oracle_c_xi, _ = solve_xi(snap, sol_c.players, act_index)
            oracle_t_xi, _ = solve_xi(snap, sol_t.players, act_index)
            oracle_c_ids = {p.id for p in oracle_c_xi}
            oracle_t_ids = {p.id for p in oracle_t_xi}

            delta_u = sol_t.next_xi_utility - sol_c.next_xi_utility
            delta_xi_picked = xi_points_ids(t_xi, act) - xi_points_ids(c_xi, act)
            delta_xi_oracle = xi_points_ids(oracle_t_ids, act) - xi_points_ids(oracle_c_ids, act)

            delta_mu_xi = (
                sum(by_t[p.id].next_mu for p in sol_t.xi)
                - sum(by_c[p.id].next_mu for p in sol_c.xi)
            )
            delta_u_xi = (
                sum(by_t[p.id].next_utility for p in sol_t.xi)
                - sum(by_c[p.id].next_utility for p in sol_c.xi)
            )

            treat_picked_regret = xi_points_ids(t_xi, act) - xi_points_ids(oracle_t_ids, act)
            ctrl_picked_regret = xi_points_ids(c_xi, act) - xi_points_ids(oracle_c_ids, act)

            try:
                ilp_starters = squad_ilp_starters(snap, v1_s, objective=OBJECTIVE)
                squad_xi_agree = int(ilp_starters == c_xi)
            except RuntimeError:
                squad_xi_agree = -1

            rows.append({
                "season": season,
                "e024_gate": gate,
                "gw": gw,
                "strategy": strategy,
                "delta_u_pred": round(delta_u, 4),
                "delta_xi_picked": round(delta_xi_picked, 4),
                "delta_xi_oracle": round(delta_xi_oracle, 4),
                "delta_mu_xi": round(delta_mu_xi, 4),
                "delta_u_xi": round(delta_u_xi, 4),
                "treat_picked_regret": round(treat_picked_regret, 4),
                "ctrl_picked_regret": round(ctrl_picked_regret, 4),
                "squad_xi_agree": squad_xi_agree,
                "xi_changed": int(c_xi != t_xi),
                "picked_eq_oracle_treat": int(t_xi == oracle_t_ids),
            })

    print(f"  gw-rows={len(rows)}")
    return rows


def summarize(rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E032: XI objective audit (ctrl vs packaged rates_v2b)")
    lines.append("delta_xi_oracle = hindsight-best XI on each squad's 15")
    lines.append("delta_mu_xi = sum(next_mu) on picked XIs; delta_u_xi = sum(next_utility) on picked XIs")
    lines.append("")

    for strategy in STRATEGIES:
        lines.append(f"=== strategy={strategy} ===")
        sr = [r for r in rows if r["strategy"] == strategy]
        for gate in ("FAIL", "PASS"):
            g = [r for r in sr if r["e024_gate"] == gate]
            n = len(g)
            if n < 3:
                lines.append(f"  {gate}: n={n} (too few)")
                continue

            du = [float(r["delta_u_pred"]) for r in g]
            dxi_p = [float(r["delta_xi_picked"]) for r in g]
            dxi_o = [float(r["delta_xi_oracle"]) for r in g]
            dmu = [float(r["delta_mu_xi"]) for r in g]
            du_xi = [float(r["delta_u_xi"]) for r in g]

            agree = [r for r in g if int(r["squad_xi_agree"]) >= 0]
            agree_rate = (
                100.0 * sum(int(r["squad_xi_agree"]) for r in agree) / len(agree)
                if agree else float("nan")
            )

            lines.append(f"  {gate}: n={n} squad_xi_agree={agree_rate:.1f}%")
            lines.append(
                f"    corr(dU,dXI_picked)={_pearson(du, dxi_p):.3f} "
                f"corr(dU,dXI_oracle)={_pearson(du, dxi_o):.3f}"
            )
            lines.append(
                f"    corr(dU,dMu_xi)={_pearson(du, dmu):.3f} "
                f"corr(dU,dU_xi)={_pearson(du, du_xi):.3f}"
            )
            lines.append(
                f"    mean_dXI_picked={statistics.mean(dxi_p):.3f} "
                f"mean_dXI_oracle={statistics.mean(dxi_o):.3f} "
                f"mean_dMu_xi={statistics.mean(dmu):.3f}"
            )
            tr = [float(r["treat_picked_regret"]) for r in g]
            lines.append(
                f"    mean_treat_picked_regret={statistics.mean(tr):.3f} "
                f"(0=oracle; negative=picked beat oracle)"
            )
            peq = sum(int(r["picked_eq_oracle_treat"]) for r in g)
            lines.append(f"    picked_eq_oracle_treat={peq}/{n}")

        lines.append("")

    text = "\n".join(lines) + "\n"
    print(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e032] XI objective audit; balanced vs safe; no new objective")
    all_rows: list[dict] = []
    for s in seasons:
        all_rows.extend(analyze_season(s))

    fields = [
        "season", "e024_gate", "gw", "strategy",
        "delta_u_pred", "delta_xi_picked", "delta_xi_oracle",
        "delta_mu_xi", "delta_u_xi",
        "treat_picked_regret", "ctrl_picked_regret",
        "squad_xi_agree", "xi_changed", "picked_eq_oracle_treat",
    ]
    OUT_GW.parent.mkdir(parents=True, exist_ok=True)
    with OUT_GW.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"Wrote {OUT_GW} ({len(all_rows)} rows)")
    summary = summarize(all_rows)
    OUT_TXT.write_text(summary, encoding="utf-8")
    print(f"Wrote {OUT_TXT}")


if __name__ == "__main__":
    main()
