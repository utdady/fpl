"""E016b diagnostic: XI movers under rates_v1 vs rates_v2b (minutes frozen at v2am_s).

Usage:
    python scripts/e016_xi_movement.py
    python scripts/e016_xi_movement.py --season 2025-26

Control:  minutes=v2am_s + rates=v1
Treatment: minutes=v2am_s + rates=v2b
Same seed both arms.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

from engine.harness import SUPPORTED_SEASONS, build_snapshot, ensure_vaastav, gw_actuals
from engine.metrics import record_path
from engine.optimize import solve_squad
from engine.project import project_all
from engine.rates_v2b import build_rates_priors_for_snapshot

OUT = Path("records") / "historical" / "e016_xi_movement.csv"
SEED = 7


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
    print(f"\n=== {season} E016b XI movement (rates_v1 -> rates_v2b) ===")

    left_pos: Counter = Counter()
    entered_pos: Counter = Counter()
    left_ps: Counter = Counter()
    entered_ps: Counter = Counter()
    left_blank = entered_blank = 0
    left_n = entered_n = 0
    left_had_prior = entered_had_prior = 0
    left_mu_delta: list[float] = []
    entered_mu_delta: list[float] = []
    out_rows: list[dict] = []

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        print(f"  [{season}] GW{gw}")
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue

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
        left = c_ids - t_ids
        entered = t_ids - c_ids

        for pid in left:
            left_n += 1
            pc, pt = by_c[pid], by_t[pid]
            mins = float(act.get(pid, {}).get("actual_minutes", 0) or 0)
            blank = mins == 0
            left_blank += int(blank)
            had = int(pid in priors)
            left_had_prior += had
            dmu = pt.next_mu - pc.next_mu
            left_mu_delta.append(dmu)
            left_pos[pc.player.position] += 1
            left_ps[p_bucket(pc.next_p_start)] += 1
            out_rows.append({
                "season": season,
                "gw": gw,
                "movement": "left",
                "player_id": pid,
                "web_name": pc.player.web_name,
                "position": pc.player.position,
                "ctrl_p_start": round(pc.next_p_start, 4),
                "ctrl_mu": round(pc.next_mu, 4),
                "treat_mu": round(pt.next_mu, 4),
                "mu_delta": round(dmu, 4),
                "had_club_prior": had,
                "actual_minutes": mins,
                "blank": int(blank),
                "actual_points": act.get(pid, {}).get("actual_points", ""),
            })

        for pid in entered:
            entered_n += 1
            pc, pt = by_c[pid], by_t[pid]
            mins = float(act.get(pid, {}).get("actual_minutes", 0) or 0)
            blank = mins == 0
            entered_blank += int(blank)
            had = int(pid in priors)
            entered_had_prior += had
            dmu = pt.next_mu - pc.next_mu
            entered_mu_delta.append(dmu)
            entered_pos[pt.player.position] += 1
            entered_ps[p_bucket(pt.next_p_start)] += 1
            out_rows.append({
                "season": season,
                "gw": gw,
                "movement": "entered",
                "player_id": pid,
                "web_name": pt.player.web_name,
                "position": pt.player.position,
                "ctrl_p_start": round(pc.next_p_start, 4),
                "ctrl_mu": round(pc.next_mu, 4),
                "treat_mu": round(pt.next_mu, 4),
                "mu_delta": round(dmu, 4),
                "had_club_prior": had,
                "actual_minutes": mins,
                "blank": int(blank),
                "actual_points": act.get(pid, {}).get("actual_points", ""),
            })

    def mean(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else float("nan")

    print(f"  left={left_n} entered={entered_n}")
    print(
        f"  blank% left={100.0 * left_blank / left_n if left_n else float('nan'):.1f} "
        f"entered={100.0 * entered_blank / entered_n if entered_n else float('nan'):.1f}"
    )
    print(
        f"  had_club_prior% left={100.0 * left_had_prior / left_n if left_n else float('nan'):.1f} "
        f"entered={100.0 * entered_had_prior / entered_n if entered_n else float('nan'):.1f}"
    )
    print(f"  mean mu_delta left={mean(left_mu_delta):.3f} entered={mean(entered_mu_delta):.3f}")
    print(f"  left pos: {dict(left_pos)}")
    print(f"  entered pos: {dict(entered_pos)}")
    print(f"  left p_start: {dict(left_ps)}")
    print(f"  entered p_start: {dict(entered_ps)}")
    return out_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e016b] XI movement: rates_v1 XI vs rates_v2b XI under frozen v2am_s")
    all_rows: list[dict] = []
    for s in seasons:
        all_rows.extend(analyze_season(s))

    fields = [
        "season", "gw", "movement", "player_id", "web_name", "position",
        "ctrl_p_start", "ctrl_mu", "treat_mu", "mu_delta", "had_club_prior",
        "actual_minutes", "blank", "actual_points",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"\nWrote {OUT} ({len(all_rows)} rows)")

    # Season-level blank summary
    by = defaultdict(lambda: {"left": [0, 0], "entered": [0, 0]})
    for r in all_rows:
        key = r["movement"]
        by[r["season"]][key][0] += 1
        by[r["season"]][key][1] += int(r["blank"])
    print("\n=== blank% among movers ===")
    for season in seasons:
        L, E = by[season]["left"], by[season]["entered"]
        lb = 100.0 * L[1] / L[0] if L[0] else float("nan")
        eb = 100.0 * E[1] / E[0] if E[0] else float("nan")
        print(f"  {season}: left blank {lb:.1f}% (n={L[0]}) | entered blank {eb:.1f}% (n={E[0]})")


if __name__ == "__main__":
    main()
