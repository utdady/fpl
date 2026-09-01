"""E034b diagnostic: forced-swap counterfactual (entrant vs cascade).

Separates entrant-specific damage from portfolio cascade on squad admission.
Per squad entrant E (one at a time):
  forced: must_include={E} on treat packaged utility, re-solve squad
  delta_force(E) = XI+cap(forced) - XI+cap(ctrl)
  delta_full     = XI+cap(full treat) - XI+cap(ctrl)
  delta_cascade  = delta_full - delta_force(E)

If |delta_cascade| >> |delta_force| on FAIL -> portfolio response dominates.

Frozen: v2am_s + rates=v1 vs packaged rates_v2b; objective=next; seed=7; balanced.
No new utility. No lambda. No squad ILP rewrite. Diagnostic only.

Usage:
    python scripts/e034b_forced_swap.py
    python scripts/e034b_forced_swap.py --season 2023-24
"""
from __future__ import annotations

import argparse
import csv
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
from engine.optimize import solve_squad
from engine.packaging import apply_packaged_next_utility
from engine.project import project_all

OUT_ENT = Path("records") / "historical" / "e034b_forced_swap_entrants.csv"
OUT_GW = Path("records") / "historical" / "e034b_forced_swap_gw.csv"
OUT_TXT = Path("records") / "historical" / "e034b_forced_swap_summary.txt"
SEED = 7
OBJECTIVE = "next"
STRATEGY = "balanced"
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}


def _pts(act: dict, pid: int) -> float:
    return float(act.get(pid, {}).get("actual_points", 0) or 0)


def cap_points(sol, act: dict) -> float:
    total = sum(_pts(act, p.id) for p in sol.xi)
    total += _pts(act, sol.captain.id)
    return total


