"""E039-A: counterfactual regret evaluator for fixture-concentration V_ns.

Frozen candidate (docs/LAB_LOG.md E039-A):

    V_ns(S) = sum_{i in XI} U_i  -  λ * sum_f C(n_f(S), 2)
    λ = 0.5
    f = Premier League match identity in GW T (as-of-T)

U_i from production stack (v2am_s + rates=v1 + fixtures v1).
Admission sample: E024-class ctrl(v1) → treat(packaged rates_v2b) same-pos pairs
(E036-style units). Scoring uses production U only.

Primary (FAIL, both60):
  1) novelty: ranking / prefs differ from U (not monotone-equivalent)
  2) decision: concordance of ΔV vs realized dpts beats concordance of ΔU

No ILP change. No λ sweep. Diagnostic only.

Usage:
    python scripts/e039_counterfactual_regret.py
    python scripts/e039_counterfactual_regret.py --season 2023-24
"""
from __future__ import annotations

import argparse
import csv
import math
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
from engine.optimize import solve_squad, solve_xi
from engine.packaging import apply_packaged_next_utility
from engine.project import project_all

OUT = Path("records") / "historical" / "e039_counterfactual_regret_pairs.csv"
OUT_GW = Path("records") / "historical" / "e039_counterfactual_regret_gw.csv"
OUT_TXT = Path("records") / "historical" / "e039_counterfactual_regret_summary.txt"
SEED = 7
OBJECTIVE = "next"
STRATEGY = "balanced"
LAMBDA = 0.5
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}
# Cap feasible-set size per leaver for regret (as-of-T pool, top by U + treat entrants).
F_TOP_K = 25


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


def build_swap_squad(ctrl_players: list[Player], entrant: Player, leaver_id: int) -> list[Player]:
    out = [p for p in ctrl_players if p.id != leaver_id]
    out.append(entrant)
    return out


def fixture_pair_count(xi: list[Player], snap, gw: int) -> float:
    """Sum_f C(n_f, 2) for XI players sharing Premier League match f in GW."""
    fixtures = snap.fixtures_for(gw)
    team_to_fids: dict[int, list[int]] = defaultdict(list)
    for fx in fixtures:
        team_to_fids[fx.team_h].append(fx.id)
        team_to_fids[fx.team_a].append(fx.id)
    counts: dict[int, int] = defaultdict(int)
    for p in xi:
        for fid in team_to_fids.get(p.team_id, []):
            counts[fid] += 1
    total = 0.0
    for n in counts.values():
        if n >= 2:
            total += n * (n - 1) / 2.0
    return total


def v_ns(squad: list[Player], xi: list[Player], by_u: dict, snap, gw: int) -> float:
    """E039-A: sum XI U − λ × fixture pairs."""
    util_sum = sum(by_u[p.id].next_utility for p in xi)
    return util_sum - LAMBDA * fixture_pair_count(xi, snap, gw)


def _spearman(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    rx = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: xs[i]), start=1)}
    ry = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: ys[i]), start=1)}
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return 1.0 - (6.0 * d2) / (n * (n * n - 1))


def concordance(subset: list[dict], score_key: str) -> tuple[float, int, int]:
    nontie = [r for r in subset if not r["tie_pts"]]
    pref = [r for r in nontie if r[score_key] > 0]
    if not pref:
        return float("nan"), 0, 0
    agree = sum(1 for r in pref if r["actual_pref_enter"])
    return 100.0 * agree / len(pref), len(pref), len(nontie)


def sign_agreement(subset: list[dict], score_key: str) -> tuple[float, int]:
    """% where sign(score) matches sign(dpts), among nontie dpts and nontie score."""
    rows = [r for r in subset if not r["tie_pts"] and r[score_key] != 0]
    if not rows:
        return float("nan"), 0
    agree = sum(1 for r in rows if (r[score_key] > 0) == (r["dpts"] > 0))
    return 100.0 * agree / len(rows), len(rows)


