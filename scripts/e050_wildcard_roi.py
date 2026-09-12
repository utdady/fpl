"""E050 / E050-A: Wildcard ROI under sticky held 15 (0 FT) with REPLACE.

Degeneracy lock: B0 Cap from HELD_0 XI every GW — never weekly blank-slate.

Arms (B1 != C):
  B0: never WC; Cap from sticky HELD_0 XI every GW
  B1: WC once at effective g* (default 20; no U in timing); REPLACE held
  C:  WC once at t* = argmax U_WC(t); tie -> lowest GW; REPLACE held

U_WC(t) = sum_{tau>=t} [U_xi(BLANK(t).players, tau) - U_xi(HELD_0, tau)] under I_t

Usage:
    python scripts/e050_wildcard_roi.py
    python scripts/e050_wildcard_roi.py --season 2023-24
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.e050_wc_policy import (
    G_STAR,
    WcRow,
    blank_slate,
    compute_u_wc,
    effective_g_star,
    ensure_e050_data,
    freeze_held_0,
    held_xi,
    project_e050,
    season_cap_with_replace,
    select_t_star,
)
from engine.harness import (
    SUPPORTED_SEASONS,
    build_snapshot,
    ensure_vaastav,
    gw_actuals,
)
from engine.metrics import record_path

OUT_SEASON = Path("records") / "historical" / "e050_wildcard_roi_season.csv"
OUT_GW = Path("records") / "historical" / "e050_wildcard_roi_gw.csv"
OUT_TXT = Path("records") / "historical" / "e050_wildcard_roi_summary.txt"
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}


def _pts(act: dict, pid: int) -> float:
    return float(act.get(pid, {}).get("actual_points", 0) or 0)


def _cap(xi, capt, act: dict) -> float:
    return sum(_pts(act, p.id) for p in xi) + _pts(act, capt.id)


def analyze_season(season: str) -> tuple[list[dict], dict]:
    ensure_vaastav((season,))
    ensure_e050_data((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E050-A WC ROI gate={gate} ===", flush=True)

    held_ids, held_gw = freeze_held_0(season)
    print(f"  HELD_0 frozen at GW{held_gw} ({len(held_ids)} ids)", flush=True)

    gw_rows: list[dict] = []
    cap_held0: dict[int, float] = {}
    cap_blank: dict[int, float] = {}
    blank_ids_by_gw: dict[int, list[int]] = {}
    act_by_gw: dict[int, dict] = {}
    snap_cache: dict[int, object] = {}

    # Pass 1: Cap under HELD_0 / blank at each GW (as-of-t, horizon=1).
    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        print(f"  [{season}] Cap GW{gw}", flush=True)
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue
        snap_cache[gw] = snap
        act_by_gw[gw] = act
        projs = project_e050(snap, horizon=1)

        try:
            sol_blank = blank_slate(snap, projs)
        except RuntimeError as e:
            gw_rows.append({
                "season": season,
                "e024_gate": gate,
                "gw": gw,
                "held_freeze_gw": held_gw,
                "excluded": 1,
                "timing_excluded": 1,
                "exclude_reason": f"blank:{e}",
                "u_wc": "",
                "n_tau": "",
                "cap_held0": "",
                "cap_blank": "",
            })
            continue

        xi_h, _b, capt_h, _u_h, excl = held_xi(snap, projs, held_ids)
        if excl is not None:
            gw_rows.append({
                "season": season,
                "e024_gate": gate,
                "gw": gw,
                "held_freeze_gw": held_gw,
                "excluded": 1,
                "timing_excluded": 1,
                "exclude_reason": excl,
                "u_wc": "",
                "n_tau": "",
                "cap_held0": "",
                "cap_blank": "",
            })
            continue

        c0 = _cap(xi_h, capt_h, act)
        cb = _cap(sol_blank.xi, sol_blank.captain, act)
        cap_held0[gw] = c0
        cap_blank[gw] = cb
        blank_ids_by_gw[gw] = [p.id for p in sol_blank.players]
        gw_rows.append({
            "season": season,
            "e024_gate": gate,
            "gw": gw,
            "held_freeze_gw": held_gw,
            "excluded": 0,
            "timing_excluded": 0,
            "exclude_reason": "",
            "u_wc": "",
            "n_tau": "",
            "cap_held0": round(c0, 4),
            "cap_blank": round(cb, 4),
            "blank_captain_id": sol_blank.captain.id,
            "blank_captain": sol_blank.captain.web_name,
            "held_captain_id": capt_h.id,
            "held_captain": capt_h.web_name,
        })

    included = [r for r in gw_rows if not int(r["excluded"])]
    included_gws = [int(r["gw"]) for r in included]
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
            "u_wc_star": "",
        }

    # Pass 2: forward U_WC under I_t for each included candidate.
    wc_rows: list[WcRow] = []
    by_gw_row = {int(r["gw"]): r for r in gw_rows}
    for gw in included_gws:
        print(f"  [{season}] U_WC GW{gw}", flush=True)
        snap = snap_cache[gw]
        row = compute_u_wc(snap, held_ids, gw)
        wc_rows.append(row)
        br = by_gw_row[gw]
        if row.excluded:
            br["timing_excluded"] = 1
            br["exclude_reason"] = row.exclude_reason or br.get("exclude_reason", "")
            br["u_wc"] = ""
            br["n_tau"] = ""
        else:
            br["u_wc"] = round(row.u_wc, 6)
            br["n_tau"] = row.n_tau

    # Timing W: non-excluded U_WC rows; Cap W: pass-1 included (held0+blank OK).
    timing_rows = [r for r in wc_rows if not r.excluded]
    if not timing_rows:
        raise RuntimeError(f"{season}: no GWs with scoreable U_WC")

    best = select_t_star(timing_rows)
    t_star = best.gw
    g_eff = effective_g_star(included_gws, G_STAR)

    post_cap_cache: dict[tuple[int, tuple[int, ...]], float] = {}

    def snap_act_cap(gw: int, ids: list[int]) -> float:
        key = (gw, tuple(ids))
        if key in post_cap_cache:
            return post_cap_cache[key]
        snap = snap_cache[gw]
        act = act_by_gw[gw]
        projs = project_e050(snap, horizon=1)
        xi, _b, capt, _u, excl = held_xi(snap, projs, ids)
        if excl is not None:
            print(f"    warn: post-replace Cap fail GW{gw}: {excl}", flush=True)
            post_cap_cache[key] = 0.0
            return 0.0
        c = _cap(xi, capt, act)
        post_cap_cache[key] = c
        return c

    r_b0 = sum(cap_held0[g] for g in included_gws)
    r_b1 = season_cap_with_replace(
        included_gws=included_gws,
        cap_held0=cap_held0,
        cap_blank=cap_blank,
        blank_ids_by_gw=blank_ids_by_gw,
        chip_gw=g_eff,
        snap_act_cap_fn=snap_act_cap,
    )
    r_c = season_cap_with_replace(
        included_gws=included_gws,
        cap_held0=cap_held0,
        cap_blank=cap_blank,
        blank_ids_by_gw=blank_ids_by_gw,
        chip_gw=t_star,
        snap_act_cap_fn=snap_act_cap,
    )

    season_row = {
        "season": season,
        "e024_gate": gate,
        "n_gw": len(included_gws),
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
        "u_wc_star": round(best.u_wc, 6),
        "n_tau_star": best.n_tau,
    }
    print(
        f"  n_gw={len(included_gws)} t*={t_star} U_WC={best.u_wc:.2f} "
        f"n_tau*={best.n_tau} g*_eff={g_eff} | "
        f"C-B0={season_row['delta_c_b0']:.1f} C-B1={season_row['delta_c_b1']:.1f}",
        flush=True,
    )
    for r in gw_rows:
        if int(r["excluded"]) and r.get("u_wc") == "":
            # pass-1 exclude
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
    lines.append("E050-A: Wildcard ROI (sticky HELD_0 / 0 FT; REPLACE; production stack)")
    lines.append(
        f"B0=never WC (held XI); B1=WC@GW{G_STAR} replace (eff. nearest if excluded); "
        "C=argmax U_WC (tie=lowest GW) replace"
    )
    lines.append(
        "U_WC(t)=sum_{tau>=t}[U_xi(BLANK(t),tau)-U_xi(HELD_0,tau)] under I_t"
    )
    lines.append("Gates: AGG sum4 C>B0 and C>B1; FAIL sum_FAIL C>=B0 and C>=B1")
    lines.append("Degeneracy lock: B0 never weekly blank-slate. Not FH revert.")
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
            lines.append("  CALL: E050-WC SURVIVES")
        else:
            lines.append(
                "  CALL: E050-WC KILL — as-of-T argmax-U_WC does not clear B0+B1 gates"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", default=None)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("[e050] Control stack = v2am_fpla + rates=v1 + fixtures=v1", flush=True)
    print("[e050] WC REPLACE held; U_WC = forward XI lift under I_t", flush=True)
    print("[e050] B0=never; B1=g*=20; C=argmax U_WC", flush=True)

    all_gw: list[dict] = []
    season_rows: list[dict] = []
    for season in seasons:
        gw_rows, srow = analyze_season(season)
        all_gw.extend(gw_rows)
        season_rows.append(srow)
        out_s = Path("records") / "historical" / f"e050_wildcard_roi_season_{season}.csv"
        out_s.parent.mkdir(parents=True, exist_ok=True)
        with out_s.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(srow.keys()))
            w.writeheader()
            w.writerow(srow)

    if args.season:
        # single-season: still write merged-shaped files for that season only
        OUT_SEASON.parent.mkdir(parents=True, exist_ok=True)
        with OUT_SEASON.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(season_rows[0].keys()))
            w.writeheader()
            w.writerows(season_rows)
        with OUT_GW.open("w", encoding="utf-8", newline="") as f:
            fields = list(all_gw[0].keys()) if all_gw else ["season", "gw"]
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(all_gw)
        text = summarize(season_rows)
        OUT_TXT.write_text(text, encoding="utf-8")
        print(text)
        return

    OUT_SEASON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_SEASON.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(season_rows[0].keys()))
        w.writeheader()
        w.writerows(season_rows)
    with OUT_GW.open("w", encoding="utf-8", newline="") as f:
        fields = list(all_gw[0].keys()) if all_gw else ["season", "gw"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_gw)
    text = summarize(season_rows)
    OUT_TXT.write_text(text, encoding="utf-8")
    print(text)
    verdict = "SURVIVES" if "SURVIVES" in text else "KILL"
    if "INCOMPLETE" in text or len(season_rows) < 4:
        verdict = "INCOMPLETE"
    # parse CALL line
    for line in text.splitlines():
        if "CALL: E050-WC" in line:
            verdict = "SURVIVES" if "SURVIVES" in line else "KILL"
    (Path("records") / "historical" / "e050_wc_verdict.txt").write_text(
        f"VERDICT: {verdict}\n", encoding="utf-8"
    )
    print(f"VERDICT: {verdict}", flush=True)


if __name__ == "__main__":
    main()
