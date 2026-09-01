"""E034c diagnostic: pairwise swap vs ILP re-equilibration.

After E034b: must_include E triggers full treat 15 (delta_cascade=0).
E034c fixes the other 14: manual E<->L swap on ctrl 15, XI+cap only.

Per same-position (entrant E, leaver L) from ctrl->treat squad diff:
  pair:     ctrl 15 with E in / L out (no squad re-solve); solve_xi on treat utility
  delta_pair = cap(pair) - cap(ctrl)
  delta_ilp  = cap(must_include E) - cap(ctrl)   [tripwire]
  delta_full = cap(full treat) - cap(ctrl)
  delta_reeq = delta_full - delta_pair

Objective gaps (squad ILP weighting after solve_xi):
  G  = U_treat(S_full) - U_treat(S_pair)
  G0 = U_control(S_ctrl) - U_control(S_pair)

Frozen: packaged rates_v2b; balanced; objective=next; seed=7.
No new utility. No lambda. Diagnostic only.

Usage:
    python scripts/e034c_pairwise_swap.py
    python scripts/e034c_pairwise_swap.py --season 2023-24
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
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
from engine.models import Player
from engine.optimize import BENCH_WEIGHT, pick_captains, solve_squad, solve_xi
from engine.packaging import apply_packaged_next_utility
from engine.project import project_all

OUT = Path("records") / "historical" / "e034c_pairwise_swap.csv"
OUT_TXT = Path("records") / "historical" / "e034c_pairwise_swap_summary.txt"
SEED = 7
OBJECTIVE = "next"
STRATEGY = "balanced"
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}


def _pts(act: dict, pid: int) -> float:
    return float(act.get(pid, {}).get("actual_points", 0) or 0)


def cap_points(xi: list[Player], captain: Player, act: dict) -> float:
    total = sum(_pts(act, p.id) for p in xi)
    total += _pts(act, captain.id)
    return total


def squad_feasible(snap, players: list[Player]) -> bool:
    rules = snap.squad
    if len(players) != rules.squad_size:
        return False
    if sum(p.now_cost for p in players) > rules.budget:
        return False
    pos: dict[str, int] = defaultdict(int)
    team: dict[int, int] = defaultdict(int)
    for p in players:
        pos[p.position] += 1
        team[p.team_id] += 1
    for pcode, n in rules.squad_select.items():
        if pos.get(pcode, 0) != n:
            return False
    for c in team.values():
        if c > rules.team_limit:
            return False
    return True


def squad_weighted_utility(
    squad: list[Player],
    xi: list[Player],
    by_id: dict,
) -> float:
    xi_ids = {p.id for p in xi}
    total = 0.0
    for p in squad:
        u = by_id[p.id].next_utility
        w = (1.0 - BENCH_WEIGHT) if p.id in xi_ids else BENCH_WEIGHT
        total += w * u
    return total


def build_pair_squad(ctrl_players: list[Player], entrant: Player, leaver_id: int) -> list[Player]:
    out = [p for p in ctrl_players if p.id != leaver_id]
    out.append(entrant)
    return out


def analyze_season(season: str) -> list[dict]:
    ensure_vaastav((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E034c pairwise swap gate={gate} ===")
    rows: list[dict] = []
    players_by_id = {}

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue
        players_by_id = {p.id: p for p in snap.players}

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
            sol_c = solve_squad(snap, v1, strategy=STRATEGY, objective=OBJECTIVE)
            sol_t = solve_squad(snap, packaged, strategy=STRATEGY, objective=OBJECTIVE)
        except RuntimeError:
            continue

        c_squad = {p.id for p in sol_c.players}
        t_squad = {p.id for p in sol_t.players}
        entered = t_squad - c_squad
        left = c_squad - t_squad
        if not entered or not left:
            continue

        ctrl_cap = cap_points(sol_c.xi, sol_c.captain, act)
        full_cap = cap_points(sol_t.xi, sol_t.captain, act)
        delta_full = full_cap - ctrl_cap
        u_treat_full = squad_weighted_utility(sol_t.players, sol_t.xi, by_t)
        u_ctrl_ctrl = squad_weighted_utility(sol_c.players, sol_c.xi, by_c)

        ent_by_pos: dict[str, list[int]] = defaultdict(list)
        lev_by_pos: dict[str, list[int]] = defaultdict(list)
        for eid in entered:
            ent_by_pos[players_by_id[eid].position].append(eid)
        for lid in left:
            lev_by_pos[players_by_id[lid].position].append(lid)

        for pos in ent_by_pos:
            if pos not in lev_by_pos:
                continue
            for eid in ent_by_pos[pos]:
                entrant = players_by_id[eid]
                delta_ilp = float("nan")
                try:
                    sol_f = solve_squad(
                        snap, packaged, strategy=STRATEGY, objective=OBJECTIVE,
                        must_include={eid},
                    )
                    delta_ilp = cap_points(sol_f.xi, sol_f.captain, act) - ctrl_cap
                except RuntimeError:
                    pass

                for lid in lev_by_pos[pos]:
                    leaver = players_by_id[lid]
                    squad_p = build_pair_squad(sol_c.players, entrant, lid)
                    if not squad_feasible(snap, squad_p):
                        continue
                    try:
                        xi, _bench = solve_xi(snap, squad_p, by_t)
                        captain, _vice = pick_captains(xi, by_t)
                    except RuntimeError:
                        continue

                    pair_cap = cap_points(xi, captain, act)
                    delta_pair = pair_cap - ctrl_cap
                    delta_reeq = delta_full - delta_pair
                    u_treat_pair = squad_weighted_utility(squad_p, xi, by_t)
                    u_ctrl_pair = squad_weighted_utility(squad_p, xi, by_c)
                    g_treat = u_treat_full - u_treat_pair
                    g_ctrl = u_ctrl_ctrl - u_ctrl_pair

                    rows.append({
                        "season": season,
                        "e024_gate": gate,
                        "gw": gw,
                        "position": pos,
                        "entrant_id": eid,
                        "entrant_name": entrant.web_name,
                        "leaver_id": lid,
                        "leaver_name": leaver.web_name,
                        "delta_pair": round(delta_pair, 4),
                        "delta_ilp": round(delta_ilp, 4) if delta_ilp == delta_ilp else "",
                        "delta_full": round(delta_full, 4),
                        "delta_reeq": round(delta_reeq, 4),
                        "abs_reeq_gt_pair": int(abs(delta_reeq) > abs(delta_pair)),
                        "g_treat": round(g_treat, 4),
                        "g_ctrl": round(g_ctrl, 4),
                        "ctrl_cap": round(ctrl_cap, 4),
                        "pair_cap": round(pair_cap, 4),
                        "full_cap": round(full_cap, 4),
                        "entrant_pts": round(_pts(act, eid), 4),
                        "leaver_pts": round(_pts(act, lid), 4),
                        "dpts_swap": round(_pts(act, eid) - _pts(act, lid), 4),
                    })

    print(f"  pair-rows={len(rows)}")
    return rows


def summarize(rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E034c: pairwise swap vs ILP re-equilibration")
    lines.append("pair = manual E<->L on ctrl 15; delta_reeq = delta_full - delta_pair")
    lines.append("")

    for gate in ("FAIL", "PASS"):
        g = [r for r in rows if r["e024_gate"] == gate]
        if len(g) < 5:
            lines.append(f"=== {gate}: n={len(g)} (too few) ===")
            continue
        lines.append(f"=== {gate} pairs n={len(g)} ===")
        dp = [float(r["delta_pair"]) for r in g]
        dr = [float(r["delta_reeq"]) for r in g]
        df = [float(r["delta_full"]) for r in g]
        di = [float(r["delta_ilp"]) for r in g if r["delta_ilp"] != ""]
        gt = [float(r["g_treat"]) for r in g]
        g0 = [float(r["g_ctrl"]) for r in g]
        lines.append(
            f"  mean_delta_pair={statistics.mean(dp):.3f} "
            f"mean_delta_reeq={statistics.mean(dr):.3f} "
            f"mean_delta_full={statistics.mean(df):.3f}"
        )
        if di:
            lines.append(f"  mean_delta_ilp={statistics.mean(di):.3f}")
        lines.append(
            f"  mean_abs_pair={statistics.mean(abs(x) for x in dp):.3f} "
            f"mean_abs_reeq={statistics.mean(abs(x) for x in dr):.3f}"
        )
        rg = sum(int(r["abs_reeq_gt_pair"]) for r in g)
        lines.append(f"  |reeq|>|pair|: {100.0 * rg / len(g):.1f}% ({rg}/{len(g)})")
        lines.append(
            f"  mean_g_treat={statistics.mean(gt):.3f} mean_g_ctrl={statistics.mean(g0):.3f}"
        )
        dswap = [float(r["dpts_swap"]) for r in g]
        lines.append(f"  mean_dpts_swap(ent-leaver)={statistics.mean(dswap):.3f}")
        lines.append("")

    text = "\n".join(lines) + "\n"
    print(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e034c] pairwise swap; balanced; no new objective")
    all_rows: list[dict] = []
    for s in seasons:
        all_rows.extend(analyze_season(s))

    fields = [
        "season", "e024_gate", "gw", "position",
        "entrant_id", "entrant_name", "leaver_id", "leaver_name",
        "delta_pair", "delta_ilp", "delta_full", "delta_reeq", "abs_reeq_gt_pair",
        "g_treat", "g_ctrl",
        "ctrl_cap", "pair_cap", "full_cap",
        "entrant_pts", "leaver_pts", "dpts_swap",
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