def analyze_season(season: str) -> tuple[list[dict], list[dict]]:
    ensure_vaastav((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E039-A counterfactual regret gate={gate} ===")
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
        by_u = {p.player.id: p for p in v1}  # production U for V_ns / ΔU

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
            xi_ctrl, _ = solve_xi(snap, sol_c.players, by_u)
            v_ctrl = v_ns(sol_c.players, xi_ctrl, by_u, snap, gw)
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

        # Feasible F per leaver: top-K by production U outside ctrl, same position.
        pool_by_pos: dict[str, list[Player]] = defaultdict(list)
        for p in snap.players:
            if p.id in c_squad:
                continue
            if not p.can_select:
                continue
            pool_by_pos[p.position].append(p)
        for pos, plist in pool_by_pos.items():
            plist.sort(key=lambda p: by_u[p.id].next_utility, reverse=True)

        gw_delta_v_sum = 0.0
        gw_delta_u_sum = 0.0
        n_pairs = 0
        n_reorder = 0

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
                        xi_s, _ = solve_xi(snap, squad_s, by_u)
                    except RuntimeError:
                        continue

                    v_swap = v_ns(squad_s, xi_s, by_u, snap, gw)
                    delta_v = v_swap - v_ctrl
                    delta_u = by_u[eid].next_utility - by_u[lid].next_utility
                    dpts = _pts(act, eid) - _pts(act, lid)
                    e_mins = _mins(act, eid)
                    l_mins = _mins(act, lid)
                    both60 = int(e_mins >= 60 and l_mins >= 60)

                    # Feasible set F for regret (same leaver).
                    cand_ids: list[int] = []
                    seen: set[int] = set()
                    for p in pool_by_pos.get(pos, [])[:F_TOP_K]:
                        if p.id in seen:
                            continue
                        sq = build_swap_squad(sol_c.players, p, lid)
                        if squad_feasible(snap, sq):
                            cand_ids.append(p.id)
                            seen.add(p.id)
                    if eid not in seen:
                        sq = build_swap_squad(sol_c.players, entrant, lid)
                        if squad_feasible(snap, sq):
                            cand_ids.append(eid)
                            seen.add(eid)

                    y_by_id = {cid: _pts(act, cid) for cid in cand_ids}
                    best_y = max(y_by_id.values()) if y_by_id else float("nan")
                    regret_e = (best_y - y_by_id[eid]) if eid in y_by_id else float("nan")

                    reorder = int(
                        (delta_u > 0 and delta_v < 0)
                        or (delta_u < 0 and delta_v > 0)
                    )
                    n_reorder += reorder
                    gw_delta_v_sum += delta_v
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
                        "delta_v": round(delta_v, 4),
                        "delta_u": round(delta_u, 4),
                        "dpts": round(dpts, 4),
                        "both60": both60,
                        "tie_pts": int(dpts == 0),
                        "v_pref_enter": int(delta_v > 0),
                        "u_pref_enter": int(delta_u > 0),
                        "actual_pref_enter": int(dpts > 0),
                        "sign_disagree": reorder,
                        "n_feasible": len(cand_ids),
                        "best_y_feasible": round(best_y, 4) if best_y == best_y else "",
                        "regret_entrant": round(regret_e, 4) if regret_e == regret_e else "",
                        "v_ctrl": round(v_ctrl, 4),
                        "v_swap": round(v_swap, 4),
                        "fixture_pairs_ctrl": round(fixture_pair_count(xi_ctrl, snap, gw), 4),
                        "fixture_pairs_swap": round(fixture_pair_count(xi_s, snap, gw), 4),
                    })

        gw_rows.append({
            "season": season,
            "e024_gate": gate,
            "gw": gw,
            "delta_cap": round(delta_cap, 4),
            "sum_delta_v": round(gw_delta_v_sum, 4),
            "sum_delta_u": round(gw_delta_u_sum, 4),
            "n_swap_pairs": n_pairs,
            "n_sign_disagree": n_reorder,
            "portfolio_bad": int(delta_cap < 0),
        })

    both60_n = sum(1 for r in pair_rows if r["both60"])
    print(f"  pair-rows={len(pair_rows)} both60={both60_n}")
    return pair_rows, gw_rows


