"""E040 / E040-A: Triple Captain ROI under frozen production stack.

Arms (B1 != C):
  B0: never TC; normal captain every GW
  B1: TC once at fixed g*=20 (no U in timing)
  C:  TC once at t* = argmax_t U_capt(t); tie -> lowest GW

U_capt(t) = next_utility of engine.optimize.pick_captains at GW t.
Stack: v2am_s + rates=v1 + fixtures v1; balanced; objective=next; seed=7.

Cap_normal = sum(XI pts) + capt_pts
Cap_TC     = Cap_normal + capt_pts

Gates (E040-A):
  AGG:  sum_4 R(C) > sum R(B0) AND sum R(C) > sum R(B1)
  FAIL: sum_FAIL R(C) >= sum_FAIL R(B0) AND sum_FAIL R(C) >= sum_FAIL R(B1)

Usage:
    python scripts/e040_triple_captain_roi.py
    python scripts/e040_triple_captain_roi.py --season 2023-24
"""
from __future__ import annotations

import argparse
import csv
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
)
from engine.metrics import record_path
from engine.optimize import pick_captains, solve_squad
from engine.project import project_all

OUT_SEASON = Path("records") / "historical" / "e040_triple_captain_roi_season.csv"
OUT_GW = Path("records") / "historical" / "e040_triple_captain_roi_gw.csv"
OUT_TXT = Path("records") / "historical" / "e040_triple_captain_roi_summary.txt"
SEED = 7
STRATEGY = "balanced"
OBJECTIVE = "next"
G_STAR = 20
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}


def _pts(act: dict, pid: int) -> float:
    return float(act.get(pid, {}).get("actual_points", 0) or 0)


