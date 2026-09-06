"""E046 / E046-A: Free Hit ROI under sticky held 15 (0 FT).

Degeneracy lock: B0 Cap from held XI every GW — never weekly blank-slate.

Arms (B1 != C):
  B0: never FH; Cap from sticky HELD_0 XI every GW
  B1: FH once at effective g* (default 20; no U in timing)
  C:  FH once at t* = argmax U_FH(t); tie -> lowest GW

Usage:
    python scripts/e046_free_hit_roi.py
    python scripts/e046_free_hit_roi.py --season 2023-24
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.e046_fh_policy import (
    G_STAR,
    blank_slate,
    effective_g_star,
    ensure_e046_data,
    held_xi,
    next_xi_utility,
    project_e046,
    select_t_star,
    FhRow,
)
from engine.harness import (
    SUPPORTED_SEASONS,
    build_snapshot,
    ensure_vaastav,
    gw_actuals,
)
from engine.metrics import record_path

OUT_SEASON = Path("records") / "historical" / "e046_free_hit_roi_season.csv"
OUT_GW = Path("records") / "historical" / "e046_free_hit_roi_gw.csv"
OUT_TXT = Path("records") / "historical" / "e046_free_hit_roi_summary.txt"
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}


def _pts(act: dict, pid: int) -> float:
    return float(act.get(pid, {}).get("actual_points", 0) or 0)


def _cap(xi, capt, act: dict) -> float:
    return sum(_pts(act, p.id) for p in xi) + _pts(act, capt.id)


def freeze_held_0(season: str) -> tuple[list[int], int]:
    """HELD_0 = blank-slate 15 at first usable GW."""
    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        snap = build_snapshot(season, as_of_gw=gw)
        if not gw_actuals(season, gw):
            continue
        projs = project_e046(snap, horizon=1)
        try:
            sol = blank_slate(snap, projs)
        except RuntimeError:
            continue
        return [p.id for p in sol.players], gw
    raise RuntimeError(f"{season}: no usable GW to freeze HELD_0")


def analyze_season(season: str) -> tuple[list[dict], dict]:
    ensure_vaastav((season,))
    ensure_e046_data((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E046-A FH ROI gate={gate} ===", flush=True)

    held_ids, held_gw = freeze_held_0(season)
    print(f"  HELD_0 frozen at GW{held_gw} ({len(held_ids)} ids)", flush=True)

    gw_rows: list[dict] = []
    fh_rows: list[FhRow] = []

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        print(f"  [{season}] GW{gw}", flush=True)
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue
        projs = project_e046(snap, horizon=1)
        by_id = {p.player.id: p for p in projs}

        try:
            sol_blank = blank_slate(snap, projs)
        except RuntimeError as e:
            fh_rows.append(
                FhRow(gw, 0.0, 0.0, 0.0, True, f"blank:{e}")
            )
            gw_rows.append({
                "season": season,
                "e024_gate": gate,
                "gw": gw,
                "held_freeze_gw": held_gw,
                "excluded": 1,
                "exclude_reason": f"blank:{e}",
                "u_blank": "",
                "u_held": "",
                "u_fh": "",
                "cap_normal": "",
                "cap_fh": "",
                "delta_cap": "",
            })
            continue

        xi_h, _bench_h, capt_h, u_held, excl = held_xi(snap, projs, held_ids)
        if excl is not None:
            fh_rows.append(FhRow(gw, 0.0, 0.0, 0.0, True, excl))
            gw_rows.append({
                "season": season,
                "e024_gate": gate,
                "gw": gw,
                "held_freeze_gw": held_gw,
                "excluded": 1,
                "exclude_reason": excl,
                "u_blank": "",
                "u_held": "",
                "u_fh": "",
                "cap_normal": "",
                "cap_fh": "",
                "delta_cap": "",
            })
            continue

        u_blank = float(sol_blank.next_xi_utility)
        # Sanity: recompute from XI+capt matches SquadSolution field
        u_blank_chk = next_xi_utility(sol_blank.xi, sol_blank.captain, by_id)
        assert abs(u_blank - u_blank_chk) < 1e-9
        u_fh = u_blank - u_held
        cap_n = _cap(xi_h, capt_h, act)
        cap_f = _cap(sol_blank.xi, sol_blank.captain, act)

        fh_rows.append(FhRow(gw, u_blank, u_held, u_fh, False, ""))
        gw_rows.append({
            "season": season,
            "e024_gate": gate,
            "gw": gw,
            "held_freeze_gw": held_gw,
            "excluded": 0,
            "exclude_reason": "",
            "u_blank": round(u_blank, 6),
            "u_held": round(u_held, 6),
            "u_fh": round(u_fh, 6),
            "cap_normal": round(cap_n, 4),
            "cap_fh": round(cap_f, 4),
            "delta_cap": round(cap_f - cap_n, 4),
            "held_captain_id": capt_h.id,
            "held_captain": capt_h.web_name,
            "blank_captain_id": sol_blank.captain.id,
            "blank_captain": sol_blank.captain.web_name,
        })

    included = [r for r in gw_rows if not int(r["excluded"])]
    if not included:
        return gw_rows, {
            "season": season,
            "e024_gate": gate,
            "n_gw": 0,
            "n_excluded": len(gw_rows),
            "held_freeze_gw": held_gw,
            "r_b0": 0.0,
            "r_b1": 0.0,
            "r_c": 0.0,
            "t_star": "",
            "g_star": G_STAR,
            "g_star_effective": "",
            "u_fh_star": "",
        }

    best = select_t_star(fh_rows)
    t_star = best.gw
    included_gws = [int(r["gw"]) for r in included]
    g_eff = effective_g_star(included_gws, G_STAR)

    r_b0 = sum(float(r["cap_normal"]) for r in included)
    by_gw = {int(r["gw"]): r for r in included}

    def season_with_fh(chip_gw: int | None) -> float:
        if chip_gw is None or chip_gw not in by_gw:
            return r_b0
        row = by_gw[chip_gw]
        return r_b0 - float(row["cap_normal"]) + float(row["cap_fh"])

    r_b1 = season_with_fh(g_eff)
    r_c = season_with_fh(t_star)

    season_row = {
        "season": season,
        "e024_gate": gate,
        "n_gw": len(included),
        "n_excluded": sum(int(r["excluded"]) for r in gw_rows),
        "held_freeze_gw": held_gw,
        "r_b0": round(r_b0, 4),
        "r_b1": round(r_b1, 4),
        "r_c": round(r_c, 4),
        "delta_c_b0": round(r_c - r_b0, 4),
        "delta_c_b1": round(r_c - r_b1, 4),
        "delta_b1_b0": round(r_b1 - r_b0, 4),
        "t_star": t_star,
        "g_star": G_STAR,
        "g_star_effective": g_eff if g_eff is not None else "",
        "u_fh_star": round(best.u_fh, 6),
        "u_blank_star": round(best.u_blank, 6),
        "u_held_star": round(best.u_held, 6),
    }
    print(
        f"  n_gw={len(included)} excl={season_row['n_excluded']} "
        f"t*={t_star} U_FH={best.u_fh:.2f} g*_eff={g_eff} | "
        f"C-B0={season_row['delta_c_b0']:.1f} C-B1={season_row['delta_c_b1']:.1f}",
        flush=True,
    )
    for r in gw_rows:
        if int(r["excluded"]):
            r["is_t_star"] = 0
            r["is_g_star"] = 0
            r["is_g_star_effective"] = 0
            continue
        g = int(r["gw"])
        r["is_t_star"] = int(g == t_star)
        r["is_g_star"] = int(g == G_STAR)
        r["is_g_star_effective"] = int(g_eff is not None and g == g_eff)
    return gw_rows, season_row


def summarize(season_rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E046-A: Free Hit ROI (sticky HELD_0 / 0 FT; production stack)")
    lines.append(
        f"B0=never FH (held XI); B1=FH@GW{G_STAR} (eff. nearest if excluded); "
        "C=argmax U_FH (tie=lowest GW)"
    )
    lines.append("U_FH = next_xi_utility(blank) - next_xi_utility(held)")
    lines.append("Gates: AGG sum4 C>B0 and C>B1; FAIL sum_FAIL C>=B0 and C>=B1")
    lines.append("Degeneracy lock: B0 never weekly blank-slate.")
    lines.append("")

    for row in season_rows:
        lines.append(
            f"  {row['season']} [{row['e024_gate']}] n={row['n_gw']} "
            f"t*={row['t_star']} g*_eff={row['g_star_effective']} | "
            f"R0={row['r_b0']:.1f} R1={row['r_b1']:.1f} Rc={row['r_c']:.1f} | "
            f"C-B0={row['delta_c_b0']:.1f} C-B1={row['delta_c_b1']:.1f}"
        )
    lines.append("")

    def _sum(rows: list[dict], key: str) -> float:
        return sum(float(r[key]) for r in rows)

    all_r = [r for r in season_rows if int(r["n_gw"]) > 0]
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
            lines.append("  CALL: E046-FH SURVIVES")
        else:
            lines.append(
                "  CALL: E046-FH KILL — as-of-T argmax-U_FH does not clear B0+B1 gates"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default=None)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else tuple(SUPPORTED_SEASONS)

    print("[e046] Control scarcity = sticky HELD_0 / 0 FT", flush=True)
    print("[e046] B0=held; B1=FH@g*; C=argmax U_FH; stack=v2am_fpla+rates=v1", flush=True)

    all_gw: list[dict] = []
    all_season: list[dict] = []
    for season in seasons:
        gw_rows, season_row = analyze_season(season)
        all_gw.extend(gw_rows)
        all_season.append(season_row)
        # Per-season artifacts so a mid-run kill does not lose progress
        out_s = Path("records") / "historical" / f"e046_free_hit_roi_season_{season}.csv"
        out_s.parent.mkdir(parents=True, exist_ok=True)
        with out_s.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(season_row.keys()))
            w.writeheader()
            w.writerow(season_row)

    OUT_SEASON.parent.mkdir(parents=True, exist_ok=True)
    if all_season:
        with OUT_SEASON.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(all_season[0].keys()))
            w.writeheader()
            w.writerows(all_season)
    if all_gw:
        # Union keys across rows (excluded rows omit some fields)
        keys: list[str] = []
        seen: set[str] = set()
        for r in all_gw:
            for k in r:
                if k not in seen:
                    seen.add(k)
                    keys.append(k)
        with OUT_GW.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(all_gw)

    text = summarize(all_season)
    print(text)
    OUT_TXT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_SEASON}", flush=True)
    print(f"wrote {OUT_GW}", flush=True)
    print(f"wrote {OUT_TXT}", flush=True)


if __name__ == "__main__":
    main()
