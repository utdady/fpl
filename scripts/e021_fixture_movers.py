"""E021b diagnostic: XI movers under fixtures_v1 vs fixtures_v2d.

Control:  minutes=v2am_s + rates=v1 + fixtures=v1
Treatment: minutes=v2am_s + rates=v1 + fixtures=v2d
Same seed both arms.

Because E021 failed Cap/XI0 on all four seasons, there is no FAIL-vs-PASS
season split. Instead compare (1) left vs entered blank%, (2) high-μΔ vs
low-μΔ entrants, (3) cold recent4, (4) prior-strength vs league-avg teams.

Usage:
    python scripts/e021_fixture_movers.py
    python scripts/e021_fixture_movers.py --season 2025-26
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.fixtures_v2d import _norm_team, strengths_for_season
from engine.harness import (
    SUPPORTED_SEASONS,
    build_snapshot,
    ensure_vaastav,
    gw_actuals,
    recent_minutes_by_element,
)
from engine.metrics import record_path
from engine.obs import new_club_ids
from engine.optimize import solve_squad
from engine.project import project_all

OUT = Path("records") / "historical" / "e021_fixture_movers.csv"
SEED = 7
RECENT_WINDOW = 4


def p_bucket(p: float) -> str:
    if p >= 0.90:
        return "0.90+"
    if p >= 0.80:
        return "0.80-0.90"
    if p >= 0.70:
        return "0.70-0.80"
    if p >= 0.60:
        return "0.60-0.70"
    if p >= 0.50:
        return "0.50-0.60"
    return "<0.50"


def analyze_season(season: str) -> list[dict]:
    ensure_vaastav((season,))
    print(f"\n=== {season} E021b XI movement (fixtures_v1 -> fixtures_v2d) ===")
    new_ids = new_club_ids(season)
    strengths = strengths_for_season(season)
    rows: list[dict] = []

    left_pos: Counter = Counter()
    entered_pos: Counter = Counter()
    left_ps: Counter = Counter()
    entered_ps: Counter = Counter()
    left_blank = entered_blank = 0
    left_n = entered_n = 0
    left_had_str = entered_had_str = 0
    left_mu: list[float] = []
    entered_mu: list[float] = []

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        print(f"  [{season}] GW{gw}")
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue

        recent = recent_minutes_by_element(season, gw, window=RECENT_WINDOW)

        ctrl = project_all(
            snap, horizon=1, strategy="balanced", seed=SEED,
            minutes_version="v2am_s", rates_version="v1", fixtures_version="v1",
        )
        treat = project_all(
            snap, horizon=1, strategy="balanced", seed=SEED,
            minutes_version="v2am_s", rates_version="v1", fixtures_version="v2d",
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
                pl = pt.player if movement == "entered" else pc.player
                mins = float(act.get(pid, {}).get("actual_minutes", 0) or 0)
                blank = int(mins == 0)
                dmu = pt.next_mu - pc.next_mu
                team_name = _norm_team(snap.team(pl.team_id).name)
                had_str = int(team_name in strengths)
                r4 = recent.get(pid, 0)
                row = {
                    "season": season,
                    "gw": gw,
                    "movement": movement,
                    "player_id": pid,
                    "web_name": pl.web_name,
                    "position": pl.position,
                    "team": snap.team(pl.team_id).name,
                    "season_minutes": pl.minutes,
                    "recent4_minutes": r4,
                    "ctrl_p_start": round(pc.next_p_start, 4),
                    "ctrl_mu": round(pc.next_mu, 4),
                    "treat_mu": round(pt.next_mu, 4),
                    "mu_delta": round(dmu, 4),
                    "had_prior_strength": had_str,
                    "new_club": int(pid in new_ids),
                    "actual_minutes": mins,
                    "blank": blank,
                    "actual_points": act.get(pid, {}).get("actual_points", ""),
                }
                rows.append(row)

                if movement == "left":
                    left_n += 1
                    left_blank += blank
                    left_had_str += had_str
                    left_mu.append(dmu)
                    left_pos[pl.position] += 1
                    left_ps[p_bucket(pc.next_p_start)] += 1
                else:
                    entered_n += 1
                    entered_blank += blank
                    entered_had_str += had_str
                    entered_mu.append(dmu)
                    entered_pos[pl.position] += 1
                    entered_ps[p_bucket(pt.next_p_start)] += 1

    def mean(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else float("nan")

    print(f"  left={left_n} entered={entered_n}")
    print(
        f"  blank% left={100.0 * left_blank / left_n if left_n else float('nan'):.1f} "
        f"entered={100.0 * entered_blank / entered_n if entered_n else float('nan'):.1f}"
    )
    print(
        f"  had_prior_strength% left={100.0 * left_had_str / left_n if left_n else float('nan'):.1f} "
        f"entered={100.0 * entered_had_str / entered_n if entered_n else float('nan'):.1f}"
    )
    print(f"  mean mu_delta left={mean(left_mu):.3f} entered={mean(entered_mu):.3f}")
    # (ASCII-only prints: Windows console may be cp1252)
    print(f"  left pos: {dict(left_pos)}")
    print(f"  entered pos: {dict(entered_pos)}")
    print(f"  left p_start: {dict(left_ps)}")
    print(f"  entered p_start: {dict(entered_ps)}")
    return rows


def summarize(rows: list[dict], seasons: tuple[str, ...]) -> None:
    print("\n=== blank% among movers (per season) ===")
    by = defaultdict(lambda: {"left": [0, 0], "entered": [0, 0]})
    for r in rows:
        key = r["movement"]
        by[r["season"]][key][0] += 1
        by[r["season"]][key][1] += int(r["blank"])
    for season in seasons:
        L, E = by[season]["left"], by[season]["entered"]
        lb = 100.0 * L[1] / L[0] if L[0] else float("nan")
        eb = 100.0 * E[1] / E[0] if E[0] else float("nan")
        print(f"  {season}: left blank {lb:.1f}% (n={L[0]}) | entered blank {eb:.1f}% (n={E[0]})")

    entered = [r for r in rows if r["movement"] == "entered"]
    left = [r for r in rows if r["movement"] == "left"]
    print("\n=== overall left vs entered ===")

    def block(label: str, subset: list[dict]) -> None:
        n = len(subset)
        if not n:
            print(f"  {label}: n=0")
            return
        blank = 100.0 * sum(r["blank"] for r in subset) / n
        had = 100.0 * sum(r["had_prior_strength"] for r in subset) / n
        newc = 100.0 * sum(r["new_club"] for r in subset) / n
        cold = 100.0 * sum(1 for r in subset if r["recent4_minutes"] < 90) / n
        r4 = statistics.mean(r["recent4_minutes"] for r in subset)
        dmu = statistics.mean(r["mu_delta"] for r in subset)
        pos = defaultdict(int)
        for r in subset:
            pos[r["position"]] += 1
        print(
            f"  {label}: n={n} blank%={blank:.1f} prior_str%={had:.1f} new_club%={newc:.1f} "
            f"recent4<90%={cold:.1f} mean_recent4={r4:.0f} mean_muD={dmu:.3f} pos={dict(pos)}"
        )

    block("left", left)
    block("entered", entered)

    # Lift tails among entrants (terciles of mu_delta)
    print("\n=== entered blank% by mu_delta tercile ===")
    if entered:
        sorted_e = sorted(entered, key=lambda r: r["mu_delta"])
        n = len(sorted_e)
        t1, t2 = n // 3, 2 * n // 3
        for label, subset in (
            ("low muD", sorted_e[:t1]),
            ("mid muD", sorted_e[t1:t2]),
            ("high muD", sorted_e[t2:]),
        ):
            nn = len(subset)
            b = 100.0 * sum(r["blank"] for r in subset) / nn if nn else float("nan")
            dmu = statistics.mean(r["mu_delta"] for r in subset) if nn else float("nan")
            print(f"  {label:8} n={nn:4} blank%={b:.1f} mean_muD={dmu:.3f}")

    print("\n=== entered blank% by recent4 / prior_strength ===")
    for label, pred in (
        ("prior_str+recent4<90", lambda r: r["had_prior_strength"] and r["recent4_minutes"] < 90),
        ("prior_str+recent4>=90", lambda r: r["had_prior_strength"] and r["recent4_minutes"] >= 90),
        ("league_avg_team", lambda r: not r["had_prior_strength"]),
        ("new_club", lambda r: r["new_club"]),
        ("estab", lambda r: not r["new_club"]),
        ("muD>=0.5", lambda r: r["mu_delta"] >= 0.5),
        ("muD<0.5", lambda r: r["mu_delta"] < 0.5),
        ("muD>=1.0", lambda r: r["mu_delta"] >= 1.0),
        ("muD<0 (demoted mu)", lambda r: r["mu_delta"] < 0),
    ):
        g = [r for r in entered if pred(r)]
        n = len(g)
        if not n:
            print(f"  {label:24} n=0")
            continue
        b = 100.0 * sum(r["blank"] for r in g) / n
        dmu = statistics.mean(r["mu_delta"] for r in g)
        print(f"  {label:24} n={n:4} blank%={b:.1f} mean_muD={dmu:.3f}")

    # Among entered who played 60+: is mu_delta still positive? (rates E018s signature)
    played = [r for r in entered if r["actual_minutes"] >= 60]
    blanks = [r for r in entered if r["blank"]]
    print("\n=== entered mu_delta among played>=60 vs blanks ===")
    if played:
        print(f"  played>=60 n={len(played)} mean_muD={statistics.mean(r['mu_delta'] for r in played):.3f}")
    if blanks:
        print(f"  blanks     n={len(blanks)} mean_muD={statistics.mean(r['mu_delta'] for r in blanks):.3f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e021b] XI movers: fixtures_v1 vs fixtures_v2d under v2am_s + rates=v1")
    all_rows: list[dict] = []
    for s in seasons:
        all_rows.extend(analyze_season(s))

    fields = [
        "season", "gw", "movement", "player_id", "web_name", "position", "team",
        "season_minutes", "recent4_minutes", "ctrl_p_start", "ctrl_mu", "treat_mu",
        "mu_delta", "had_prior_strength", "new_club", "actual_minutes", "blank",
        "actual_points",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"\nWrote {OUT} ({len(all_rows)} rows)")
    summarize(all_rows, seasons)


if __name__ == "__main__":
    main()
