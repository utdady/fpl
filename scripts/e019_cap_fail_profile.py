"""E019b diagnostic: Cap-FAIL vs Cap-PASS demoted leavers under v2c.

Question: among players ejected from the v2am_s XI after competition demotion,
do Cap-fail seasons (2022/23, 2024/25) remove high value-when-playing transitions
(false positives), while Cap-pass seasons remove low-value players?

Usage:
    python scripts/e019_cap_fail_profile.py
"""
from __future__ import annotations

import argparse
import csv
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from engine.harness import (
    PREV_SEASON,
    SUPPORTED_SEASONS,
    _id_code_map,
    build_snapshot,
    ensure_vaastav,
    gw_actuals,
    recent_minutes_by_element,
)
from engine.metrics import record_path
from engine.minutes_struct import HOT_RECENT_MIN, RECENT_WINDOW
from engine.minutes_v2c import (
    CAP_NCOMP_EQ1,
    CAP_NCOMP_GE2,
    club_transition_ids,
    competition_count,
    prior_minutes_at_club_by_code,
)
from engine.optimize import solve_squad
from engine.project import project_all

OUT = Path("records") / "historical" / "e019_cap_fail_profile.csv"
SEED = 7
CAP_FAIL = {"2022-23", "2024-25"}
CAP_PASS = {"2023-24", "2025-26"}


def demotion_label(n_comp: int, hot: bool, is_transition: bool, is_outfield: bool) -> str:
    if not is_transition or not is_outfield:
        return "none"
    if hot:
        return "hot_skip"
    if n_comp >= 2:
        return "cap_0.48"
    if n_comp == 1:
        return "cap_0.68"
    return "n_comp_0"


def analyze_season(season: str) -> list[dict]:
    ensure_vaastav((season,))
    gate = "FAIL" if season in CAP_FAIL else ("PASS" if season in CAP_PASS else "?")
    print(f"\n=== {season} E019b Cap-{gate} (v2am_s XI -> v2c XI) ===")

    prev = PREV_SEASON.get(season)
    prior_mins = prior_minutes_at_club_by_code(prev) if prev else {}
    id_code = _id_code_map(season)
    rows: list[dict] = []

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        print(f"  [{season}] GW{gw}")
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue

        apply_recent = gw > RECENT_WINDOW
        recent = (
            recent_minutes_by_element(season, gw, window=RECENT_WINDOW)
            if apply_recent
            else {}
        )
        transition = club_transition_ids(season, gw)
        team_names = {tid: t.name for tid, t in snap.teams.items()}
        groups: dict[tuple[int, str], list] = defaultdict(list)
        for p in snap.players:
            groups[(p.team_id, p.position)].append(p)

        ctrl = project_all(
            snap, horizon=1, strategy="balanced", seed=SEED,
            minutes_version="v2am_s", rates_version="v1",
        )
        treat = project_all(
            snap, horizon=1, strategy="balanced", seed=SEED,
            minutes_version="v2c", rates_version="v1",
        )
        by_c = {p.player.id: p for p in ctrl}
        by_t = {p.player.id: p for p in treat}

        try:
            sol_c = solve_squad(snap, ctrl, strategy="balanced", objective="next")
            sol_t = solve_squad(snap, treat, strategy="balanced", objective="next")
        except RuntimeError as e:
            print(f"    solver fail: {e}")
            continue

        c_ids = {p.id for p in sol_c.xi}
        t_ids = {p.id for p in sol_t.xi}

        for movement, pids in (("left", c_ids - t_ids), ("entered", t_ids - c_ids)):
            for pid in pids:
                pc, pt = by_c[pid], by_t[pid]
                pl = pc.player if movement == "left" else pt.player
                is_tr = pid in transition
                is_of = pl.position != "GKP"
                group = groups[(pl.team_id, pl.position)]
                n_comp = (
                    competition_count(
                        pl, group, team_names.get(pl.team_id, ""), id_code, prior_mins
                    )
                    if is_tr and is_of
                    else 0
                )
                r4 = recent.get(pid, 0)
                hot = apply_recent and r4 >= HOT_RECENT_MIN
                dem = demotion_label(n_comp, hot, is_tr, is_of)
                demoted = dem in {"cap_0.48", "cap_0.68"}
                mins = float(act.get(pid, {}).get("actual_minutes", 0) or 0)
                pts = float(act.get(pid, {}).get("actual_points", 0) or 0)
                rows.append({
                    "season": season,
                    "cap_gate": gate,
                    "gw": gw,
                    "movement": movement,
                    "player_id": pid,
                    "web_name": pl.web_name,
                    "position": pl.position,
                    "club_transition": int(is_tr),
                    "n_comp": n_comp,
                    "recent4": r4,
                    "demotion": dem,
                    "demoted": int(demoted),
                    "ctrl_p_start": round(pc.next_p_start, 4),
                    "treat_p_start": round(pt.next_p_start, 4),
                    "p_start_delta": round(pt.next_p_start - pc.next_p_start, 4),
                    "ctrl_mu": round(pc.next_mu, 4),
                    "treat_mu": round(pt.next_mu, 4),
                    "actual_minutes": mins,
                    "blank": int(mins == 0),
                    "actual_points": pts,
                })

    left = [r for r in rows if r["movement"] == "left"]
    dem_left = [r for r in left if r["demoted"]]
    print(
        f"  movers left={len(left)} demoted_left={len(dem_left)} "
        f"entered={sum(1 for r in rows if r['movement']=='entered')}"
    )
    return rows