def _finite(rows: list[dict], key: str) -> list[dict]:
    out = []
    for r in rows:
        v = r.get(key, "")
        if v == "" or v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if math.isnan(fv):
            continue
        out.append(r)
    return out


def summarize(pair_rows: list[dict], gw_rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E039-A: fixture-concentration V_ns vs separable U")
    lines.append(f"V_ns = sum_XI U - {LAMBDA} * sum_f C(n_f, 2); production U; E024 pair sample")
    lines.append("primary FAIL both60: novelty (!= monotone U) AND concordance beats U")
    lines.append("")

    for gate in ("FAIL", "PASS"):
        g60 = [r for r in pair_rows if r["e024_gate"] == gate and r["both60"]]
        lines.append(f"=== {gate} both60 same-pos pairs n={len(g60)} ===")
        if len(g60) < 3:
            lines.append("  (too few)")
            lines.append("")
            continue

        v_conc, v_pref_n, v_nontie = concordance(g60, "delta_v")
        u_conc, u_pref_n, u_nontie = concordance(g60, "delta_u")
        v_agree, v_agree_n = sign_agreement(g60, "delta_v")
        u_agree, u_agree_n = sign_agreement(g60, "delta_u")
        disagree = sum(1 for r in g60 if r["sign_disagree"])
        same_sign = len(g60) - disagree
        lines.append(
            f"  concordance V (pref enter): {v_conc:.1f}% "
            f"(model_pref_nontie={v_pref_n} nontie={v_nontie})"
            if v_conc == v_conc else
            f"  concordance V (pref enter): nan (model_pref_nontie={v_pref_n})"
        )
        lines.append(
            f"  concordance U (pref enter): {u_conc:.1f}% "
            f"(model_pref_nontie={u_pref_n} nontie={u_nontie})"
            if u_conc == u_conc else
            f"  concordance U (pref enter): nan (model_pref_nontie={u_pref_n})"
        )
        lines.append(
            f"  sign_agreement V: {v_agree:.1f}% (n={v_agree_n})"
            if v_agree == v_agree else "  sign_agreement V: nan"
        )
        lines.append(
            f"  sign_agreement U: {u_agree:.1f}% (n={u_agree_n})"
            if u_agree == u_agree else "  sign_agreement U: nan"
        )
        lines.append(
            f"  novelty: sign_disagree={disagree}/{len(g60)} "
            f"({100.0 * disagree / len(g60):.1f}%); same_sign={same_sign}"
        )
        sp_v = _spearman([r["delta_v"] for r in g60], [r["dpts"] for r in g60])
        sp_u = _spearman([r["delta_u"] for r in g60], [r["dpts"] for r in g60])
        lines.append(f"  spearman(delta_v, dpts)={sp_v:.3f}")
        lines.append(f"  spearman(delta_u, dpts)={sp_u:.3f}")

        g_reg = _finite(g60, "regret_entrant")
        g_reg = [r for r in g_reg if r["n_feasible"] >= 2]
        sp_vr = sp_ur = float("nan")
        if len(g_reg) >= 3:
            sp_vr = _spearman(
                [r["delta_v"] for r in g_reg],
                [-float(r["regret_entrant"]) for r in g_reg],
            )
            sp_ur = _spearman(
                [r["delta_u"] for r in g_reg],
                [-float(r["regret_entrant"]) for r in g_reg],
            )
            lines.append(
                f"  regret n={len(g_reg)}: spearman(delta_v, -regret)={sp_vr:.3f} "
                f"spearman(delta_u, -regret)={sp_ur:.3f}"
            )
            lines.append(f"  mean_regret_entrant={statistics.mean(float(r['regret_entrant']) for r in g_reg):.3f}")
        lines.append(f"  mean_dpts={statistics.mean(r['dpts'] for r in g60):.3f}")
        lines.append("")

    lines.append("=== GW-level secondary ===")
    for gate in ("FAIL", "PASS"):
        g = [r for r in gw_rows if r["e024_gate"] == gate and r["n_swap_pairs"] > 0]
        if len(g) < 3:
            continue
        sp_v = _spearman([r["sum_delta_v"] for r in g], [r["delta_cap"] for r in g])
        sp_u = _spearman([r["sum_delta_u"] for r in g], [r["delta_cap"] for r in g])
        lines.append(
            f"  {gate} n={len(g)}: spearman(sum_v, dcap)={sp_v:.3f} "
            f"spearman(sum_u, dcap)={sp_u:.3f}"
        )
    lines.append("")

    # Gate call (FAIL primary). Decision uses spearman + sign_agreement
    # because production-U on treat admissions often has delta_u <= 0 (pref-enter empty).
    fail60 = [r for r in pair_rows if r["e024_gate"] == "FAIL" and r["both60"]]
    if len(fail60) >= 3:
        v_agree, _ = sign_agreement(fail60, "delta_v")
        u_agree, _ = sign_agreement(fail60, "delta_u")
        disagree = sum(1 for r in fail60 if r["sign_disagree"])
        novelty = disagree > 0
        sp_v = _spearman([r["delta_v"] for r in fail60], [r["dpts"] for r in fail60])
        sp_u = _spearman([r["delta_u"] for r in fail60], [r["dpts"] for r in fail60])
        g_reg = [r for r in _finite(fail60, "regret_entrant") if r["n_feasible"] >= 2]
        regret_win = False
        if len(g_reg) >= 3:
            sp_vr = _spearman(
                [r["delta_v"] for r in g_reg],
                [-float(r["regret_entrant"]) for r in g_reg],
            )
            sp_ur = _spearman(
                [r["delta_u"] for r in g_reg],
                [-float(r["regret_entrant"]) for r in g_reg],
            )
            regret_win = sp_vr == sp_vr and sp_ur == sp_ur and sp_vr > sp_ur
        spearman_win = sp_v == sp_v and sp_u == sp_u and sp_v > sp_u
        agree_win = v_agree == v_agree and u_agree == u_agree and v_agree > u_agree
        # Primary decision metric: spearman vs realized dpts (pref-enter concordance
        # is often empty for production-U on treat admissions).
        decision_win = spearman_win
        lines.append("=== PRIMARY GATE (FAIL both60) ===")
        lines.append(f"  novelty (any sign disagreement): {novelty} ({disagree}/{len(fail60)})")
        lines.append(
            f"  decision spearman(V>U on dpts): {spearman_win} "
            f"(V={sp_v:.3f} U={sp_u:.3f})"
        )
        lines.append(
            f"  secondary sign_agreement(V>U): {agree_win} "
            f"(V={v_agree:.1f}% U={u_agree:.1f}%)"
            if v_agree == v_agree and u_agree == u_agree else
            "  secondary sign_agreement(V>U): n/a"
        )
        lines.append(f"  secondary regret spearman(V>U): {regret_win}")
        lines.append(f"  decision_win (spearman primary): {decision_win}")
        if novelty and decision_win:
            lines.append("  CALL: E039-A SURVIVES primary gate (optimizer still requires separate prereg)")
        elif not novelty:
            lines.append("  CALL: E039-A KILL — novelty-fail (monotone/same ordering as U)")
        else:
            lines.append("  CALL: E039-A KILL — decision-fail (differs but does not beat U)")
        lines.append("")

    text = "\n".join(lines) + "\n"
    print(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default=None, help="Single season; default all supported")
    args = parser.parse_args()
    seasons = (args.season,) if args.season else tuple(SUPPORTED_SEASONS)

    all_pairs: list[dict] = []
    all_gw: list[dict] = []
    for season in seasons:
        pairs, gw = analyze_season(season)
        all_pairs.extend(pairs)
        all_gw.extend(gw)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if all_pairs:
        with OUT.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(all_pairs[0].keys()))
            w.writeheader()
            w.writerows(all_pairs)
    if all_gw:
        with OUT_GW.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(all_gw[0].keys()))
            w.writeheader()
            w.writerows(all_gw)

    text = summarize(all_pairs, all_gw)
    OUT_TXT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"wrote {OUT_GW}")
    print(f"wrote {OUT_TXT}")


if __name__ == "__main__":
    main()
