"""E034 diagnostic: squad-admission entrant toxicology + boundary analysis.

After E033: wrong-15 dominates on FAIL. Profiles squad entrants/leavers at the
15-player admission boundary under packaged rates_v2b.

Per entrant:
  profile fields (position, price, p_start, recent4, prior, new_club, ...)
  delta_u_boundary = entrant U - best excluded U (marginal admission)
  delta_mu_boundary = entrant mu - best excluded mu
  good/bad labels (evaluation only; mins>=60)

Frozen: v2am_s + rates=v1 vs packaged rates_v2b; objective=next; seed=7; balanced.

No new utility. No lambda. No squad ILP rewrite. Diagnostic only.

Usage:
    python scripts/e034_squad_entrant_toxicology.py
    python scripts/e034_squad_entrant_toxicology.py --season 2023-24
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
from engine.packaging import apply_packaged_next_utility, minutes_reliability_q
from engine.project import project_all
from engine.rates_v2b import build_rates_priors_for_snapshot

OUT = Path("records") / "historical" / "e034_squad_entrant_toxicology.csv"
OUT_TXT = Path("records") / "historical" / "e034_squad_entrant_toxicology_summary.txt"
SEED = 7
OBJECTIVE = "next"
STRATEGY = "balanced"
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}


def _pts(act: dict, pid: int) -> float:
    return float(act.get(pid, {}).get("actual_points", 0) or 0)


def _mins(act: dict, pid: int) -> float:
    return float(act.get(pid, {}).get("actual_minutes", 0) or 0)


def best_excluded(
    snap,
    by_t: dict,
    squad_ids: set[int],
) -> tuple[int | None, float, float]:
    """Best eligible player not in squad by treat next_utility."""
    best_id: int | None = None
    best_u = float("-inf")
    best_mu = float("-inf")
    for p in snap.players:
        if p.id not in by_t or not p.can_select:
            continue
        if by_t[p.id].horizon_utility <= -20:
            continue
        if p.id in squad_ids:
            continue
        u = by_t[p.id].next_utility
        if u > best_u:
            best_u = u
            best_mu = by_t[p.id].next_mu
            best_id = p.id
    if best_id is None:
        return None, float("nan"), float("nan")
    return best_id, best_u, best_mu


def analyze_season(season: str) -> list[dict]:
    ensure_vaastav((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E034 squad entrant toxicology gate={gate} ===")
    new_ids = new_club_ids(season)
    rows: list[dict] = []

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue

        recent = recent_minutes_by_element(season, gw, window=RECENT_WINDOW)
        priors = build_rates_priors_for_snapshot(season, snap)
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
        by_c = {p.player.id: p for p in v1}
        by_t = {p.player.id: p for p in packaged}
        by_v2b = {p.player.id: p for p in v2b}

        try:
            sol_c = solve_squad(snap, v1, strategy=STRATEGY, objective=OBJECTIVE)
            sol_t = solve_squad(snap, packaged, strategy=STRATEGY, objective=OBJECTIVE)
        except RuntimeError:
            continue

        c_squad = {p.id for p in sol_c.players}
        t_squad = {p.id for p in sol_t.players}
        entered = t_squad - c_squad
        left = c_squad - t_squad

        be_id, be_u, be_mu = best_excluded(snap, by_t, t_squad)
        weakest_u = min(by_t[p.id].next_utility for p in sol_t.players)
        leaver_pts = [_pts(act, pid) for pid in left]
        mean_leaver_pts = statistics.mean(leaver_pts) if leaver_pts else float("nan")

        for movement, pids in (("entered", entered), ("left", left)):
            for pid in pids:
                pc, pt, pv2 = by_c[pid], by_t[pid], by_v2b[pid]
                pl = pt.player
                mins = _mins(act, pid)
                pts = _pts(act, pid)
                r4 = recent.get(pid, 0)
                q = minutes_reliability_q(r4, gw)
                mu_lift = pt.next_mu - pc.next_mu
                u_lift = pt.next_utility - pc.next_utility
                v2b_lift = pv2.next_mu - pc.next_mu

                delta_u_boundary = float("nan")
                delta_mu_boundary = float("nan")
                small_boundary = 0
                if movement == "entered" and be_id is not None:
                    delta_u_boundary = pt.next_utility - be_u
                    delta_mu_boundary = pt.next_mu - be_mu
                    small_boundary = int(delta_u_boundary < 0.25)

                good_60 = int(mins >= 60 and pts > 0)
                bad_60 = int(mins >= 60 and pts <= 0)
                vs_leavers = (
                    round(pts - mean_leaver_pts, 4)
                    if movement == "entered" and leaver_pts
                    else ""
                )

                rows.append({
                    "season": season,
                    "e024_gate": gate,
                    "gw": gw,
                    "movement": movement,
                    "player_id": pid,
                    "web_name": pl.web_name,
                    "position": pl.position,
                    "price": pl.now_cost,
                    "season_minutes": pl.minutes,
                    "recent4_minutes": r4,
                    "p_start": round(pc.next_p_start, 4),
                    "q": round(q, 4),
                    "ctrl_mu": round(pc.next_mu, 4),
                    "treat_mu": round(pt.next_mu, 4),
                    "mu_lift": round(mu_lift, 4),
                    "ctrl_u": round(pc.next_utility, 4),
                    "treat_u": round(pt.next_utility, 4),
                    "u_lift": round(u_lift, 4),
                    "v2b_mu_lift": round(v2b_lift, 4),
                    "delta_u_boundary": round(delta_u_boundary, 4) if movement == "entered" else "",
                    "delta_mu_boundary": round(delta_mu_boundary, 4) if movement == "entered" else "",
                    "small_boundary": small_boundary if movement == "entered" else "",
                    "best_excluded_u": round(be_u, 4) if movement == "entered" and be_id else "",
                    "had_club_prior": int(pid in priors),
                    "new_club": int(pid in new_ids),
                    "actual_minutes": mins,
                    "blank": int(mins == 0),
                    "actual_pts": round(pts, 4),
                    "mu_error": round(pts - pt.next_mu, 4),
                    "good_60": good_60,
                    "bad_60": bad_60,
                    "vs_mean_leaver_pts": vs_leavers,
                })

    ent = [r for r in rows if r["movement"] == "entered"]
    print(f"  rows={len(rows)} entered={len(ent)}")
    return rows


def _pct(num: int, den: int) -> str:
    if den == 0:
        return "n/a"
    return f"{100.0 * num / den:.1f}% ({num}/{den})"


def summarize(rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E034: squad-admission entrant toxicology (packaged rates_v2b; balanced)")
    lines.append("delta_u_boundary = entrant treat_u - best excluded treat_u")
    lines.append("good_60/bad_60: actual_pts >/<= 0 with minutes>=60 (evaluation only)")
    lines.append("")

    entered = [r for r in rows if r["movement"] == "entered"]
    for gate in ("FAIL", "PASS"):
        g = [r for r in entered if r["e024_gate"] == gate]
        n = len(g)
        if n < 3:
            lines.append(f"=== {gate}: n={n} (too few) ===")
            continue
        lines.append(f"=== {gate} entered n={n} ===")
        blank = 100.0 * sum(int(r["blank"]) for r in g) / n
        prior = 100.0 * sum(int(r["had_club_prior"]) for r in g) / n
        cold = 100.0 * sum(1 for r in g if r["recent4_minutes"] < 90) / n
        lines.append(
            f"  blank%={blank:.1f} prior%={prior:.1f} recent4<90%={cold:.1f} "
            f"mean_mu_lift={statistics.mean(float(r['mu_lift']) for r in g):.3f} "
            f"mean_u_lift={statistics.mean(float(r['u_lift']) for r in g):.3f}"
        )
        g60 = [r for r in g if float(r["actual_minutes"]) >= 60]
        if g60:
            good = sum(int(r["good_60"]) for r in g60)
            bad = sum(int(r["bad_60"]) for r in g60)
            lines.append(
                f"  both60: good%={_pct(good, len(g60))} bad%={_pct(bad, len(g60))} "
                f"mean_pts={statistics.mean(float(r['actual_pts']) for r in g60):.2f} "
                f"mean_mu_error={statistics.mean(float(r['mu_error']) for r in g60):.3f}"
            )
        dub = [float(r["delta_u_boundary"]) for r in g if r["delta_u_boundary"] != ""]
        if dub:
            lines.append(
                f"  delta_u_boundary: mean={statistics.mean(dub):.3f} "
                f"small(<0.25)={sum(1 for x in dub if x < 0.25)}/{len(dub)}"
            )
        vs = [float(r["vs_mean_leaver_pts"]) for r in g if r["vs_mean_leaver_pts"] != ""]
        if vs:
            lines.append(f"  vs_mean_leaver_pts: mean={statistics.mean(vs):.3f}")

        lines.append("  cells (entered blank% / good_60% when n>=5):")
        for label, pred in (
            ("prior+recent4<90", lambda r: r["had_club_prior"] and r["recent4_minutes"] < 90),
            ("prior+recent4>=90", lambda r: r["had_club_prior"] and r["recent4_minutes"] >= 90),
            ("small_boundary", lambda r: r["small_boundary"] == 1),
            ("large_boundary", lambda r: r["delta_u_boundary"] != "" and float(r["delta_u_boundary"]) >= 0.5),
        ):
            cell = [r for r in g if pred(r)]
            nc = len(cell)
            if nc < 5:
                continue
            b = 100.0 * sum(int(r["blank"]) for r in cell) / nc
            c60 = [r for r in cell if float(r["actual_minutes"]) >= 60]
            good_c = 100.0 * sum(int(r["good_60"]) for r in c60) / len(c60) if c60 else float("nan")
            lines.append(f"    {label:22} n={nc:3} blank%={b:.1f} good_60%={good_c:.1f}")
        lines.append("")

    text = "\n".join(lines) + "\n"
    print(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e034] squad entrant toxicology; balanced; no new objective")
    all_rows: list[dict] = []
    for s in seasons:
        all_rows.extend(analyze_season(s))

    fields = [
        "season", "e024_gate", "gw", "movement", "player_id", "web_name", "position",
        "price", "season_minutes", "recent4_minutes", "p_start", "q",
        "ctrl_mu", "treat_mu", "mu_lift", "ctrl_u", "treat_u", "u_lift", "v2b_mu_lift",
        "delta_u_boundary", "delta_mu_boundary", "small_boundary", "best_excluded_u",
        "had_club_prior", "new_club",
        "actual_minutes", "blank", "actual_pts", "mu_error",
        "good_60", "bad_60", "vs_mean_leaver_pts",
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
