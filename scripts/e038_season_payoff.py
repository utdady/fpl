"""E038 diagnostic: season payoff — rolling vs GW1-lock (Landing A vs B).

Pre-registered in docs/DECISION_CHARTER.md.

Discriminates whether FAIL-season damage is GW-structural (Landing A) or
amplified by rolling re-squadding (Landing B).

Arms (same frozen E024 stack: v2am_s, packaged rates_v2b vs v1, balanced, seed=7):
  rolling:   re-solve squad each GW; season_sum_delta_cap = sum(treat_cap - ctrl_cap)
  gw1_lock:  fix GW1 ctrl/treat 15; each GW re-solve XI+cap on as-of-T mu; season delta

Primary: sign and magnitude on FAIL seasons (2022-23, 2025-26); compare arms.

No transfers. No V_C. No optimizer change.

Usage:
    python scripts/e038_season_payoff.py
    python scripts/e038_season_payoff.py --season 2023-24
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
from engine.models import Player
from engine.optimize import pick_captains, solve_squad, solve_xi
from engine.packaging import apply_packaged_next_utility
from engine.project import project_all

OUT_SEASON = Path("records") / "historical" / "e038_season_payoff_season.csv"
OUT_GW = Path("records") / "historical" / "e038_season_payoff_gw.csv"
OUT_TXT = Path("records") / "historical" / "e038_season_payoff_summary.txt"
SEED = 7
STRATEGY = "balanced"
OBJECTIVE = "next"
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}


def _pts(act: dict, pid: int) -> float:
    return float(act.get(pid, {}).get("actual_points", 0) or 0)


def cap_from_xi(xi: list[Player], captain: Player, act: dict) -> float:
    return sum(_pts(act, p.id) for p in xi) + _pts(act, captain.id)


def gw_cap_roll(snap, act, v1, packaged) -> tuple[float, float] | None:
    try:
        sol_c = solve_squad(snap, v1, strategy=STRATEGY, objective=OBJECTIVE)
        sol_t = solve_squad(snap, packaged, strategy=STRATEGY, objective=OBJECTIVE)
    except RuntimeError:
        return None
    return cap_from_xi(sol_c.xi, sol_c.captain, act), cap_from_xi(sol_t.xi, sol_t.captain, act)


def gw_cap_lock(
    snap,
    act,
    squad_c: list[Player],
    squad_t: list[Player],
    by_c: dict,
    by_t: dict,
) -> tuple[float, float] | None:
    try:
        xi_c, _ = solve_xi(snap, squad_c, by_c)
        xi_t, _ = solve_xi(snap, squad_t, by_t)
        cap_c, _ = pick_captains(xi_c, by_c)
        cap_t, _ = pick_captains(xi_t, by_t)
    except RuntimeError:
        return None
    return cap_from_xi(xi_c, cap_c, act), cap_from_xi(xi_t, cap_t, act)


def project_pair(season: str, gw: int):
    snap = build_snapshot(season, as_of_gw=gw)
    act = gw_actuals(season, gw)
    if not act:
        return None
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
    return snap, act, v1, packaged, by_c, by_t


def analyze_season(season: str) -> tuple[dict, list[dict]]:
    ensure_vaastav((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E038 season payoff gate={gate} ===")

    gw_rows: list[dict] = []
    squad_c: list[Player] | None = None
    squad_t: list[Player] | None = None

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        pair = project_pair(season, gw)
        if pair is None:
            continue
        snap, act, v1, packaged, by_c, by_t = pair

        roll = gw_cap_roll(snap, act, v1, packaged)
        if roll is None:
            continue
        cap_c_roll, cap_t_roll = roll
        delta_roll = cap_t_roll - cap_c_roll

        if gw == 1:
            try:
                sol_c = solve_squad(snap, v1, strategy=STRATEGY, objective=OBJECTIVE)
                sol_t = solve_squad(snap, packaged, strategy=STRATEGY, objective=OBJECTIVE)
                squad_c = list(sol_c.players)
                squad_t = list(sol_t.players)
            except RuntimeError:
                squad_c = squad_t = None

        delta_lock = ""
        cap_c_lock = cap_t_lock = ""
        if squad_c is not None and squad_t is not None:
            lock = gw_cap_lock(snap, act, squad_c, squad_t, by_c, by_t)
            if lock is not None:
                cap_c_lock, cap_t_lock = lock
                delta_lock = cap_t_lock - cap_c_lock

        gw_rows.append({
            "season": season,
            "e024_gate": gate,
            "gw": gw,
            "cap_ctrl_roll": round(cap_c_roll, 4),
            "cap_treat_roll": round(cap_t_roll, 4),
            "delta_cap_roll": round(delta_roll, 4),
            "cap_ctrl_lock": round(cap_c_lock, 4) if cap_c_lock != "" else "",
            "cap_treat_lock": round(cap_t_lock, 4) if cap_t_lock != "" else "",
            "delta_cap_lock": round(delta_lock, 4) if delta_lock != "" else "",
        })

    rolling_sum = sum(float(r["delta_cap_roll"]) for r in gw_rows)
    lock_rows = [r for r in gw_rows if r["delta_cap_lock"] != ""]
    lock_sum = sum(float(r["delta_cap_lock"]) for r in lock_rows) if lock_rows else float("nan")
    ctrl_lock_total = sum(float(r["cap_ctrl_lock"]) for r in lock_rows) if lock_rows else float("nan")
    treat_lock_total = sum(float(r["cap_treat_lock"]) for r in lock_rows) if lock_rows else float("nan")

    season_row = {
        "season": season,
        "e024_gate": gate,
        "n_gw": len(gw_rows),
        "rolling_sum_delta_cap": round(rolling_sum, 4),
        "gw1_lock_sum_delta_cap": round(lock_sum, 4) if lock_sum == lock_sum else "",
        "gw1_lock_ctrl_total_cap": round(ctrl_lock_total, 4) if ctrl_lock_total == ctrl_lock_total else "",
        "gw1_lock_treat_total_cap": round(treat_lock_total, 4) if treat_lock_total == treat_lock_total else "",
        "rolling_mean_delta_cap": round(rolling_sum / len(gw_rows), 4) if gw_rows else "",
        "gw1_lock_mean_delta_cap": round(lock_sum / len(lock_rows), 4) if lock_rows else "",
    }
    print(
        f"  n_gw={len(gw_rows)} rolling_sum={rolling_sum:.1f} "
        f"gw1_lock_sum={lock_sum:.1f}" if lock_sum == lock_sum else f"  n_gw={len(gw_rows)}"
    )
    return season_row, gw_rows


def summarize(season_rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E038: season payoff rolling vs GW1-lock (Landing A vs B)")
    lines.append("rolling = re-solve squad each GW; gw1_lock = fix GW1 15, XI/cap each GW")
    lines.append("")

    for gate in ("FAIL", "PASS"):
        g = [r for r in season_rows if r["e024_gate"] == gate]
        if not g:
            continue
        roll = [float(r["rolling_sum_delta_cap"]) for r in g]
        lock = [float(r["gw1_lock_sum_delta_cap"]) for r in g if r["gw1_lock_sum_delta_cap"] != ""]
        lines.append(f"=== {gate} seasons n={len(g)} ===")
        lines.append(f"  rolling_sum_delta_cap:  {roll}  mean={statistics.mean(roll):.1f}")
        if lock:
            lines.append(f"  gw1_lock_sum_delta_cap: {lock}  mean={statistics.mean(lock):.1f}")
        for r in g:
            lines.append(
                f"  {r['season']}: roll={r['rolling_sum_delta_cap']} "
                f"lock={r['gw1_lock_sum_delta_cap']}"
            )
        lines.append("")

    lines.append("=== Branching guide ===")
    lines.append("  both roll and lock negative on FAIL -> Landing A (season-structural)")
    lines.append("  roll negative, lock neutral/positive on FAIL -> Landing B (re-squadding stress)")
    lines.append("")
    text = "\n".join(lines) + "\n"
    print(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e038] season payoff; rolling vs GW1-lock; no transfers")
    season_rows: list[dict] = []
    all_gw: list[dict] = []
    for s in seasons:
        srow, gw = analyze_season(s)
        season_rows.append(srow)
        all_gw.extend(gw)

    OUT_SEASON.parent.mkdir(parents=True, exist_ok=True)
    sfields = list(season_rows[0].keys()) if season_rows else []
    with OUT_SEASON.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sfields)
        w.writeheader()
        w.writerows(season_rows)
    print(f"Wrote {OUT_SEASON} ({len(season_rows)} rows)")

    gfields = list(all_gw[0].keys()) if all_gw else []
    with OUT_GW.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=gfields)
        w.writeheader()
        w.writerows(all_gw)
    print(f"Wrote {OUT_GW} ({len(all_gw)} rows)")

    summary = summarize(season_rows)
    OUT_TXT.write_text(summary, encoding="utf-8")
    print(f"Wrote {OUT_TXT}")


if __name__ == "__main__":
    main()
