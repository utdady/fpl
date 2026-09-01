"""E029 diagnostic: treatment-lift outcome profile on actual ctrl->treat swaps.

Unit: same-position (entrant, leaver) pairs from control vs packaged-rates XI diff.
Primary filter: both played >=60 minutes.
Classify: good (dpts>0), bad (dpts<0), tie excluded from good/bad rates.

Inspect pre-decision fields separating good vs bad promotions.
Treatment source: packaged rates_v2b (E024 stack). No mechanism. No q(Δμ).

Usage:
    python scripts/e029_treatment_lift_profile.py
    python scripts/e029_treatment_lift_profile.py --season 2023-24
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

OUT = Path("records") / "historical" / "e029_treatment_lift_pairs.csv"
OUT_TXT = Path("records") / "historical" / "e029_treatment_lift_summary.txt"
SEED = 7
STRATEGY = "balanced"
NEAR = 0.25
MID = 0.75
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}
TREATMENT_SOURCE = "rates_v2b_packaged"


def gap_bucket(abs_margin: float) -> str:
    if abs_margin < NEAR:
        return "near"
    if abs_margin < MID:
        return "mid"
    return "large"


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


def outcome_label(dpts: float, both60: bool) -> str:
    if not both60:
        return "not_both60"
    if dpts > 0:
        return "good"
    if dpts < 0:
        return "bad"
    return "tie"


def build_row(
    *,
    season: str,
    gw: int,
    enter_id: int,
    left_id: int,
    by_c: dict[int, PlayerProjection],
    by_t: dict[int, PlayerProjection],
    recent: dict[int, int],
    act: dict,
) -> dict:
    pc_e, pc_l = by_c[enter_id], by_c[left_id]
    pt_e = by_t[enter_id]
    pl_e = pc_e.player
    ctrl_margin = pc_e.next_mu - pc_l.next_mu
    treat_lift = pt_e.next_mu - pc_e.next_mu
    e_mins = float(act.get(enter_id, {}).get("actual_minutes", 0) or 0)
    l_mins = float(act.get(left_id, {}).get("actual_minutes", 0) or 0)
    e_pts = float(act.get(enter_id, {}).get("actual_points", 0) or 0)
    l_pts = float(act.get(left_id, {}).get("actual_points", 0) or 0)
    dpts = e_pts - l_pts
    both60 = int(e_mins >= 60 and l_mins >= 60)
    outcome = outcome_label(dpts, bool(both60))
    e024_gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    r4 = recent.get(enter_id, 0)
    return {
        "season": season,
        "e024_gate": e024_gate,
        "gw": gw,
        "treatment_source": TREATMENT_SOURCE,
        "enter_id": enter_id,
        "enter_name": pl_e.web_name,
        "enter_pos": pl_e.position,
        "left_id": left_id,
        "left_name": pc_l.player.web_name,
        "left_pos": pc_l.player.position,
        "ctrl_margin": round(ctrl_margin, 4),
        "abs_ctrl_margin": round(abs(ctrl_margin), 4),
        "gap_bucket": gap_bucket(abs(ctrl_margin)),
        "treat_lift": round(treat_lift, 4),
        "ctrl_mu_enter": round(pc_e.next_mu, 4),
        "ctrl_mu_left": round(pc_l.next_mu, 4),
        "treat_mu_enter": round(pt_e.next_mu, 4),
        "enter_sigma": round(pc_e.next_sigma, 4),
        "enter_p10": round(pc_e.next_p_10, 4),
        "enter_p_start": round(pc_e.next_p_start, 4),
        "enter_price": pl_e.now_cost,
        "enter_recent4": r4,
        "enter_mins": e_mins,
        "left_mins": l_mins,
        "enter_pts": e_pts,
        "left_pts": l_pts,
        "dpts": round(dpts, 4),
        "both60": both60,
        "outcome": outcome,
    }


def analyze_season(season: str) -> list[dict]:
    ensure_vaastav((season,))
    print(f"\n=== {season} E029 treatment-lift pairs ===")
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

        try:
            sol_c = solve_squad(snap, v1, strategy=STRATEGY, objective="next")
            sol_t = solve_squad(snap, packaged, strategy=STRATEGY, objective="next")
        except RuntimeError as e:
            print(f"    solver fail: {e}")
            continue

        c_xi = {p.id for p in sol_c.xi}
        t_xi = {p.id for p in sol_t.xi}
        for eid, lid in same_position_pairs(t_xi - c_xi, c_xi - t_xi, by_c):
            rows.append(
                build_row(
                    season=season,
                    gw=gw,
                    enter_id=eid,
                    left_id=lid,
                    by_c=by_c,
                    by_t=by_t,
                    recent=recent,
                    act=act,
                )
            )

    both60 = [r for r in rows if r["both60"]]
    good = sum(1 for r in both60 if r["outcome"] == "good")
    print(f"  pairs={len(rows)} both60={len(both60)} good={good} bad={len(both60)-good}")
    return rows


def _mean_field(subset: list[dict], field: str) -> float:
    vals = [r[field] for r in subset]
    return statistics.mean(vals) if vals else float("nan")


def summarize(rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E029: treatment-lift outcome profile (ctrl->packaged rates)")
    lines.append(f"Treatment source: {TREATMENT_SOURCE}")
    lines.append("Primary: both>=60; good=dpts>0, bad=dpts<0, ties excluded from rates")
    lines.append("")

    primary = [r for r in rows if r["both60"] and r["outcome"] in ("good", "bad")]

    def profile(label: str, subset: list[dict]) -> None:
        n = len(subset)
        if not n:
            lines.append(f"{label}: n=0")
            return
        good = [r for r in subset if r["outcome"] == "good"]
        bad = [r for r in subset if r["outcome"] == "bad"]
        ng, nb = len(good), len(bad)
        good_pct = 100.0 * ng / n
        lines.append(
            f"{label}: n={n} good={ng} ({good_pct:.1f}%) bad={nb} "
            f"mean_lift good={_mean_field(good, 'treat_lift'):.3f} "
            f"bad={_mean_field(bad, 'treat_lift'):.3f} "
            f"mean_sigma good={_mean_field(good, 'enter_sigma'):.3f} "
            f"bad={_mean_field(bad, 'enter_sigma'):.3f} "
            f"mean_p_start good={_mean_field(good, 'enter_p_start'):.3f} "
            f"bad={_mean_field(bad, 'enter_p_start'):.3f} "
            f"mean_p10 good={_mean_field(good, 'enter_p10'):.3f} "
            f"bad={_mean_field(bad, 'enter_p10'):.3f} "
            f"mean_recent4 good={_mean_field(good, 'enter_recent4'):.1f} "
            f"bad={_mean_field(bad, 'enter_recent4'):.1f}"
        )

    for gate in ("FAIL", "PASS"):
        g = [r for r in primary if r["e024_gate"] == gate]
        profile(f"=== {gate} all ===", g)
        for b in ("near", "mid", "large"):
            profile(f"  {b}", [r for r in g if r["gap_bucket"] == b])
        for pos in ("GKP", "DEF", "MID", "FWD"):
            profile(f"  {pos}", [r for r in g if r["enter_pos"] == pos])
        # lift tails
        for thresh, op in ((0.5, ">="), (1.0, ">=")):
            hi = [r for r in g if r["treat_lift"] >= thresh]
            profile(f"  lift>={thresh}", hi)
        lines.append("")

    text = "\n".join(lines) + "\n"
    print(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e029] treatment-lift outcome profile; diagnostic only; no q(dmu)")
    all_rows: list[dict] = []
    for s in seasons:
        all_rows.extend(analyze_season(s))

    fields = [
        "season", "e024_gate", "gw", "treatment_source",
        "enter_id", "enter_name", "enter_pos", "left_id", "left_name", "left_pos",
        "ctrl_margin", "abs_ctrl_margin", "gap_bucket", "treat_lift",
        "ctrl_mu_enter", "ctrl_mu_left", "treat_mu_enter",
        "enter_sigma", "enter_p10", "enter_p_start", "enter_price", "enter_recent4",
        "enter_mins", "left_mins", "enter_pts", "left_pts", "dpts", "both60", "outcome",
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
