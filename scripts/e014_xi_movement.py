"""E014 diagnostic: V1 vs V2A-M XI membership by bucket/role/blank outcome."""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from engine.harness import SUPPORTED_SEASONS, build_snapshot, ensure_vaastav, gw_actuals
from engine.minutes_v2am import bucket_name, fit_loso_map
from engine.metrics import record_path, safe_float
from engine.optimize import solve_squad
from engine.project import project_all

OUT = Path("records") / "historical" / "e014_xi_movement.csv"


def v1_xi_by_gw(season: str) -> dict[int, list[int]]:
    path = Path("records") / "historical" / season / "decision_decomp.csv"
    by: dict[int, list[int]] = {}
    if not path.exists():
        return by
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("in_v1_xi") != "1":
                continue
            by.setdefault(int(r["gw"]), []).append(int(r["player_id"]))
    return by


def v1_row_index(season: str) -> dict[tuple[int, int], dict]:
    """(gw, player_id) -> frozen V1 row."""
    idx = {}
    for gw in range(1, 39):
        path = record_path(gw, season=season)
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                idx[(gw, int(r["player_id"]))] = r
    return idx


def analyze_season(season: str) -> list[dict]:
    ensure_vaastav((season,))
    pmap = fit_loso_map(season, SUPPORTED_SEASONS)
    v1xi = v1_xi_by_gw(season)
    rows_idx = v1_row_index(season)
    out_rows = []

    left_bucket = Counter()
    entered_bucket = Counter()
    left_pos = Counter()
    entered_pos = Counter()
    left_blank = Counter()  # True/False
    entered_blank = Counter()
    left_played = Counter()
    entered_played = Counter()

    n_left = n_entered = 0
    left_blank_n = entered_blank_n = 0

    for gw in range(1, 39):
        if gw not in v1xi:
            continue
        print(f"  [{season}] GW{gw}")
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue
        projs = project_all(
            snap, horizon=1, strategy="balanced",
            minutes_version="v2am", p_start_map=pmap,
        )
        try:
            sol = solve_squad(snap, projs, strategy="balanced", objective="next")
        except RuntimeError:
            continue
        v2_ids = {p.id for p in sol.xi}
        v1_ids = set(v1xi[gw])
        left = v1_ids - v2_ids
        entered = v2_ids - v1_ids
        for pid in left:
            n_left += 1
            r = rows_idx.get((gw, pid), {})
            ps = safe_float(r.get("p_start")) or 0.0
            pos = r.get("position") or "?"
            mins = float(act.get(pid, {}).get("actual_minutes", 0) or 0)
            blank = mins == 0
            left_bucket[bucket_name(ps)] += 1
            left_pos[pos] += 1
            left_blank[blank] += 1
            left_blank_n += int(blank)
            left_played[mins >= 60] += 1
            out_rows.append({
                "season": season, "gw": gw, "movement": "left",
                "player_id": pid, "web_name": r.get("web_name", ""),
                "position": pos, "v1_p_start": round(ps, 4),
                "v1_bucket": bucket_name(ps),
                "actual_minutes": mins,
                "blank": int(blank),
                "actual_points": act.get(pid, {}).get("actual_points", ""),
            })
        for pid in entered:
            n_entered += 1
            # get name/pos from snapshot
            pl = next((p for p in snap.players if p.id == pid), None)
            r = rows_idx.get((gw, pid), {})
            ps = safe_float(r.get("p_start"))
            if ps is None and pl is not None:
                # use v2 next_p_start from proj
                proj = next((x for x in projs if x.player.id == pid), None)
                ps = proj.next_p_start if proj else 0.0
                pos = pl.position
                name = pl.web_name
            else:
                pos = r.get("position") or (pl.position if pl else "?")
                name = r.get("web_name") or (pl.web_name if pl else "")
                ps = ps or 0.0
            mins = float(act.get(pid, {}).get("actual_minutes", 0) or 0)
            blank = mins == 0
            # bucket by V1 p_start if available else v2
            bkey = bucket_name(float(safe_float(r.get("p_start")) or ps))
            entered_bucket[bkey] += 1
            entered_pos[pos] += 1
            entered_blank[blank] += 1
            entered_blank_n += int(blank)
            entered_played[mins >= 60] += 1
            out_rows.append({
                "season": season, "gw": gw, "movement": "entered",
                "player_id": pid, "web_name": name,
                "position": pos,
                "v1_p_start": round(float(safe_float(r.get("p_start")) or ps), 4),
                "v1_bucket": bkey,
                "actual_minutes": mins,
                "blank": int(blank),
                "actual_points": act.get(pid, {}).get("actual_points", ""),
            })

    print(f"\n=== {season} XI movement summary ===")
    print(f"  left={n_left}  entered={n_entered}")
    print(f"  left blank rate:    {100*left_blank_n/max(n_left,1):.1f}% ({left_blank_n}/{n_left})")
    print(f"  entered blank rate: {100*entered_blank_n/max(n_entered,1):.1f}% ({entered_blank_n}/{n_entered})")
    print(f"  left by bucket:    {dict(left_bucket)}")
    print(f"  entered by bucket: {dict(entered_bucket)}")
    print(f"  left by pos:       {dict(left_pos)}")
    print(f"  entered by pos:    {dict(entered_pos)}")
    print(f"  left mins>=60:     {dict(left_played)}")
    print(f"  entered mins>=60:  {dict(entered_played)}")
    return out_rows


def main():
    all_rows = []
    for season in SUPPORTED_SEASONS:
        print(f"\n######## {season} ########")
        all_rows.extend(analyze_season(season))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        fields = ["season", "gw", "movement", "player_id", "web_name", "position",
                  "v1_p_start", "v1_bucket", "actual_minutes", "blank", "actual_points"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"\nWrote {OUT} ({len(all_rows)} rows)")

    # Cross-season blank rates among movers
    print("\n=== Cross-season blank rates among XI movers ===")
    by = defaultdict(lambda: {"left": [0, 0], "entered": [0, 0]})
    for r in all_rows:
        key = r["season"]
        m = r["movement"]
        by[key][m][1] += 1
        by[key][m][0] += int(r["blank"])
    for season in SUPPORTED_SEASONS:
        L, E = by[season]["left"], by[season]["entered"]
        print(
            f"  {season}: left blanks {L[0]}/{L[1]} ({100*L[0]/max(L[1],1):.1f}%) | "
            f"entered blanks {E[0]}/{E[1]} ({100*E[0]/max(E[1],1):.1f}%)"
        )


if __name__ == "__main__":
    main()
