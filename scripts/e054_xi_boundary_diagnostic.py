"""E054-A: μ→XI decision-boundary mechanism diagnostic.

Frozen inputs: production fixtures=v1 vs candidate fixtures=v1_adxg.
Classification constants locked in LAB_LOG E054-A — do not retune after peek.

Usage:
    python scripts/e054_xi_boundary_diagnostic.py
    python scripts/e054_xi_boundary_diagnostic.py --season 2024-25
    python scripts/e054_xi_boundary_diagnostic.py --candidate v1_sxg   # optional replication
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.fplcache_avail import ensure_fplcache_avail
from engine.fplcache_strength import ensure_fplcache_strength
from engine.fplcache_strength_ad import ensure_fplcache_strength_ad
from engine.harness import SUPPORTED_SEASONS, build_snapshot, ensure_vaastav, gw_actuals
from engine.metrics import record_path
from engine.optimize import solve_squad
from engine.project import project_all

OUT_DIR = ROOT / "records" / "historical"
SEED = 7
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}

# E054-A frozen constants
NEAR = 0.25
MID = 0.75
BLANK_P60 = 0.50
CONCENTRATION_MIN = 0.50


def gap_bucket(abs_gap: float) -> str:
    if abs_gap < NEAR:
        return "near"
    if abs_gap < MID:
        return "mid"
    return "large"


def classify(
    *,
    n_enter: int,
    n_pos_touched: int,
    enter_p60_ctrl: float,
    abs_d_ctrl: float | None,
) -> str:
    if n_enter > 1 or n_pos_touched > 1:
        return "BUDGET_FLEX"
    if enter_p60_ctrl < BLANK_P60:
        return "BLANK_MIN"
    if abs_d_ctrl is not None and abs_d_ctrl < MID:
        return "NEAR_TIE"
    return "DIFFUSE"


def pair_same_pos(enters: list, exits: list) -> list[tuple]:
    """Greedy same-position pairs minimizing |d_ctrl|."""
    used_e: set[int] = set()
    used_x: set[int] = set()
    pairs: list[tuple] = []
    candidates: list[tuple] = []
    for i, e in enumerate(enters):
        for j, x in enumerate(exits):
            if e["pos"] != x["pos"]:
                continue
            d = abs(e["ctrl_mu"] - x["ctrl_mu"])
            candidates.append((d, i, j))
    candidates.sort()
    for _, i, j in candidates:
        if i in used_e or j in used_x:
            continue
        used_e.add(i)
        used_x.add(j)
        pairs.append((enters[i], exits[j]))
    return pairs


def eval_season(season: str, candidate: str, strategy: str = "balanced") -> list[dict]:
    ensure_vaastav((season,))
    ensure_fplcache_avail((season,))
    if candidate == "v1_adxg":
        ensure_fplcache_strength_ad((season,))
    elif candidate == "v1_sxg":
        ensure_fplcache_strength((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E054-A boundary ({candidate} vs v1) gate={gate} ===")
    events: list[dict] = []

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        print(f"  [{season}] GW{gw}")
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue

        ctrl = project_all(
            snap, horizon=1, strategy=strategy, seed=SEED,
            minutes_version="v2am_fpla", rates_version="v1", fixtures_version="v1",
        )
        cand = project_all(
            snap, horizon=1, strategy=strategy, seed=SEED,
            minutes_version="v2am_fpla", rates_version="v1", fixtures_version=candidate,
        )
        by_c = {p.player.id: p for p in ctrl}
        by_t = {p.player.id: p for p in cand}

        try:
            sol_c = solve_squad(snap, ctrl, strategy=strategy, objective="next")
            sol_t = solve_squad(snap, cand, strategy=strategy, objective="next")
        except RuntimeError as e:
            print(f"    solver fail: {e}")
            continue

        xi_c = {p.id for p in sol_c.xi}
        xi_t = {p.id for p in sol_t.xi}
        if xi_c == xi_t:
            continue

        enter_ids = sorted(xi_t - xi_c)
        exit_ids = sorted(xi_c - xi_t)

        def row(pid: int) -> dict:
            pc = by_c[pid]
            pt = by_t.get(pid)
            a = act.get(pid, {})
            return {
                "id": pid,
                "name": pc.player.web_name,
                "pos": pc.player.position,
                "ctrl_mu": float(pc.next_mu),
                "cand_mu": float(pt.next_mu) if pt else float("nan"),
                "ctrl_p60": float(pc.next_p_60),
                "mins": float(a.get("actual_minutes", 0) or 0),
                "pts": float(a.get("actual_points", 0) or 0),
            }

        enters = [row(i) for i in enter_ids]
        exits = [row(i) for i in exit_ids]
        pos_touched = {r["pos"] for r in enters} | {r["pos"] for r in exits}
        n_pos = len(pos_touched)
        n_enter = len(enters)

        zeros_c = sum(1 for pid in xi_c if float(act.get(pid, {}).get("actual_minutes", 0) or 0) == 0)
        zeros_t = sum(1 for pid in xi_t if float(act.get(pid, {}).get("actual_minutes", 0) or 0) == 0)
        xi0_worse = int(zeros_t > zeros_c)

        paired = pair_same_pos(enters, exits)
        paired_enter_ids = {e["id"] for e, _ in paired}
        exit_by_enter = {e["id"]: x for e, x in paired}

        for e in enters:
            x = exit_by_enter.get(e["id"])
            abs_d = abs(e["ctrl_mu"] - x["ctrl_mu"]) if x is not None else None
            bucket = gap_bucket(abs_d) if abs_d is not None else ""
            cls = classify(
                n_enter=n_enter,
                n_pos_touched=n_pos,
                enter_p60_ctrl=e["ctrl_p60"],
                abs_d_ctrl=abs_d,
            )
            blank_enter = int(e["mins"] == 0)
            primary_harm = int(blank_enter == 1 and xi0_worse == 1)
            events.append({
                "season": season,
                "e024_gate": gate,
                "candidate": candidate,
                "gw": gw,
                "class": cls,
                "gap_bucket": bucket,
                "n_enter": n_enter,
                "n_exit": len(exits),
                "n_pos_touched": n_pos,
                "xi0_ctrl": zeros_c,
                "xi0_cand": zeros_t,
                "xi0_worse_gw": xi0_worse,
                "enter_id": e["id"],
                "enter_name": e["name"],
                "enter_pos": e["pos"],
                "enter_ctrl_mu": round(e["ctrl_mu"], 4),
                "enter_cand_mu": round(e["cand_mu"], 4) if e["cand_mu"] == e["cand_mu"] else "",
                "enter_ctrl_p60": round(e["ctrl_p60"], 4),
                "enter_mins": e["mins"],
                "enter_pts": e["pts"],
                "exit_id": x["id"] if x else "",
                "exit_name": x["name"] if x else "",
                "exit_pos": x["pos"] if x else "",
                "exit_ctrl_mu": round(x["ctrl_mu"], 4) if x else "",
                "exit_mins": x["mins"] if x else "",
                "exit_pts": x["pts"] if x else "",
                "abs_d_ctrl": round(abs_d, 4) if abs_d is not None else "",
                "blank_enter": blank_enter,
                "primary_harm": primary_harm,
                "paired": int(e["id"] in paired_enter_ids),
            })
    return events


def write_events(events: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not events:
        path.write_text("", encoding="utf-8")
        return
    cols = list(events[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(events)


def summarize(events: list[dict], candidate: str) -> tuple[str, str]:
    lines: list[str] = []
    lines.append(f"E054-A decision-boundary diagnostic: {candidate} vs fixtures=v1")
    lines.append(
        f"Frozen: NEAR/MID={NEAR}/{MID}; BLANK_P60={BLANK_P60}; "
        f"priority BUDGET_FLEX>BLANK_MIN>NEAR_TIE>DIFFUSE; "
        f"concentration>={CONCENTRATION_MIN}"
    )
    lines.append("")

    classes = ["BUDGET_FLEX", "BLANK_MIN", "NEAR_TIE", "DIFFUSE"]
    primary = [e for e in events if int(e["primary_harm"]) == 1]
    blanks = [e for e in events if int(e["blank_enter"]) == 1]

    def shares(subset: list[dict]) -> dict[str, float]:
        n = len(subset)
        if n == 0:
            return {c: float("nan") for c in classes}
        ctr = Counter(e["class"] for e in subset)
        return {c: ctr[c] / n for c in classes}

    lines.append(
        f"n_enter_events={len(events)} blank_enter={len(blanks)} "
        f"primary_harm(blank_enter on xi0_worse_gw)={len(primary)}"
    )
    lines.append("")

    def block(title: str, subset: list[dict]) -> None:
        lines.append(f"=== {title} n={len(subset)} ===")
        if not subset:
            lines.append("  (empty)")
            lines.append("")
            return
        sh = shares(subset)
        for c in classes:
            n = sum(1 for e in subset if e["class"] == c)
            s = sh[c]
            s_txt = f"{100.0 * s:.1f}%" if s == s else "nan"
            lines.append(f"  {c:12} n={n:4d} share={s_txt}")
        # gap buckets among paired
        paired = [e for e in subset if e["gap_bucket"]]
        if paired:
            bc = Counter(e["gap_bucket"] for e in paired)
            lines.append(
                "  gap_buckets(paired): "
                + ", ".join(f"{k}={bc[k]}" for k in ("near", "mid", "large"))
            )
        lines.append("")

    block("ALL enter-events", events)
    block("blank_enter", blanks)
    block("PRIMARY harm (blank_enter on xi0_worse_gw)", primary)

    # per season primary
    lines.append("=== PRIMARY harm by season ===")
    for season in SUPPORTED_SEASONS:
        sub = [e for e in primary if e["season"] == season]
        if not sub:
            lines.append(f"  {season}: n=0")
            continue
        sh = shares(sub)
        top = max(classes, key=lambda c: sh[c] if sh[c] == sh[c] else -1)
        lines.append(
            f"  {season} n={len(sub)} "
            + " ".join(f"{c[0:3]}={100*sh[c]:.0f}%" for c in classes)
            + f" top={top}"
        )
    lines.append("")

    sh_p = shares(primary)
    if primary:
        best = max(classes, key=lambda c: sh_p[c])
        best_s = sh_p[best]
        if best_s >= CONCENTRATION_MIN:
            branch = best
            verdict = f"CONCENTRATED -> branch {branch} (share={100*best_s:.1f}%)"
        else:
            branch = "DIFFUSE"
            verdict = (
                f"DIFFUSE / park (max={best} at {100*best_s:.1f}% "
                f"< {100*CONCENTRATION_MIN:.0f}%)"
            )
    else:
        branch = "DIFFUSE"
        verdict = "DIFFUSE / park (no primary harm events)"

    family = {
        "NEAR_TIE": "ranking/degeneracy research (E026 identity)",
        "BUDGET_FLEX": "ILP/portfolio interaction research",
        "BLANK_MIN": "minutes/availability research",
        "DIFFUSE": "park boundary hypothesis; do not invent a mechanism",
    }[branch]

    lines.append("=== BRANCH (frozen rule) ===")
    lines.append(verdict)
    lines.append(f"NEXT_FAMILY: {family}")
    lines.append("No mechanism / no promote on this card.")
    text = "\n".join(lines) + "\n"
    return text, branch


def main() -> None:
    parser = argparse.ArgumentParser(description="E054-A μ→XI boundary diagnostic.")
    parser.add_argument("--season", choices=SUPPORTED_SEASONS, default=None)
    parser.add_argument(
        "--candidate",
        choices=("v1_adxg", "v1_sxg"),
        default="v1_adxg",
        help="Frozen candidate fixtures_version (primary=v1_adxg)",
    )
    parser.add_argument("--strategy", default="balanced")
    args = parser.parse_args()

    print("[e054] CONTROL = v2am_fpla + rates=v1 + fixtures=v1")
    print(f"[e054] CANDIDATE = fixtures={args.candidate}")
    print("[e054] Mechanism forbidden — classification report only")

    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    events: list[dict] = []
    for s in seasons:
        events.extend(eval_season(s, args.candidate, args.strategy))

    tag = args.candidate.replace("v1_", "")
    if args.season:
        ev_path = OUT_DIR / f"e054_boundary_events_{tag}_{args.season}.csv"
        sum_path = OUT_DIR / f"e054_boundary_summary_{tag}_{args.season}.txt"
        verd_path = OUT_DIR / f"e054_boundary_verdict_{tag}_{args.season}.txt"
    else:
        ev_path = OUT_DIR / f"e054_boundary_events_{tag}.csv"
        sum_path = OUT_DIR / f"e054_boundary_summary_{tag}.txt"
        verd_path = OUT_DIR / f"e054_boundary_verdict_{tag}.txt"

    write_events(events, ev_path)
    text, branch = summarize(events, args.candidate)
    sum_path.write_text(text, encoding="utf-8")
    verd_path.write_text(
        f"E054-A verdict ({args.candidate} vs v1)\n"
        f"BRANCH={branch}\n"
        f"See {sum_path.name}\n",
        encoding="utf-8",
    )
    print(text)
    print(f"Wrote {ev_path}")
    print(f"Wrote {sum_path}")
    print(f"Wrote {verd_path}")


if __name__ == "__main__":
    main()
