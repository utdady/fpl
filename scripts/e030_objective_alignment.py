"""E030 diagnostic: objective alignment (predicted vs realized portfolio outcomes).

Frozen stack: control v2am_s+rates=v1 vs packaged rates_v2b; objective=next; seed=7.
Strategies: balanced (mu) and safe (mu - 0.4*sigma) — existing objectives only.

GW-level metrics per E024 gate (FAIL/PASS):
  corr(delta U_pred XI, delta pts XI)
  corr(delta U_pred XI, delta Cap)
  P(local bad | portfolio good)
  P(local bad | portfolio bad)

local bad: >=1 same-position ctrl->treat pair with both>=60 and dpts<0
portfolio good/bad: treat Cap >= control Cap (GW level)

No new objective. No packaging. Diagnostic only.

Usage:
    python scripts/e030_objective_alignment.py
    python scripts/e030_objective_alignment.py --season 2023-24
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
from engine.models import PlayerProjection
from engine.optimize import solve_squad
from engine.packaging import apply_packaged_next_utility
from engine.project import project_all

OUT_GW = Path("records") / "historical" / "e030_objective_alignment_gw.csv"
OUT_TXT = Path("records") / "historical" / "e030_objective_alignment_summary.txt"
SEED = 7
OBJECTIVE = "next"
STRATEGIES = ("balanced", "safe")
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}


def player_lookup(projections: list[PlayerProjection]) -> dict[int, PlayerProjection]:
    return {p.player.id: p for p in projections}


def same_position_pairs(
    entered: set[int],
    left: set[int],
    by_id: dict[int, PlayerProjection],
) -> list[tuple[int, int]]:
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


def has_local_bad(
    entered: set[int],
    left: set[int],
    by_c: dict[int, PlayerProjection],
    act: dict,
) -> bool:
    for eid, lid in same_position_pairs(entered, left, by_c):
        e_mins = float(act.get(eid, {}).get("actual_minutes", 0) or 0)
        l_mins = float(act.get(lid, {}).get("actual_minutes", 0) or 0)
        if e_mins < 60 or l_mins < 60:
            continue
        e_pts = float(act.get(eid, {}).get("actual_points", 0) or 0)
        l_pts = float(act.get(lid, {}).get("actual_points", 0) or 0)
        if e_pts < l_pts:
            return True
    return False


def xi_points(xi_ids: set[int], act: dict) -> float:
    return sum(float(act.get(pid, {}).get("actual_points", 0) or 0) for pid in xi_ids)


def cap_points(sol, act: dict) -> float:
    total = sum(float(act.get(p.id, {}).get("actual_points", 0) or 0) for p in sol.xi)
    total += float(act.get(sol.captain.id, {}).get("actual_points", 0) or 0)
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


def analyze_season(season: str) -> list[dict]:
    ensure_vaastav((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E030 objective alignment gate={gate} ===")
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
            snap, horizon=1, strategy="balanced", seed=SEED,
            minutes_version="v2am_s", rates_version="v1", fixtures_version="v1",
        )
        v2b = project_all(
            snap, horizon=1, strategy="balanced", seed=SEED,
            minutes_version="v2am_s", rates_version="v2b", fixtures_version="v1",
        )
        by_c = player_lookup(v1)

        for strategy in STRATEGIES:
            packaged = apply_packaged_next_utility(
                v2b, v1, recent_minutes=recent, as_of_gw=gw, strategy=strategy,
            )
            v1_s = project_all(
                snap, horizon=1, strategy=strategy, seed=SEED,
                minutes_version="v2am_s", rates_version="v1", fixtures_version="v1",
            )
            try:
                sol_c = solve_squad(snap, v1_s, strategy=strategy, objective=OBJECTIVE)
                sol_t = solve_squad(snap, packaged, strategy=strategy, objective=OBJECTIVE)
            except RuntimeError:
                continue

            c_xi = {p.id for p in sol_c.xi}
            t_xi = {p.id for p in sol_t.xi}
            delta_u = sol_t.next_xi_utility - sol_c.next_xi_utility
            delta_xi_pts = xi_points(t_xi, act) - xi_points(c_xi, act)
            delta_cap = cap_points(sol_t, act) - cap_points(sol_c, act)
            local_bad = int(has_local_bad(t_xi - c_xi, c_xi - t_xi, by_c, act))
            portfolio_good = int(delta_cap >= 0)
            portfolio_bad = int(delta_cap < 0)

            rows.append({
                "season": season,
                "e024_gate": gate,
                "gw": gw,
                "strategy": strategy,
                "delta_u_pred": round(delta_u, 4),
                "delta_xi_pts": round(delta_xi_pts, 4),
                "delta_cap": round(delta_cap, 4),
                "local_bad": local_bad,
                "portfolio_good": portfolio_good,
                "portfolio_bad": portfolio_bad,
                "xi_changed": int(c_xi != t_xi),
                "n_swap_pairs": len(same_position_pairs(t_xi - c_xi, c_xi - t_xi, by_c)),
            })

    print(f"  gw-rows={len(rows)}")
    return rows


def _cond_rate(rows: list[dict], portfolio_key: str, n_local: str) -> tuple[float, int, int]:
    denom = [r for r in rows if r[portfolio_key]]
    if not denom:
        return float("nan"), 0, 0
    num = sum(r["local_bad"] for r in denom)
    return 100.0 * num / len(denom), num, len(denom)


def summarize(rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E030: objective alignment (ctrl vs packaged rates_v2b)")
    lines.append("Predicted: delta next_xi_utility; Realized: delta XI pts / delta Cap")
    lines.append("local bad: >=1 same-pos pair both>=60 with entrant pts < leaver pts")
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
            du = [r["delta_u_pred"] for r in g]
            dxi = [r["delta_xi_pts"] for r in g]
            dcap = [r["delta_cap"] for r in g]
            c_xi = _pearson(du, dxi)
            c_cap = _pearson(du, dcap)
            p_good, ng, dg = _cond_rate(g, "portfolio_good", "local_bad")
            p_bad, nb, db = _cond_rate(g, "portfolio_bad", "local_bad")
            mean_du = statistics.mean(du)
            mean_dcap = statistics.mean(dcap)
            lines.append(
                f"  {gate}: n={n} corr(dU,dXIpts)={c_xi:.3f} corr(dU,dCap)={c_cap:.3f} "
                f"P(local_bad|port_good)={p_good:.1f}% ({ng}/{dg}) "
                f"P(local_bad|port_bad)={p_bad:.1f}% ({nb}/{db}) "
                f"mean_dU={mean_du:.3f} mean_dCap={mean_dcap:.3f}"
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
    print("[e030] objective alignment diagnostic; balanced vs safe; no new objective")
    all_rows: list[dict] = []
    for s in seasons:
        all_rows.extend(analyze_season(s))

    fields = [
        "season", "e024_gate", "gw", "strategy",
        "delta_u_pred", "delta_xi_pts", "delta_cap",
        "local_bad", "portfolio_good", "portfolio_bad",
        "xi_changed", "n_swap_pairs",
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
