"""E017b diagnostic: FAIL vs PASS season profiles of rates_v2b XI entrants.

Under frozen minutes=v2am_s, compare rates=v1 XI vs rates=v2b XI.
Ask whether FAIL-season entrants (2022-23, 2025-26) share identifiable
traits that PASS-season entrants (2023-24, 2024-25) lack.

Usage:
    python scripts/e017_entrant_profile.py
"""
from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

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
from engine.rates_v2b import build_rates_priors_for_snapshot

OUT = Path("records") / "historical" / "e017_entrant_profile.csv"
SEED = 7
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}
RECENT_WINDOW = 4


def analyze_season(season: str) -> list[dict]:
    ensure_vaastav((season,))
    print(f"\n=== {season} E017b entrant profile (rates_v1 -> rates_v2b) ===")
    new_ids = new_club_ids(season)
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
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
        priors = build_rates_priors_for_snapshot(season, snap)

        ctrl = project_all(
            snap, horizon=1, strategy="balanced", seed=SEED,
            minutes_version="v2am_s", rates_version="v1",
        )
        treat = project_all(
            snap, horizon=1, strategy="balanced", seed=SEED,
            minutes_version="v2am_s", rates_version="v2b",
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
                rows.append({
                    "season": season,
                    "e016_gate": gate,
                    "gw": gw,
                    "movement": movement,
                    "player_id": pid,
                    "web_name": pl.web_name,
                    "position": pl.position,
                    "season_minutes": pl.minutes,
                    "recent4_minutes": recent.get(pid, 0),
                    "p_start": round(pc.next_p_start, 4),
                    "ctrl_mu": round(pc.next_mu, 4),
                    "treat_mu": round(pt.next_mu, 4),
                    "mu_delta": round(pt.next_mu - pc.next_mu, 4),
                    "had_club_prior": int(pid in priors),
                    "new_club": int(pid in new_ids),
                    "actual_minutes": mins,
                    "blank": blank,
                    "actual_points": act.get(pid, {}).get("actual_points", ""),
                })

    entered = [r for r in rows if r["movement"] == "entered"]
    n = len(entered)
    if n:
        blank = 100.0 * sum(r["blank"] for r in entered) / n
        prior = 100.0 * sum(r["had_club_prior"] for r in entered) / n
        newc = 100.0 * sum(r["new_club"] for r in entered) / n
        r4 = statistics.mean(r["recent4_minutes"] for r in entered)
        sm = statistics.mean(r["season_minutes"] for r in entered)
        dmu = statistics.mean(r["mu_delta"] for r in entered)
        print(
            f"  entered n={n} blank%={blank:.1f} prior%={prior:.1f} new_club%={newc:.1f} "
            f"mean_recent4={r4:.0f} mean_season_mins={sm:.0f} mean_μΔ={dmu:.3f}"
        )
    return rows


def summarize(rows: list[dict]) -> None:
    print("\n=== E017b FAIL vs PASS — entered players only ===")

    def block(label: str, subset: list[dict]) -> None:
        n = len(subset)
        if not n:
            print(f"  {label}: n=0")
            return
        blank = 100.0 * sum(r["blank"] for r in subset) / n
        prior = 100.0 * sum(r["had_club_prior"] for r in subset) / n
        newc = 100.0 * sum(r["new_club"] for r in subset) / n
        cold = 100.0 * sum(1 for r in subset if r["recent4_minutes"] < 90) / n
        thin = 100.0 * sum(1 for r in subset if r["season_minutes"] < 450) / n
        r4 = statistics.mean(r["recent4_minutes"] for r in subset)
        sm = statistics.mean(r["season_minutes"] for r in subset)
        dmu = statistics.mean(r["mu_delta"] for r in subset)
        pos = defaultdict(int)
        for r in subset:
            pos[r["position"]] += 1
        print(
            f"  {label}: n={n} blank%={blank:.1f} prior%={prior:.1f} new_club%={newc:.1f} "
            f"recent4<90%={cold:.1f} season_mins<450%={thin:.1f} "
            f"mean_recent4={r4:.0f} mean_season_mins={sm:.0f} mean_μΔ={dmu:.3f} pos={dict(pos)}"
        )

    fail_e = [r for r in rows if r["movement"] == "entered" and r["season"] in FAIL_SEASONS]
    pass_e = [r for r in rows if r["movement"] == "entered" and r["season"] in PASS_SEASONS]
    block("FAIL entered", fail_e)
    block("PASS entered", pass_e)

    # Cross tabs that matter for a form gate
    print("\n=== entered blank% by recent4 / prior (FAIL vs PASS) ===")
    for gate, subset in (("FAIL", fail_e), ("PASS", pass_e)):
        for label, pred in (
            ("prior+recent4<90", lambda r: r["had_club_prior"] and r["recent4_minutes"] < 90),
            ("prior+recent4>=90", lambda r: r["had_club_prior"] and r["recent4_minutes"] >= 90),
            ("prior+season<450", lambda r: r["had_club_prior"] and r["season_minutes"] < 450),
            ("prior+season>=450", lambda r: r["had_club_prior"] and r["season_minutes"] >= 450),
            ("new_club+prior", lambda r: r["new_club"] and r["had_club_prior"]),
            ("estab+prior", lambda r: (not r["new_club"]) and r["had_club_prior"]),
        ):
            g = [r for r in subset if pred(r)]
            n = len(g)
            b = 100.0 * sum(r["blank"] for r in g) / n if n else float("nan")
            print(f"  {gate:4} {label:22} n={n:3} blank%={b:.1f}" if n else f"  {gate:4} {label:22} n=0")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e017b] Entrant profiles: rates_v1 vs rates_v2b under v2am_s (max contrast)")
    all_rows: list[dict] = []
    for s in seasons:
        all_rows.extend(analyze_season(s))

    fields = [
        "season", "e016_gate", "gw", "movement", "player_id", "web_name", "position",
        "season_minutes", "recent4_minutes", "p_start", "ctrl_mu", "treat_mu", "mu_delta",
        "had_club_prior", "new_club", "actual_minutes", "blank", "actual_points",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"\nWrote {OUT} ({len(all_rows)} rows)")
    summarize(all_rows)


if __name__ == "__main__":
    main()
