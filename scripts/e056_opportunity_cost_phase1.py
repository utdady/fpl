"""E056-A Phase-1: opportunity-cost descriptive (MATERIAL gate).

Frozen algebra/constants: LAB_LOG E056-A — do not retune after peek.
Phase-1 only: OC of cand vs HOLD/PAIR/CTRL on xi0_worse.
RULE_UMAX locked but untested. No promote. No new ILP objective.

Primary input: records/historical/e055_cascade_phase2_events.csv
(E055-A CF constructions; identity with E056-A recipes).

Usage:
    python scripts/e056_opportunity_cost_phase1.py
    python scripts/e056_opportunity_cost_phase1.py --events path/to/events.csv
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.harness import SUPPORTED_SEASONS

OUT_DIR = ROOT / "records" / "historical"
DEFAULT_EVENTS = OUT_DIR / "e055_cascade_phase2_events.csv"
CANDIDATE = "v1_adxg"


def mean(xs: list[float]) -> float:
    return statistics.mean(xs) if xs else float("nan")


def median(xs: list[float]) -> float:
    return statistics.median(xs) if xs else float("nan")


def stdev(xs: list[float]) -> float:
    return statistics.stdev(xs) if len(xs) >= 2 else float("nan")


def load_events(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"empty events: {path}")
    return rows


def enrich(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        z_c = int(r["xi0_cand"])
        z_ctrl = int(r["xi0_ctrl"])
        z_h = int(r["xi0_hold"])
        cap_c = float(r["cap_cand"])
        cap_ctrl = float(r["cap_ctrl"])
        cap_h = float(r["cap_hold"])
        pair_ok = int(r["pair_feasible"]) == 1
        row = {
            "season": r["season"],
            "e024_gate": r["e024_gate"],
            "candidate": r.get("candidate", CANDIDATE),
            "gw": int(r["gw"]),
            "xi0_worse_gw": int(r["xi0_worse_gw"]),
            "xi0_ctrl": z_ctrl,
            "xi0_cand": z_c,
            "xi0_hold": z_h,
            "cap_ctrl": cap_ctrl,
            "cap_cand": cap_c,
            "cap_hold": cap_h,
            "oc_xi0_hold": z_c - z_h,
            "oc_cap_hold": cap_h - cap_c,
            "oc_xi0_ctrl": z_c - z_ctrl,
            "oc_cap_ctrl": cap_ctrl - cap_c,
            "pair_feasible": int(pair_ok),
            "pair_reason": r.get("pair_reason", ""),
            "xi0_pair": int(r["xi0_pair"]) if pair_ok and r["xi0_pair"] != "" else "",
            "cap_pair": float(r["cap_pair"]) if pair_ok and r["cap_pair"] != "" else "",
            "oc_xi0_pair": (z_c - int(r["xi0_pair"])) if pair_ok and r["xi0_pair"] != "" else "",
            "oc_cap_pair": (
                float(r["cap_pair"]) - cap_c if pair_ok and r["cap_pair"] != "" else ""
            ),
        }
        out.append(row)
    return out


def arm_stats(rows: list[dict], oc_xi0_key: str, oc_cap_key: str) -> dict:
    xi0s = [float(r[oc_xi0_key]) for r in rows if r[oc_xi0_key] != ""]
    caps = [float(r[oc_cap_key]) for r in rows if r[oc_cap_key] != ""]
    n = len(xi0s)
    return {
        "n": n,
        "mean_oc_xi0": mean(xi0s),
        "mean_oc_cap": mean(caps),
        "median_oc_xi0": median(xi0s),
        "median_oc_cap": median(caps),
        "stdev_oc_xi0": stdev(xi0s),
        "stdev_oc_cap": stdev(caps),
        "n_oc_xi0_gt0": sum(1 for x in xi0s if x > 0),
        "n_oc_cap_gt0": sum(1 for x in caps if x > 0),
        "n_both_gt0": sum(
            1
            for r in rows
            if r[oc_xi0_key] != ""
            and r[oc_cap_key] != ""
            and float(r[oc_xi0_key]) > 0
            and float(r[oc_cap_key]) > 0
        ),
    }


def fmt_arm(name: str, s: dict) -> list[str]:
    lines = [f"=== {name} n={s['n']} ==="]
    if s["n"] == 0:
        lines.append("  (empty)")
        lines.append("")
        return lines

    def f(x: float) -> str:
        return f"{x:.4f}" if x == x else "nan"

    lines.append(f"  mean OC_XI0={f(s['mean_oc_xi0'])}  mean OC_CAP={f(s['mean_oc_cap'])}")
    lines.append(
        f"  median OC_XI0={f(s['median_oc_xi0'])}  median OC_CAP={f(s['median_oc_cap'])}"
    )
    lines.append(
        f"  stdev OC_XI0={f(s['stdev_oc_xi0'])}  stdev OC_CAP={f(s['stdev_oc_cap'])}"
    )
    lines.append(
        f"  count OC_XI0>0={s['n_oc_xi0_gt0']}/{s['n']}  "
        f"OC_CAP>0={s['n_oc_cap_gt0']}/{s['n']}  both>0={s['n_both_gt0']}/{s['n']}"
    )
    lines.append("")
    return lines


def summarize(rows: list[dict]) -> tuple[str, str, dict]:
    worse = [r for r in rows if int(r["xi0_worse_gw"]) == 1]
    lines: list[str] = []
    lines.append(f"E056-A Phase-1 OC: {CANDIDATE} vs fixtures=v1")
    lines.append(
        "Frozen: OC_XI0=z_cand-z_arm; OC_CAP=Cap_arm-Cap_cand (+ = alt better); "
        "MATERIAL iff mean OC_CAP(HOLD)>0 AND mean OC_XI0(HOLD)>0 on xi0_worse; "
        "RULE_UMAX locked untested"
    )
    lines.append(f"Source: e055_cascade_phase2_events (identity CF recipes)")
    lines.append("")
    lines.append(f"n_xi_diff_gw={len(rows)}  xi0_worse n={len(worse)}")
    lines.append("")

    lines.append("--- PRIMARY universe: xi0_worse ---")
    hold_w = arm_stats(worse, "oc_xi0_hold", "oc_cap_hold")
    pair_w = arm_stats(worse, "oc_xi0_pair", "oc_cap_pair")
    ctrl_w = arm_stats(worse, "oc_xi0_ctrl", "oc_cap_ctrl")
    lines.extend(fmt_arm("HOLD (gate)", hold_w))
    lines.extend(fmt_arm("PAIR (twin)", pair_w))
    lines.extend(fmt_arm("CTRL (anchor)", ctrl_w))

    lines.append("--- HOLD by season (xi0_worse) ---")
    for season in SUPPORTED_SEASONS:
        sub = [r for r in worse if r["season"] == season]
        if not sub:
            lines.append(f"  {season}: n=0")
            continue
        sh = arm_stats(sub, "oc_xi0_hold", "oc_cap_hold")
        lines.append(
            f"  {season} n={sh['n']} mean_OC_XI0={sh['mean_oc_xi0']:.4f} "
            f"mean_OC_CAP={sh['mean_oc_cap']:.4f} "
            f"both>0={sh['n_both_gt0']}/{sh['n']}"
        )
    lines.append("")

    lines.append("--- Report-only: ALL XI-diff GWs ---")
    hold_a = arm_stats(rows, "oc_xi0_hold", "oc_cap_hold")
    pair_a = arm_stats(rows, "oc_xi0_pair", "oc_cap_pair")
    ctrl_a = arm_stats(rows, "oc_xi0_ctrl", "oc_cap_ctrl")
    lines.extend(fmt_arm("HOLD", hold_a))
    lines.extend(fmt_arm("PAIR", pair_a))
    lines.extend(fmt_arm("CTRL", ctrl_a))

    # PAIR vs HOLD concordance on worse where PAIR feasible
    both = [
        r
        for r in worse
        if r["oc_xi0_pair"] != "" and r["oc_cap_pair"] != ""
    ]
    if both:
        same_xi0_sign = sum(
            1
            for r in both
            if (float(r["oc_xi0_hold"]) > 0) == (float(r["oc_xi0_pair"]) > 0)
        )
        same_cap_sign = sum(
            1
            for r in both
            if (float(r["oc_cap_hold"]) > 0) == (float(r["oc_cap_pair"]) > 0)
        )
        lines.append("--- Report-only: PAIR vs HOLD sign concordance (xi0_worse, pair feas) ---")
        lines.append(
            f"  n={len(both)} OC_XI0 same_sign={same_xi0_sign}/{len(both)} "
            f"OC_CAP same_sign={same_cap_sign}/{len(both)}"
        )
        lines.append("")

    m_xi0 = hold_w["mean_oc_xi0"]
    m_cap = hold_w["mean_oc_cap"]
    material = (
        len(worse) >= 1
        and m_xi0 == m_xi0
        and m_cap == m_cap
        and m_cap > 0
        and m_xi0 > 0
    )
    if material:
        status = "SURVIVE"
        verdict = (
            f"SURVIVE Phase-1 MATERIAL "
            f"(mean OC_CAP(HOLD)={m_cap:.4f}>0 AND mean OC_XI0(HOLD)={m_xi0:.4f}>0; "
            f"n_xi0_worse={len(worse)})"
        )
        nxt = "NEXT: Phase-2 RULE_UMAX only (no promote / no new ILP objective)."
    else:
        status = "PARK"
        verdict = (
            f"PARK Phase-1 (not MATERIAL: mean OC_CAP(HOLD)={m_cap} "
            f"mean OC_XI0(HOLD)={m_xi0}; n_xi0_worse={len(worse)})"
        )
        nxt = "NEXT: park valuation family for this stack; RULE_UMAX remains untested."

    lines.append("=== VERDICT (frozen MATERIAL rule) ===")
    lines.append(verdict)
    lines.append(nxt)
    lines.append("RULE_UMAX locked untested. No promote. Production untouched.")
    text = "\n".join(lines) + "\n"
    return text, status, {"mean_oc_xi0_hold": m_xi0, "mean_oc_cap_hold": m_cap, "n_worse": len(worse)}


def write_rows(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="E056-A Phase-1 OC descriptive.")
    parser.add_argument(
        "--events",
        type=Path,
        default=DEFAULT_EVENTS,
        help="E055 Phase-2 events CSV (default: records/historical/e055_cascade_phase2_events.csv)",
    )
    args = parser.parse_args()

    print("[e056-p1] CONTROL = v2am_fpla + rates=v1 + fixtures=v1")
    print(f"[e056-p1] CANDIDATE = fixtures={CANDIDATE} (E053 KILL diagnostic reference)")
    print("[e056-p1] Phase-1 OC only — RULE_UMAX locked untested")
    print(f"[e056-p1] events = {args.events}")

    raw = load_events(args.events)
    rows = enrich(raw)

    ev_path = OUT_DIR / "e056_oc_phase1_events.csv"
    sum_path = OUT_DIR / "e056_oc_phase1_summary.txt"
    verd_path = OUT_DIR / "e056_oc_phase1_verdict.txt"

    write_rows(rows, ev_path)
    text, status, stats = summarize(rows)
    sum_path.write_text(text, encoding="utf-8")
    verd_path.write_text(
        f"E056-A Phase-1 verdict ({CANDIDATE} vs v1)\n"
        f"STATUS={status}\n"
        f"n_xi0_worse={stats['n_worse']}\n"
        f"mean_OC_XI0_HOLD={stats['mean_oc_xi0_hold']}\n"
        f"mean_OC_CAP_HOLD={stats['mean_oc_cap_hold']}\n"
        f"See {sum_path.name}\n",
        encoding="utf-8",
    )
    sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
    print(f"Wrote {ev_path}")
    print(f"Wrote {sum_path}")
    print(f"Wrote {verd_path}")


if __name__ == "__main__":
    main()