def analyze_season(season: str) -> tuple[list[dict], dict]:
    ensure_vaastav((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E040-A TC ROI gate={gate} ===")
    gw_rows: list[dict] = []

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue
        v1 = project_all(
            snap, horizon=1, strategy=STRATEGY, seed=SEED,
            minutes_version="v2am_s", rates_version="v1", fixtures_version="v1",
        )
        by_id = {p.player.id: p for p in v1}
        try:
            sol = solve_squad(snap, v1, strategy=STRATEGY, objective=OBJECTIVE)
        except RuntimeError:
            continue
        capt = sol.captain
        # Prefer pick_captains on solved XI for consistency with amendment wording.
        try:
            capt, _ = pick_captains(sol.xi, by_id)
        except Exception:
            pass
        u_capt = by_id[capt.id].next_utility
        capt_y = _pts(act, capt.id)
        xi_y = sum(_pts(act, p.id) for p in sol.xi)
        cap_normal = xi_y + capt_y
        gw_rows.append({
            "season": season,
            "e024_gate": gate,
            "gw": gw,
            "captain_id": capt.id,
            "captain_name": capt.web_name,
            "u_capt": round(u_capt, 4),
            "capt_pts": round(capt_y, 4),
            "cap_normal": round(cap_normal, 4),
            "cap_tc": round(cap_normal + capt_y, 4),
        })

    if not gw_rows:
        return [], {
            "season": season,
            "e024_gate": gate,
            "n_gw": 0,
            "r_b0": 0.0,
            "r_b1": 0.0,
            "r_c": 0.0,
            "t_star": "",
            "g_star": G_STAR,
            "u_capt_star": "",
            "captain_c": "",
            "captain_b1": "",
        }

    # C: argmax U_capt; tie -> lowest GW
    best = sorted(gw_rows, key=lambda r: (-r["u_capt"], r["gw"]))[0]
    t_star = int(best["gw"])

    r_b0 = sum(r["cap_normal"] for r in gw_rows)
    # B1 / C: add one extra captain copy on chip GW if that GW exists
    by_gw = {int(r["gw"]): r for r in gw_rows}

    def season_with_tc(chip_gw: int) -> float:
        total = r_b0
        row = by_gw.get(chip_gw)
        if row is not None:
            total += row["capt_pts"]  # Cap_TC - Cap_normal
        return total

    r_b1 = season_with_tc(G_STAR)
    r_c = season_with_tc(t_star)

    b1_row = by_gw.get(G_STAR)
    season_row = {
        "season": season,
        "e024_gate": gate,
        "n_gw": len(gw_rows),
        "r_b0": round(r_b0, 4),
        "r_b1": round(r_b1, 4),
        "r_c": round(r_c, 4),
        "delta_c_b0": round(r_c - r_b0, 4),
        "delta_c_b1": round(r_c - r_b1, 4),
        "delta_b1_b0": round(r_b1 - r_b0, 4),
        "t_star": t_star,
        "g_star": G_STAR,
        "u_capt_star": best["u_capt"],
        "captain_c": best["captain_name"],
        "captain_c_id": best["captain_id"],
        "captain_b1": b1_row["captain_name"] if b1_row else "",
        "captain_b1_id": b1_row["captain_id"] if b1_row else "",
        "g_star_present": int(b1_row is not None),
    }
    print(
        f"  n_gw={len(gw_rows)} t*={t_star} ({best['captain_name']} U={best['u_capt']:.2f}) "
        f"R(C)-R(B0)={season_row['delta_c_b0']:.1f} R(C)-R(B1)={season_row['delta_c_b1']:.1f}"
    )
    for r in gw_rows:
        r["is_t_star"] = int(int(r["gw"]) == t_star)
        r["is_g_star"] = int(int(r["gw"]) == G_STAR)
    return gw_rows, season_row


def summarize(season_rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E040-A: Triple Captain ROI (production stack)")
    lines.append(f"B0=never TC; B1=TC@GW{G_STAR}; C=argmax U_capt (tie=lowest GW)")
    lines.append("Gates: AGG sum4 C>B0 and C>B1; FAIL sum_FAIL C>=B0 and C>=B1")
    lines.append("")

    for row in season_rows:
        lines.append(
            f"  {row['season']} [{row['e024_gate']}] n={row['n_gw']} "
            f"t*={row['t_star']} C={row['captain_c']} | "
            f"R0={row['r_b0']:.1f} R1={row['r_b1']:.1f} Rc={row['r_c']:.1f} | "
            f"C-B0={row['delta_c_b0']:.1f} C-B1={row['delta_c_b1']:.1f}"
        )
    lines.append("")

    def _sum(rows: list[dict], key: str) -> float:
        return sum(float(r[key]) for r in rows)

    all_r = [r for r in season_rows if r["n_gw"] > 0]
    fail_r = [r for r in all_r if r["e024_gate"] == "FAIL"]
    pass_r = [r for r in all_r if r["e024_gate"] == "PASS"]

    if all_r:
        lines.append("=== AGGREGATE (4 seasons) ===")
        lines.append(
            f"  sum R(B0)={_sum(all_r,'r_b0'):.1f}  "
            f"sum R(B1)={_sum(all_r,'r_b1'):.1f}  "
            f"sum R(C)={_sum(all_r,'r_c'):.1f}"
        )
        agg_b0 = _sum(all_r, "r_c") > _sum(all_r, "r_b0")
        agg_b1 = _sum(all_r, "r_c") > _sum(all_r, "r_b1")
        lines.append(f"  AGG C>B0: {agg_b0}  AGG C>B1: {agg_b1}")
        lines.append("")

    if fail_r:
        lines.append("=== FAIL seasons ===")
        lines.append(
            f"  sum R(B0)={_sum(fail_r,'r_b0'):.1f}  "
            f"sum R(B1)={_sum(fail_r,'r_b1'):.1f}  "
            f"sum R(C)={_sum(fail_r,'r_c'):.1f}"
        )
        fail_b0 = _sum(fail_r, "r_c") >= _sum(fail_r, "r_b0")
        fail_b1 = _sum(fail_r, "r_c") >= _sum(fail_r, "r_b1")
        lines.append(f"  FAIL C>=B0: {fail_b0}  FAIL C>=B1: {fail_b1}")
        lines.append("")

    if pass_r:
        lines.append("=== PASS seasons (report) ===")
        lines.append(
            f"  sum R(B0)={_sum(pass_r,'r_b0'):.1f}  "
            f"sum R(B1)={_sum(pass_r,'r_b1'):.1f}  "
            f"sum R(C)={_sum(pass_r,'r_c'):.1f}"
        )
        lines.append("")

    if all_r and fail_r:
        agg_ok = (_sum(all_r, "r_c") > _sum(all_r, "r_b0")) and (
            _sum(all_r, "r_c") > _sum(all_r, "r_b1")
        )
        fail_ok = (_sum(fail_r, "r_c") >= _sum(fail_r, "r_b0")) and (
            _sum(fail_r, "r_c") >= _sum(fail_r, "r_b1")
        )
        lines.append("=== PRIMARY GATE ===")
        lines.append(f"  AGG: {agg_ok}")
        lines.append(f"  FAIL robustness: {fail_ok}")
        if agg_ok and fail_ok:
            lines.append("  CALL: E040-TC SURVIVES (product wiring still needs separate prereg)")
        else:
            lines.append("  CALL: E040-TC KILL — as-of-T argmax-U TC does not clear B0+B1 gates")
        lines.append("")

    text = "\n".join(lines) + "\n"
    print(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default=None)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else tuple(SUPPORTED_SEASONS)

    all_gw: list[dict] = []
    all_season: list[dict] = []
    for season in seasons:
        gw_rows, season_row = analyze_season(season)
        all_gw.extend(gw_rows)
        all_season.append(season_row)

    OUT_SEASON.parent.mkdir(parents=True, exist_ok=True)
    if all_season:
        with OUT_SEASON.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(all_season[0].keys()))
            w.writeheader()
            w.writerows(all_season)
    if all_gw:
        with OUT_GW.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(all_gw[0].keys()))
            w.writeheader()
            w.writerows(all_gw)

    text = summarize(all_season)
    OUT_TXT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_SEASON}")
    print(f"wrote {OUT_GW}")
    print(f"wrote {OUT_TXT}")


if __name__ == "__main__":
    main()