def _mean(xs: list[float]) -> float:
    return statistics.mean(xs) if xs else float("nan")


def summarize(rows: list[dict]) -> None:
    print("\n=== demoted leavers: Cap-FAIL vs Cap-PASS ===")
    dem_left = [r for r in rows if r["movement"] == "left" and r["demoted"]]
    for gate in ("FAIL", "PASS"):
        sub = [r for r in dem_left if r["cap_gate"] == gate]
        n = len(sub)
        if not n:
            print(f"{gate}: n=0")
            continue
        blank = 100.0 * sum(r["blank"] for r in sub) / n
        played = [r for r in sub if r["actual_minutes"] > 0]
        played60 = [r for r in sub if r["actual_minutes"] >= 60]
        dem_counts = Counter(r["demotion"] for r in sub)
        print(
            f"{gate}: n={n} blank%={blank:.1f} "
            f"mean_pts_all={_mean([r['actual_points'] for r in sub]):.2f} "
            f"mean_pts|played>0 n={len(played)} pts={_mean([r['actual_points'] for r in played]):.2f} "
            f"mean_pts|60+ n={len(played60)} pts={_mean([r['actual_points'] for r in played60]):.2f} "
            f"mean_mins={_mean([r['actual_minutes'] for r in sub]):.0f} "
            f"demotion={dict(dem_counts)}"
        )

    print("\n=== all leavers (incl. non-demoted portfolio spill) ===")
    for gate in ("FAIL", "PASS"):
        sub = [r for r in rows if r["movement"] == "left" and r["cap_gate"] == gate]
        n = len(sub)
        if not n:
            continue
        dem_pct = 100.0 * sum(r["demoted"] for r in sub) / n
        blank = 100.0 * sum(r["blank"] for r in sub) / n
        played = [r for r in sub if r["actual_minutes"] > 0]
        print(
            f"{gate}: left_n={n} demoted%={dem_pct:.1f} blank%={blank:.1f} "
            f"mean_pts|played>0={_mean([r['actual_points'] for r in played]):.2f}"
        )

    print("\n=== entered (replacements) FAIL vs PASS ===")
    for gate in ("FAIL", "PASS"):
        sub = [r for r in rows if r["movement"] == "entered" and r["cap_gate"] == gate]
        n = len(sub)
        if not n:
            continue
        blank = 100.0 * sum(r["blank"] for r in sub) / n
        played = [r for r in sub if r["actual_minutes"] > 0]
        played60 = [r for r in sub if r["actual_minutes"] >= 60]
        print(
            f"{gate}: n={n} blank%={blank:.1f} "
            f"mean_pts|played>0={_mean([r['actual_points'] for r in played]):.2f} "
            f"mean_pts|60+={_mean([r['actual_points'] for r in played60]):.2f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="E019b Cap-fail demoted-leaver profile.")
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    all_rows: list[dict] = []
    for s in seasons:
        all_rows.extend(analyze_season(s))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = list(all_rows[0].keys()) if all_rows else []
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"\nWrote {OUT} ({len(all_rows)} rows)")
    summarize(all_rows)


if __name__ == "__main__":
    main()
