"""E036 / H-MC1 Phase A: contextual marginal admission value.

Compare standalone treat utility ranking vs contextual marginal contribution
at ctrl→treat squad boundary. Frozen mu; realized dpts as judge.

Per same-position (E,L) pair:
  V(S)     = squad-weighted treat utility post solve_xi (BENCH_WEIGHT=0.12)
  delta_mc = V(S_ctrl \\ L ∪ E) - V(S_ctrl)   manual swap, no squad ILP
  delta_u  = U_E - U_L                         treat next_utility
  dpts     = pts_E - pts_L

Primary: concordance sign(delta_mc) vs sign(dpts) vs sign(delta_u) on FAIL both60.

Frozen: packaged rates_v2b; balanced; objective=next; seed=7.
No MC in optimizer. Diagnostic only.

Usage:
    python scripts/e036_contextual_marginal.py
    python scripts/e036_contextual_marginal.py --season 2023-24
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
from engine.optimize import BENCH_WEIGHT, solve_squad, solve_xi
from engine.packaging import apply_packaged_next_utility
from engine.project import project_all

OUT = Path("records") / "historical" / "e036_contextual_marginal_pairs.csv"
OUT_GW = Path("records") / "historical" / "e036_contextual_marginal_gw.csv"
OUT_TXT = Path("records") / "historical" / "e036_contextual_marginal_summary.txt"
SEED = 7
OBJECTIVE = "next"
STRATEGY = "balanced"
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}
NEAR = 0.25
MID = 0.75


def _pts(act: dict, pid: int) -> float:
    return float(act.get(pid, {}).get("actual_points", 0) or 0)


def _mins(act: dict, pid: int) -> float:
    return float(act.get(pid, {}).get("actual_minutes", 0) or 0)


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


def squad_weighted_utility(squad: list[Player], xi: list[Player], by_id: dict) -> float:
    xi_ids = {p.id for p in xi}
    total = 0.0
    for p in squad:
        u = by_id[p.id].next_utility
        w = (1.0 - BENCH_WEIGHT) if p.id in xi_ids else BENCH_WEIGHT
        total += w * u
    return total


def build_swap_squad(ctrl_players: list[Player], entrant: Player, leaver_id: int) -> list[Player]:
    out = [p for p in ctrl_players if p.id != leaver_id]
    out.append(entrant)
    return out


def gap_bucket(abs_gap: float) -> str:
    if abs_gap < NEAR:
        return "near"
    if abs_gap < MID:
        return "mid"
    return "large"


def _spearman(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    rx = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: xs[i]), start=1)}
    ry = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: ys[i]), start=1)}
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return 1.0 - (6.0 * d2) / (n * (n * n - 1))


def concordance(subset: list[dict], score_key: str) -> tuple[float, int, int]:
    """% concordant among nontie pairs where model prefers entrant (score > 0)."""
    nontie = [r for r in subset if not r["tie_pts"]]
    pref = [r for r in nontie if r[score_key] > 0]
    if not pref:
        return float("nan"), 0, 0
    agree = sum(1 for r in pref if r["actual_pref_enter"])
    return 100.0 * agree / len(pref), len(pref), len(nontie)


def analyze_season(season: str) -> tuple[list[dict], list[dict]]:
    ensure_vaastav((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E036 contextual marginal gate={gate} ===")
    pair_rows: list[dict] = []
    gw_rows: list[dict] = []

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

        try:
            xi_ctrl, _ = solve_xi(snap, sol_c.players, by_t)
            v_ctrl = squad_weighted_utility(sol_c.players, xi_ctrl, by_t)
        except RuntimeError:
            continue

        ctrl_cap = sum(_pts(act, p.id) for p in sol_c.xi) + _pts(act, sol_c.captain.id)
        treat_cap = sum(_pts(act, p.id) for p in sol_t.xi) + _pts(act, sol_t.captain.id)
        delta_cap = treat_cap - ctrl_cap

        ent_by_pos: dict[str, list[int]] = defaultdict(list)
        lev_by_pos: dict[str, list[int]] = defaultdict(list)
        for eid in entered:
            ent_by_pos[players_by_id[eid].position].append(eid)
        for lid in left:
            lev_by_pos[players_by_id[lid].position].append(lid)

        gw_delta_mc_sum = 0.0
        gw_delta_u_sum = 0.0
        n_pairs = 0

        for pos in ent_by_pos:
            if pos not in lev_by_pos:
                continue
            for eid in ent_by_pos[pos]:
                entrant = players_by_id[eid]
                for lid in lev_by_pos[pos]:
                    leaver = players_by_id[lid]
                    squad_s = build_swap_squad(sol_c.players, entrant, lid)
                    if not squad_feasible(snap, squad_s):
                        continue
                    try:
                        xi_s, _ = solve_xi(snap, squad_s, by_t)
                    except RuntimeError:
                        continue

                    v_swap = squad_weighted_utility(squad_s, xi_s, by_t)
                    delta_mc = v_swap - v_ctrl
                    delta_u = by_t[eid].next_utility - by_t[lid].next_utility
                    dpts = _pts(act, eid) - _pts(act, lid)
                    e_mins = _mins(act, eid)
                    l_mins = _mins(act, lid)
                    both60 = int(e_mins >= 60 and l_mins >= 60)
                    ctrl_mu_gap = abs(by_c[eid].next_mu - by_c[lid].next_mu)

                    gw_delta_mc_sum += delta_mc
                    gw_delta_u_sum += delta_u
                    n_pairs += 1

                    pair_rows.append({
                        "season": season,
                        "e024_gate": gate,
                        "gw": gw,
                        "position": pos,
                        "entrant_id": eid,
                        "entrant_name": entrant.web_name,
                        "leaver_id": lid,
                        "leaver_name": leaver.web_name,
                        "delta_mc": round(delta_mc, 4),
                        "delta_u": round(delta_u, 4),
                        "dpts": round(dpts, 4),
                        "both60": both60,
                        "tie_pts": int(dpts == 0),
                        "mc_pref_enter": int(delta_mc > 0),
                        "u_pref_enter": int(delta_u > 0),
                        "actual_pref_enter": int(dpts > 0),
                        "ctrl_mu_gap": round(ctrl_mu_gap, 4),
                        "gap_bucket": gap_bucket(ctrl_mu_gap),
                        "v_ctrl": round(v_ctrl, 4),
                        "v_swap": round(v_swap, 4),
                    })

        gw_rows.append({
            "season": season,
            "e024_gate": gate,
            "gw": gw,
            "delta_cap": round(delta_cap, 4),
            "sum_delta_mc": round(gw_delta_mc_sum, 4),
            "sum_delta_u": round(gw_delta_u_sum, 4),
            "n_swap_pairs": n_pairs,
            "portfolio_bad": int(delta_cap < 0),
        })

    both60_n = sum(1 for r in pair_rows if r["both60"])
    print(f"  pair-rows={len(pair_rows)} both60={both60_n}")
    return pair_rows, gw_rows


def summarize(pair_rows: list[dict], gw_rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E036 / H-MC1: contextual marginal vs standalone utility")
    lines.append("primary: concordance sign(score) vs sign(dpts) on both60 pairs")
    lines.append("")

    for gate in ("FAIL", "PASS"):
        g60 = [r for r in pair_rows if r["e024_gate"] == gate and r["both60"]]
        lines.append(f"=== {gate} both60 same-pos pairs n={len(g60)} ===")
        if len(g60) < 3:
            lines.append("  (too few)")
            lines.append("")
            continue
        mc_conc, mc_pref_n, mc_nontie = concordance(g60, "delta_mc")
        u_conc, u_pref_n, u_nontie = concordance(g60, "delta_u")
        lines.append(
            f"  concordance MC: {mc_conc:.1f}% (model_pref_nontie={mc_pref_n} nontie={mc_nontie})"
        )
        lines.append(
            f"  concordance U:  {u_conc:.1f}% (model_pref_nontie={u_pref_n} nontie={u_nontie})"
        )
        sp_mc = _spearman([r["delta_mc"] for r in g60], [r["dpts"] for r in g60])
        sp_u = _spearman([r["delta_u"] for r in g60], [r["dpts"] for r in g60])
        lines.append(f"  spearman(delta_mc, dpts)={sp_mc:.3f}")
        lines.append(f"  spearman(delta_u, dpts)={sp_u:.3f}")
        lines.append(f"  mean_dpts={statistics.mean(r['dpts'] for r in g60):.3f}")
        lines.append("")

        for bucket in ("near", "mid", "large"):
            sub = [r for r in g60 if r["gap_bucket"] == bucket]
            if len(sub) < 3:
                continue
            mc_b, _, _ = concordance(sub, "delta_mc")
            u_b, _, _ = concordance(sub, "delta_u")
            lines.append(
                f"  bucket {bucket} n={len(sub)}: MC_conc={mc_b:.1f}% U_conc={u_b:.1f}%"
            )
        lines.append("")

    lines.append("=== GW-level secondary (sum_delta_mc vs delta_cap) ===")
    for gate in ("FAIL", "PASS"):
        g = [r for r in gw_rows if r["e024_gate"] == gate and r["n_swap_pairs"] > 0]
        if len(g) < 3:
            continue
        sp_mc = _spearman([r["sum_delta_mc"] for r in g], [r["delta_cap"] for r in g])
        sp_u = _spearman([r["sum_delta_u"] for r in g], [r["delta_cap"] for r in g])
        lines.append(f"  {gate} n={len(g)}: spearman(sum_mc, dcap)={sp_mc:.3f} spearman(sum_u, dcap)={sp_u:.3f}")
    lines.append("")

    text = "\n".join(lines) + "\n"
    print(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e036] H-MC1 contextual marginal; frozen mu; no optimizer change")
    all_pairs: list[dict] = []
    all_gw: list[dict] = []
    for s in seasons:
        pairs, gw = analyze_season(s)
        all_pairs.extend(pairs)
        all_gw.extend(gw)

    pair_fields = [
        "season", "e024_gate", "gw", "position",
        "entrant_id", "entrant_name", "leaver_id", "leaver_name",
        "delta_mc", "delta_u", "dpts", "both60", "tie_pts",
        "mc_pref_enter", "u_pref_enter", "actual_pref_enter",
        "ctrl_mu_gap", "gap_bucket", "v_ctrl", "v_swap",
    ]
    gw_fields = [
        "season", "e024_gate", "gw", "delta_cap",
        "sum_delta_mc", "sum_delta_u", "n_swap_pairs", "portfolio_bad",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=pair_fields)
        w.writeheader()
        w.writerows(all_pairs)
    print(f"Wrote {OUT} ({len(all_pairs)} rows)")
    with OUT_GW.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=gw_fields)
        w.writeheader()
        w.writerows(all_gw)
    print(f"Wrote {OUT_GW} ({len(all_gw)} rows)")
    summary = summarize(all_pairs, all_gw)
    OUT_TXT.write_text(summary, encoding="utf-8")
    print(f"Wrote {OUT_TXT}")


if __name__ == "__main__":
    main()
