"""E028 diagnostic: local substitution stability on actual XI swap pairs.

Collects actual entrant/leaver pairs from XI diffs (same-position only):
  ctrl_treat   : control -> unconstrained packaged treat
  ctrl_pack1   : control -> H-PACK1 stable
  treat_pack1  : unconstrained treat -> PACK1 (bound GWs only)

No new mechanism. No ε retune. Diagnostic only.

Usage:
    python scripts/e028_local_substitution.py
    python scripts/e028_local_substitution.py --season 2023-24
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
from engine.models import PlayerProjection
from engine.optimize import solve_squad
from engine.packaging import apply_packaged_next_utility
from engine.project import project_all
from engine.stability_selection import load_epsilon, solve_squad_stability, squad_objective_value

OUT = Path("records") / "historical" / "e028_local_substitution_pairs.csv"
OUT_TXT = Path("records") / "historical" / "e028_local_substitution_summary.txt"
SEED = 7
STRATEGY = "balanced"
NEAR = 0.25
MID = 0.75
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}

# E027 PACK1 vs control season gates (frozen; not recomputed from this script).
SEASON_GATE = {
    "2022-23": "both",
    "2023-24": "pass",
    "2024-25": "xi0_fail",
    "2025-26": "both",
}


def gap_bucket(abs_margin: float) -> str:
    if abs_margin < NEAR:
        return "near"
    if abs_margin < MID:
        return "mid"
    return "large"


def control_ranks(projections: list[PlayerProjection]) -> dict[int, int]:
    ranked = sorted(projections, key=lambda p: p.next_utility, reverse=True)
    return {p.player.id: i + 1 for i, p in enumerate(ranked)}


def player_lookup(projections: list[PlayerProjection]) -> dict[int, PlayerProjection]:
    return {p.player.id: p for p in projections}


def same_position_pairs(
    entered: set[int],
    left: set[int],
    by_id: dict[int, PlayerProjection],
) -> list[tuple[int, int]]:
    """Pair actual diff players within position (entrant, leaver)."""
    pairs: list[tuple[int, int]] = []
    by_pos: dict[str, tuple[list[int], list[int]]] = defaultdict(lambda: ([], []))
    for pid in entered:
        by_pos[by_id[pid].player.position][0].append(pid)
    for pid in left:
        by_pos[by_id[pid].player.position][1].append(pid)
    for _pos, (ents, levs) in by_pos.items():
        for e in ents:
            for left_id in levs:
                pairs.append((e, left_id))
    return pairs


def build_pair_row(
    *,
    season: str,
    gw: int,
    swap_set: str,
    enter_id: int,
    left_id: int,
    by_c: dict[int, PlayerProjection],
    by_t: dict[int, PlayerProjection],
    ranks: dict[int, int],
    act: dict,
    bound: int,
    gw_u0_slack: float,
    epsilon: float,
) -> dict:
    pc_e, pc_l = by_c[enter_id], by_c[left_id]
    pt_e = by_t[enter_id]
    ctrl_margin = pc_e.next_mu - pc_l.next_mu
    rank_dist = ranks[enter_id] - ranks[left_id]
    treat_lift = pt_e.next_mu - pc_e.next_mu
    e_mins = float(act.get(enter_id, {}).get("actual_minutes", 0) or 0)
    l_mins = float(act.get(left_id, {}).get("actual_minutes", 0) or 0)
    e_pts = float(act.get(enter_id, {}).get("actual_points", 0) or 0)
    l_pts = float(act.get(left_id, {}).get("actual_points", 0) or 0)
    both60 = int(e_mins >= 60 and l_mins >= 60)
    bad_swap = int(both60 and e_pts < l_pts)
    globally_admissible = int(gw_u0_slack <= epsilon + 1e-6)
    gate = SEASON_GATE.get(season, "?")
    e024_gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    return {
        "season": season,
        "e024_gate": e024_gate,
        "season_gate": gate,
        "gw": gw,
        "swap_set": swap_set,
        "enter_id": enter_id,
        "enter_name": pc_e.player.web_name,
        "enter_pos": pc_e.player.position,
        "left_id": left_id,
        "left_name": pc_l.player.web_name,
        "left_pos": pc_l.player.position,
        "ctrl_margin": round(ctrl_margin, 4),
        "abs_ctrl_margin": round(abs(ctrl_margin), 4),
        "gap_bucket": gap_bucket(abs(ctrl_margin)),
        "ctrl_rank_dist": rank_dist,
        "treat_lift": round(treat_lift, 4),
        "ctrl_mu_enter": round(pc_e.next_mu, 4),
        "ctrl_mu_left": round(pc_l.next_mu, 4),
        "treat_mu_enter": round(pt_e.next_mu, 4),
        "enter_mins": e_mins,
        "left_mins": l_mins,
        "enter_pts": e_pts,
        "left_pts": l_pts,
        "both60": both60,
        "bad_swap": bad_swap,
        "bound": bound,
        "gw_u0_slack": round(gw_u0_slack, 4),
        "epsilon": epsilon,
        "globally_admissible": globally_admissible,
    }


def analyze_season(season: str, epsilon: float) -> list[dict]:
    ensure_vaastav((season,))
    print(f"\n=== {season} E028 local substitution pairs ===")
    rows: list[dict] = []

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
        by_c = player_lookup(v1)
        by_t = player_lookup(v2b)
        ranks = control_ranks(v1)

        try:
            sol_c = solve_squad(snap, v1, strategy=STRATEGY, objective="next")
            sol_t = solve_squad(snap, packaged, strategy=STRATEGY, objective="next")
            sol_p, u0_pack, _ = solve_squad_stability(
                snap, v1, packaged, strategy=STRATEGY, epsilon=epsilon, objective="next",
            )
        except RuntimeError as e:
            print(f"    solver fail: {e}")
            continue

        u0_star = squad_objective_value(sol_c.players, sol_c.xi, by_c, objective="next")
        gw_u0_slack = u0_star - u0_pack
        c_xi = {p.id for p in sol_c.xi}
        t_xi = {p.id for p in sol_t.xi}
        p_xi = {p.id for p in sol_p.xi}
        bound = int(p_xi != t_xi)

        for swap_set, base, alt in (
            ("ctrl_treat", c_xi, t_xi),
            ("ctrl_pack1", c_xi, p_xi),
        ):
            entered = alt - base
            left = base - alt
            for eid, lid in same_position_pairs(entered, left, by_c):
                rows.append(
                    build_pair_row(
                        season=season,
                        gw=gw,
                        swap_set=swap_set,
                        enter_id=eid,
                        left_id=lid,
                        by_c=by_c,
                        by_t=by_t,
                        ranks=ranks,
                        act=act,
                        bound=bound,
                        gw_u0_slack=gw_u0_slack,
                        epsilon=epsilon,
                    )
                )

        if bound:
            entered = p_xi - t_xi
            left = t_xi - p_xi
            for eid, lid in same_position_pairs(entered, left, by_c):
                rows.append(
                    build_pair_row(
                        season=season,
                        gw=gw,
                        swap_set="treat_pack1",
                        enter_id=eid,
                        left_id=lid,
                        by_c=by_c,
                        by_t=by_t,
                        ranks=ranks,
                        act=act,
                        bound=1,
                        gw_u0_slack=gw_u0_slack,
                        epsilon=epsilon,
                    )
                )

    print(f"  pairs collected: {len(rows)}")
    return rows


def _bad_rate(subset: list[dict]) -> tuple[float, int]:
    both60 = [r for r in subset if r["both60"]]
    if not both60:
        return float("nan"), 0
    return 100.0 * sum(r["bad_swap"] for r in both60) / len(both60), len(both60)


def summarize(rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E028: local substitution stability diagnostic")
    lines.append(f"Buckets: near |margin|<{NEAR}, mid [{NEAR},{MID}), large >={MID}")
    lines.append("Pair unit: same-position actual entrant/leaver from XI diff")
    lines.append("")

    def block(label: str, subset: list[dict]) -> None:
        rate, n60 = _bad_rate(subset)
        lines.append(f"{label}: n={len(subset)} both60={n60} bad_swap%={rate:.1f}")

    for swap_set in ("ctrl_treat", "ctrl_pack1", "treat_pack1"):
        lines.append(f"=== {swap_set} ===")
        ss = [r for r in rows if r["swap_set"] == swap_set]
        for gate in ("FAIL", "PASS"):
            g = [r for r in ss if r["e024_gate"] == gate]
            block(f"  {gate} all", g)
            for b in ("near", "mid", "large"):
                cell = [r for r in g if r["gap_bucket"] == b]
                block(f"    {b}", cell)
            # globally admissible + near margin
            adm_near = [
                r for r in g
                if r["globally_admissible"] and r["gap_bucket"] == "near"
            ]
            block(f"    admissible+near", adm_near)
        lines.append("")

    lines.append("=== Central test: P(bad|both60) by ctrl_margin bucket (ctrl_treat) ===")
    ct = [r for r in rows if r["swap_set"] == "ctrl_treat"]
    for gate in ("FAIL", "PASS"):
        g = [r for r in ct if r["e024_gate"] == gate]
        near_r, near_n = _bad_rate([r for r in g if r["gap_bucket"] == "near"])
        large_r, large_n = _bad_rate([r for r in g if r["gap_bucket"] == "large"])
        lines.append(
            f"  {gate}: near bad%={near_r:.1f} (n60={near_n}) "
            f"large bad%={large_r:.1f} (n60={large_n})"
        )

    text = "\n".join(lines) + "\n"
    print(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    args = parser.parse_args()
    epsilon = load_epsilon()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print(f"[e028] local substitution diagnostic; eps={epsilon:.6f}; no mechanism")
    all_rows: list[dict] = []
    for s in seasons:
        all_rows.extend(analyze_season(s, epsilon))

    fields = [
        "season", "e024_gate", "season_gate", "gw", "swap_set",
        "enter_id", "enter_name", "enter_pos", "left_id", "left_name", "left_pos",
        "ctrl_margin", "abs_ctrl_margin", "gap_bucket", "ctrl_rank_dist", "treat_lift",
        "ctrl_mu_enter", "ctrl_mu_left", "treat_mu_enter",
        "enter_mins", "left_mins", "enter_pts", "left_pts",
        "both60", "bad_swap", "bound", "gw_u0_slack", "epsilon", "globally_admissible",
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