def analyze_season(season: str) -> tuple[list[dict], list[dict]]:
    ensure_vaastav((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E034b forced swap gate={gate} ===")
    ent_rows: list[dict] = []
    gw_rows: list[dict] = []

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

        try:
            sol_c = solve_squad(snap, v1, strategy=STRATEGY, objective=OBJECTIVE)
            sol_t = solve_squad(snap, packaged, strategy=STRATEGY, objective=OBJECTIVE)
        except RuntimeError:
            continue

        c_squad = {p.id for p in sol_c.players}
        t_squad = {p.id for p in sol_t.players}
        entered = sorted(t_squad - c_squad)
        if not entered:
            continue

        ctrl_cap = cap_points(sol_c, act)
        full_cap = cap_points(sol_t, act)
        delta_full = full_cap - ctrl_cap
        overlap_full = len(c_squad & t_squad)

        forces: list[float] = []
        cascades: list[float] = []

        for eid in entered:
            try:
                sol_f = solve_squad(
                    snap, packaged, strategy=STRATEGY, objective=OBJECTIVE,
                    must_include={eid},
                )
            except RuntimeError:
                continue

            f_squad = {p.id for p in sol_f.players}
            force_cap = cap_points(sol_f, act)
            delta_force = force_cap - ctrl_cap
            delta_cascade = delta_full - delta_force
            forces.append(delta_force)
            cascades.append(delta_cascade)

            left_ids = sorted(c_squad - f_squad)
            ent_rows.append({
                "season": season,
                "e024_gate": gate,
                "gw": gw,
                "entrant_id": eid,
                "entrant_name": next(p for p in sol_t.players if p.id == eid).web_name,
                "delta_force": round(delta_force, 4),
                "delta_full": round(delta_full, 4),
                "delta_cascade": round(delta_cascade, 4),
                "abs_cascade_gt_force": int(abs(delta_cascade) > abs(delta_force)),
                "ctrl_cap": round(ctrl_cap, 4),
                "force_cap": round(force_cap, 4),
                "full_cap": round(full_cap, 4),
                "overlap_forced_ctrl": len(c_squad & f_squad),
                "overlap_full_ctrl": overlap_full,
                "n_squad_diff_forced": len(c_squad ^ f_squad),
                "n_leavers_forced": len(left_ids),
                "leaver_ids": ";".join(str(x) for x in left_ids),
            })

        if forces:
            gw_rows.append({
                "season": season,
                "e024_gate": gate,
                "gw": gw,
                "n_entrants": len(forces),
                "delta_full": round(delta_full, 4),
                "mean_delta_force": round(statistics.mean(forces), 4),
                "mean_delta_cascade": round(statistics.mean(cascades), 4),
                "mean_abs_delta_force": round(statistics.mean(abs(x) for x in forces), 4),
                "mean_abs_delta_cascade": round(statistics.mean(abs(x) for x in cascades), 4),
                "cascade_gt_force_n": sum(int(abs(c) > abs(f)) for f, c in zip(forces, cascades)),
                "overlap_full_ctrl": overlap_full,
            })

    print(f"  entrant-rows={len(ent_rows)} gw-rows={len(gw_rows)}")
    return ent_rows, gw_rows


def summarize(ent_rows: list[dict], gw_rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E034b: forced-swap counterfactual (one entrant at a time)")
    lines.append("delta_force = cap(forced must_include E) - cap(ctrl)")
    lines.append("delta_cascade = delta_full - delta_force")
    lines.append("")

    for gate in ("FAIL", "PASS"):
        g_ent = [r for r in ent_rows if r["e024_gate"] == gate]
        g_gw = [r for r in gw_rows if r["e024_gate"] == gate]
        if len(g_ent) < 5:
            lines.append(f"=== {gate}: too few entrants ===")
            continue
        lines.append(f"=== {gate} entrants n={len(g_ent)} gws={len(g_gw)} ===")
        df = [float(r["delta_force"]) for r in g_ent]
        dc = [float(r["delta_cascade"]) for r in g_ent]
        lines.append(
            f"  entrant mean_delta_force={statistics.mean(df):.3f} "
            f"mean_delta_cascade={statistics.mean(dc):.3f}"
        )
        lines.append(
            f"  entrant mean_abs_force={statistics.mean(abs(x) for x in df):.3f} "
            f"mean_abs_cascade={statistics.mean(abs(x) for x in dc):.3f}"
        )
        cg = sum(int(r["abs_cascade_gt_force"]) for r in g_ent)
        lines.append(f"  |cascade|>|force|: {100.0 * cg / len(g_ent):.1f}% ({cg}/{len(g_ent)})")
        if g_gw:
            lines.append(
                f"  gw mean_delta_full={statistics.mean(float(r['delta_full']) for r in g_gw):.3f} "
                f"mean_mean_delta_force={statistics.mean(float(r['mean_delta_force']) for r in g_gw):.3f}"
            )
            lines.append(
                f"  gw mean_n_entrants={statistics.mean(int(r['n_entrants']) for r in g_gw):.2f} "
                f"mean_overlap_full_ctrl={statistics.mean(int(r['overlap_full_ctrl']) for r in g_gw):.1f}"
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
    print("[e034b] forced-swap counterfactual; balanced; no new objective")
    all_ent: list[dict] = []
    all_gw: list[dict] = []
    for s in seasons:
        ent, gw = analyze_season(s)
        all_ent.extend(ent)
        all_gw.extend(gw)

    ent_fields = [
        "season", "e024_gate", "gw", "entrant_id", "entrant_name",
        "delta_force", "delta_full", "delta_cascade", "abs_cascade_gt_force",
        "ctrl_cap", "force_cap", "full_cap",
        "overlap_forced_ctrl", "overlap_full_ctrl",
        "n_squad_diff_forced", "n_leavers_forced", "leaver_ids",
    ]
    gw_fields = [
        "season", "e024_gate", "gw", "n_entrants",
        "delta_full", "mean_delta_force", "mean_delta_cascade",
        "mean_abs_delta_force", "mean_abs_delta_cascade", "cascade_gt_force_n",
        "overlap_full_ctrl",
    ]
    OUT_ENT.parent.mkdir(parents=True, exist_ok=True)
    with OUT_ENT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ent_fields)
        w.writeheader()
        w.writerows(all_ent)
    print(f"Wrote {OUT_ENT} ({len(all_ent)} rows)")
    with OUT_GW.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=gw_fields)
        w.writeheader()
        w.writerows(all_gw)
    print(f"Wrote {OUT_GW} ({len(all_gw)} rows)")
    summary = summarize(all_ent, all_gw)
    OUT_TXT.write_text(summary, encoding="utf-8")
    print(f"Wrote {OUT_TXT}")


if __name__ == "__main__":
    main()
