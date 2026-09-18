"""E057-A Phase-2: Cap/XI0 of RULE_UMAX on ELIGIBLE GWs only.

Frozen gate: LAB_LOG E057-A. Universe = ELIGIBLE (FLEX), NOT xi0_worse.
No promote. Production untouched.

Primary input: records/historical/e057_eligibility_phase1_events.csv

Usage:
    python scripts/e057_eligibility_phase2.py
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

from engine.harness import SUPPORTED_SEASONS

OUT_DIR = ROOT / "records" / "historical"
DEFAULT_EVENTS = OUT_DIR / "e057_eligibility_phase1_events.csv"
CANDIDATE = "v1_adxg"


def load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"empty: {path}")
    return rows


def summarize(eligible: list[dict]) -> tuple[str, str]:
    lines: list[str] = []
    lines.append(f"E057-A Phase-2 Cap/XI0 on ELIGIBLE: {CANDIDATE} vs fixtures=v1")
    lines.append(
        "Frozen: universe=ELIGIBLE (XI diff AND FLEX); NOT xi0_worse; "
        "SURVIVE iff Cap(RULE)>Cap(cand) AND zeros(RULE)<=zeros(cand) "
        "AND not identity-to-ctrl on all eligible"
    )
    lines.append("")
    lines.append(f"n_eligible={len(eligible)}")
    lines.append("")

    if not eligible:
        text = "\n".join(lines + ["PARK (empty eligible)", ""])
        return text, "PARK"

    ctr = Counter(r["rule_choice"] for r in eligible)
    lines.append("=== rule_choice on ELIGIBLE ===")
    for k in ("hold", "pair", "ctrl", "cand"):
        if ctr[k]:
            lines.append(f"  {k}={ctr[k]} ({100.0 * ctr[k] / len(eligible):.1f}%)")
    lines.append("")

    z_rule = sum(int(r["xi0_rule"]) for r in eligible)
    z_cand = sum(int(r["xi0_cand"]) for r in eligible)
    z_ctrl = sum(int(r["xi0_ctrl"]) for r in eligible)
    cap_rule = sum(float(r["cap_rule"]) for r in eligible)
    cap_cand = sum(float(r["cap_cand"]) for r in eligible)
    cap_ctrl = sum(float(r["cap_ctrl"]) for r in eligible)
    n_ctrl = sum(1 for r in eligible if r["rule_choice"] == "ctrl")

    lines.append("=== AGG on ELIGIBLE (primary gate) ===")
    lines.append(
        f"  sum_xi0 rule={z_rule} cand={z_cand} ctrl={z_ctrl} "
        f"(rule<=cand: {z_rule <= z_cand})"
    )
    lines.append(
        f"  sum_Cap rule={cap_rule:.1f} cand={cap_cand:.1f} ctrl={cap_ctrl:.1f} "
        f"delta_vs_cand={cap_rule - cap_cand:+.1f}"
    )
    lines.append(f"  n_rule_eq_ctrl={n_ctrl}/{len(eligible)}")
    lines.append("")

    lines.append("=== per-season ELIGIBLE (asterisk visibility) ===")
    for season in SUPPORTED_SEASONS:
        sub = [r for r in eligible if r["season"] == season]
        if not sub:
            lines.append(f"  {season}: n=0")
            continue
        zr = sum(int(r["xi0_rule"]) for r in sub)
        zc = sum(int(r["xi0_cand"]) for r in sub)
        cr = sum(float(r["cap_rule"]) for r in sub)
        cc = sum(float(r["cap_cand"]) for r in sub)
        c = Counter(r["rule_choice"] for r in sub)
        lines.append(
            f"  {season} n={len(sub)} "
            + " ".join(f"{k}={c[k]}" for k in ("hold", "pair", "ctrl", "cand") if c[k])
            + f" xi0 {zc}->{zr} Cap {cc:.0f}->{cr:.0f} dCap={cr - cc:+.0f}"
        )
    lines.append("")

    # report-only: eligible ∩ xi0_worse
    overlap = [r for r in eligible if int(r["xi0_worse_gw"]) == 1]
    if overlap:
        zr = sum(int(r["xi0_rule"]) for r in overlap)
        zc = sum(int(r["xi0_cand"]) for r in overlap)
        cr = sum(float(r["cap_rule"]) for r in overlap)
        cc = sum(float(r["cap_cand"]) for r in overlap)
        lines.append("=== Report-only: ELIGIBLE ∩ xi0_worse (not the gate) ===")
        lines.append(
            f"  n={len(overlap)} xi0 {zc}->{zr} Cap {cc:.1f}->{cr:.1f} "
            f"dCap={cr - cc:+.1f}"
        )
        lines.append("")

    cap_ok = cap_rule > cap_cand
    xi0_ok = z_rule <= z_cand
    not_all_ctrl = n_ctrl < len(eligible)
    survive = cap_ok and xi0_ok and not_all_ctrl

    if survive:
        status = "SURVIVE"
        verdict = (
            f"SURVIVE Phase-2 on ELIGIBLE "
            f"(Cap RULE {cap_rule:.1f} > cand {cap_cand:.1f}; "
            f"XI0 RULE {z_rule} <= cand {z_cand}; not identity-to-ctrl)"
        )
        nxt = (
            "NEXT: adopt prereg OR product-surface wiring under LIVE MENU "
            "(HOLD deferred); production still untouched until explicit adopt."
        )
    else:
        status = "PARK"
        reasons = []
        if not cap_ok:
            reasons.append("Cap(RULE)<=Cap(cand)")
        if not xi0_ok:
            reasons.append("XI0(RULE)>XI0(cand)")
        if not not_all_ctrl:
            reasons.append("RULE identical to always-ctrl on all eligible")
        verdict = f"PARK Phase-2 ({'; '.join(reasons)})"
        nxt = "NEXT: park product-surface Cap claim; do not adopt RULE globally."

    lines.append("=== VERDICT (frozen Phase-2 on ELIGIBLE) ===")
    lines.append(verdict)
    lines.append(nxt)
    lines.append("xi0_worse was not the gate. No promote. Production untouched.")
    return "\n".join(lines) + "\n", status


def main() -> None:
    parser = argparse.ArgumentParser(description="E057-A Phase-2 Cap/XI0 on ELIGIBLE.")
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    args = parser.parse_args()

    print("[e057-p2] Universe = ELIGIBLE (FLEX) — NOT xi0_worse")
    print("[e057-p2] Phase-2 Cap/XI0 gate — no promote")

    rows = load_csv(args.events)
    eligible = [r for r in rows if str(r["eligible"]) == "1"]

    text, status = summarize(eligible)
    ev_path = OUT_DIR / "e057_eligibility_phase2_events.csv"
    sum_path = OUT_DIR / "e057_eligibility_phase2_summary.txt"
    verd_path = OUT_DIR / "e057_eligibility_phase2_verdict.txt"

    # write eligible-only events for audit
    if eligible:
        with ev_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(eligible[0].keys()))
            w.writeheader()
            w.writerows(eligible)
    else:
        ev_path.write_text("", encoding="utf-8")

    sum_path.write_text(text, encoding="utf-8")
    verd_path.write_text(
        f"E057-A Phase-2 verdict ({CANDIDATE} vs v1)\n"
        f"STATUS={status}\n"
        f"n_eligible={len(eligible)}\n"
        f"See {sum_path.name}\n",
        encoding="utf-8",
    )
    sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
    print(f"Wrote {ev_path}")
    print(f"Wrote {sum_path}")
    print(f"Wrote {verd_path}")


if __name__ == "__main__":
    main()
