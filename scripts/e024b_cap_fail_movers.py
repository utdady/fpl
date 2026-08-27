"""E024b diagnostic: Cap-FAIL vs Cap-PASS movers under packaged rates_v2b.

Control:  rates=v1, ILP on raw mu
Treatment: rates=v2b, ILP on packaged U (q frozen from E022)
FAIL seasons (E024 Cap): 2022-23, 2025-26
PASS seasons: 2023-24, 2024-25

Ask whether Cap-fail entrants are high-muDelta / wrong-player-when-playing
(vs blank toxicity already fixed by packaging).

Usage:
    python scripts/e024b_cap_fail_movers.py
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
from engine.obs import new_club_ids
from engine.optimize import solve_squad
from engine.packaging import apply_packaged_next_utility, minutes_reliability_q, packaged_mu
from engine.project import project_all
from engine.rates_v2b import build_rates_priors_for_snapshot

OUT = Path("records") / "historical" / "e024b_cap_fail_movers.csv"
OUT_TXT = Path("records") / "historical" / "e024b_cap_fail_movers_summary.txt"
SEED = 7
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}


def analyze_season(season: str) -> list[dict]:
    ensure_vaastav((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E024b movers (rates_v1 -> packaged rates_v2b) gate={gate} ===")
    new_ids = new_club_ids(season)
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

        v1 = project_all(
            snap, horizon=1, strategy="balanced", seed=SEED,
            minutes_version="v2am_s", rates_version="v1", fixtures_version="v1",
        )
        v2b = project_all(
            snap, horizon=1, strategy="balanced", seed=SEED,
            minutes_version="v2am_s", rates_version="v2b", fixtures_version="v1",
        )
        packaged = apply_packaged_next_utility(
            v2b, v1, recent_minutes=recent, as_of_gw=gw, strategy="balanced",
        )
        by_c = {p.player.id: p for p in v1}
        by_t = {p.player.id: p for p in v2b}
        by_u = {p.player.id: p for p in packaged}

        try:
            sol_c = solve_squad(snap, v1, strategy="balanced", objective="next")
            sol_t = solve_squad(snap, packaged, strategy="balanced", objective="next")
        except RuntimeError as e:
            print(f"    solver fail: {e}")
            continue

        c_ids = {p.id for p in sol_c.xi}
        t_ids = {p.id for p in sol_t.xi}
        c_cap = sol_c.captain.id
        t_cap = sol_t.captain.id

        for movement, pids in (("left", c_ids - t_ids), ("entered", t_ids - c_ids)):
            for pid in pids:
                pc, pt, pu = by_c[pid], by_t[pid], by_u[pid]
                pl = pt.player if movement == "entered" else pc.player
                mins = float(act.get(pid, {}).get("actual_minutes", 0) or 0)
                pts = float(act.get(pid, {}).get("actual_points", 0) or 0)
                blank = int(mins == 0)
                r4 = recent.get(pid, 0)
                q = minutes_reliability_q(r4, gw)
                dmu = pt.next_mu - pc.next_mu
                u_mu = packaged_mu(pc.next_mu, pt.next_mu, q)
                rows.append({
                    "season": season,
                    "e024_gate": gate,
                    "gw": gw,
                    "movement": movement,
                    "player_id": pid,
                    "web_name": pl.web_name,
                    "position": pl.position,
                    "season_minutes": pl.minutes,
                    "recent4_minutes": r4,
                    "q": round(q, 4),
                    "ctrl_mu": round(pc.next_mu, 4),
                    "treat_mu": round(pt.next_mu, 4),
                    "packaged_u": round(u_mu, 4),
                    "mu_delta": round(dmu, 4),
                    "had_club_prior": int(pid in priors),
                    "new_club": int(pid in new_ids),
                    "was_ctrl_captain": int(pid == c_cap),
                    "was_treat_captain": int(pid == t_cap),
                    "actual_minutes": mins,
                    "blank": blank,
                    "actual_points": pts,
                    "decision_utility": round(pu.next_utility, 4),
                })

    entered = [r for r in rows if r["movement"] == "entered"]
    if entered:
        n = len(entered)
        blank = 100.0 * sum(r["blank"] for r in entered) / n
        dmu = statistics.mean(r["mu_delta"] for r in entered)
        pts60 = [r["actual_points"] for r in entered if r["actual_minutes"] >= 60]
        print(
            f"  entered n={n} blank%={blank:.1f} mean_muD={dmu:.3f} "
            f"mean_pts|60+={statistics.mean(pts60) if pts60 else float('nan'):.2f} (n={len(pts60)})"
        )
    return rows


def summarize(rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E024b: Cap-FAIL vs Cap-PASS packaged rates movers")
    lines.append("Entered players under rates_v1 XI -> packaged rates_v2b XI")
    lines.append("")

    def block(label: str, subset: list[dict]) -> None:
        n = len(subset)
        if not n:
            lines.append(f"{label}: n=0")
            return
        blank = 100.0 * sum(r["blank"] for r in subset) / n
        cold = 100.0 * sum(1 for r in subset if r["recent4_minutes"] < 90) / n
        prior = 100.0 * sum(r["had_club_prior"] for r in subset) / n
        dmu = statistics.mean(r["mu_delta"] for r in subset)
        q = statistics.mean(r["q"] for r in subset)
        pts_all = statistics.mean(r["actual_points"] for r in subset)
        played = [r for r in subset if r["actual_minutes"] >= 60]
        pts60 = statistics.mean(r["actual_points"] for r in played) if played else float("nan")
        pos = defaultdict(int)
        for r in subset:
            pos[r["position"]] += 1
        lines.append(
            f"{label}: n={n} blank%={blank:.1f} prior%={prior:.1f} recent4<90%={cold:.1f} "
            f"mean_q={q:.2f} mean_muD={dmu:.3f} mean_pts={pts_all:.2f} "
            f"mean_pts|60+={pts60:.2f} (n60={len(played)}) pos={dict(pos)}"
        )

    fail_e = [r for r in rows if r["movement"] == "entered" and r["season"] in FAIL_SEASONS]
    pass_e = [r for r in rows if r["movement"] == "entered" and r["season"] in PASS_SEASONS]
    fail_l = [r for r in rows if r["movement"] == "left" and r["season"] in FAIL_SEASONS]
    pass_l = [r for r in rows if r["movement"] == "left" and r["season"] in PASS_SEASONS]

    lines.append("=== entered ===")
    block("FAIL entered", fail_e)
    block("PASS entered", pass_e)
    lines.append("=== left (ejected from production XI) ===")
    block("FAIL left", fail_l)
    block("PASS left", pass_l)

    lines.append("")
    lines.append("=== FAIL vs PASS entered: prior+cold / lift tails ===")
    for gate, subset in (("FAIL", fail_e), ("PASS", pass_e)):
        for label, pred in (
            ("prior+recent4<90", lambda r: r["had_club_prior"] and r["recent4_minutes"] < 90),
            ("prior+recent4>=90", lambda r: r["had_club_prior"] and r["recent4_minutes"] >= 90),
            ("muD>=0.5", lambda r: r["mu_delta"] >= 0.5),
            ("muD>=1.0", lambda r: r["mu_delta"] >= 1.0),
            ("q<0.5", lambda r: r["q"] < 0.5),
            ("q>=0.5", lambda r: r["q"] >= 0.5),
        ):
            g = [r for r in subset if pred(r)]
            n = len(g)
            if not n:
                lines.append(f"  {gate:4} {label:22} n=0")
                continue
            blank = 100.0 * sum(r["blank"] for r in g) / n
            played = [r for r in g if r["actual_minutes"] >= 60]
            pts60 = statistics.mean(r["actual_points"] for r in played) if played else float("nan")
            dmu = statistics.mean(r["mu_delta"] for r in g)
            lines.append(
                f"  {gate:4} {label:22} n={n:3} blank%={blank:.1f} "
                f"mean_muD={dmu:.3f} mean_pts|60+={pts60:.2f} (n60={len(played)})"
            )

    # Cap-relevant: among entered who played 60+, do FAIL seasons score worse?
    lines.append("")
    lines.append("=== entered who played >=60: Cap-relevant scoring ===")
    for gate, subset in (("FAIL", fail_e), ("PASS", pass_e)):
        played = [r for r in subset if r["actual_minutes"] >= 60]
        if not played:
            lines.append(f"  {gate}: n=0")
            continue
        pts = statistics.mean(r["actual_points"] for r in played)
        dmu = statistics.mean(r["mu_delta"] for r in played)
        treat = statistics.mean(r["treat_mu"] for r in played)
        gap = statistics.mean(r["treat_mu"] - r["actual_points"] for r in played)
        lines.append(
            f"  {gate}: n={len(played)} mean_pts={pts:.2f} mean_muD={dmu:.3f} "
            f"mean_treat_mu={treat:.2f} mean_treat_mu-actual={gap:.2f}"
        )

    # Left who played 60+: were we ejecting high scorers in FAIL?
    lines.append("")
    lines.append("=== left who played >=60 (ejected production XI) ===")
    for gate, subset in (("FAIL", fail_l), ("PASS", pass_l)):
        played = [r for r in subset if r["actual_minutes"] >= 60]
        if not played:
            lines.append(f"  {gate}: n=0")
            continue
        pts = statistics.mean(r["actual_points"] for r in played)
        lines.append(f"  {gate}: n={len(played)} mean_pts={pts:.2f}")

    text = "\n".join(lines) + "\n"
    print(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e024b] Cap-FAIL vs Cap-PASS packaged rates movers; q frozen; no retune")
    all_rows: list[dict] = []
    for s in seasons:
        all_rows.extend(analyze_season(s))

    fields = [
        "season", "e024_gate", "gw", "movement", "player_id", "web_name", "position",
        "season_minutes", "recent4_minutes", "q", "ctrl_mu", "treat_mu", "packaged_u",
        "mu_delta", "had_club_prior", "new_club", "was_ctrl_captain", "was_treat_captain",
        "actual_minutes", "blank", "actual_points", "decision_utility",
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
