"""E057-A Phase-1: eligibility coverage / wiring diagnostic.

Frozen: LAB_LOG E057-A — ELIGIBLE = XI_cand≠XI_ctrl AND FLEX_flag.
No Cap promote gate. xi0_worse is report-only overlap (not a trigger).
RULE_UMAX identity from E056 Phase-2 events.

Usage:
    python scripts/e057_eligibility_phase1.py
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
E055_EVENTS = OUT_DIR / "e055_cascade_phase1_events.csv"
E056_EVENTS = OUT_DIR / "e056_oc_phase2_events.csv"
CANDIDATE = "v1_adxg"


def load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"empty: {path}")
    return rows


def gw_flex_map(e055_rows: list[dict]) -> dict[tuple[str, int], dict]:
    """One row per (season, gw) from enter-events: flex_flag, n_enter, n_pos, xi0_worse."""
    out: dict[tuple[str, int], dict] = {}
    for r in e055_rows:
        key = (r["season"], int(r["gw"]))
        if key in out:
            continue
        out[key] = {
            "season": r["season"],
            "gw": int(r["gw"]),
            "e024_gate": r["e024_gate"],
            "n_enter": int(r["n_enter"]),
            "n_pos_touched": int(r["n_pos_touched"]),
            "flex_flag": int(r["flex_flag"]),
            "xi0_worse_gw": int(r["xi0_worse_gw"]),
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="E057-A Phase-1 eligibility coverage.")
    parser.add_argument("--e055", type=Path, default=E055_EVENTS)
    parser.add_argument("--e056", type=Path, default=E056_EVENTS)
    args = parser.parse_args()

    print("[e057-p1] ELIGIBLE = XI_cand!=XI_ctrl AND FLEX_flag (ex-ante)")
    print("[e057-p1] xi0_worse = report-only overlap — NOT a trigger")
    print("[e057-p1] Phase-1 coverage only — no Cap promote gate")

    flex_by_gw = gw_flex_map(load_csv(args.e055))
    e056 = load_csv(args.e056)

    rows: list[dict] = []
    missing_flex = 0
    for r in e056:
        key = (r["season"], int(r["gw"]))
        meta = flex_by_gw.get(key)
        if meta is None:
            missing_flex += 1
            flex_flag = ""
            n_enter = ""
            n_pos = ""
            xi0_worse = int(r["xi0_worse_gw"])
            eligible = 0
            wire_ok = 0
        else:
            flex_flag = meta["flex_flag"]
            n_enter = meta["n_enter"]
            n_pos = meta["n_pos_touched"]
            xi0_worse = meta["xi0_worse_gw"]
            # e056 rows are already XI_cand != XI_ctrl
            eligible = int(flex_flag == 1)
            choice = r["rule_choice"]
            wire_ok = int(eligible == 1 and choice in {"hold", "pair", "ctrl", "cand"})

        rows.append({
            "season": r["season"],
            "e024_gate": r.get("e024_gate", meta["e024_gate"] if meta else ""),
            "candidate": CANDIDATE,
            "gw": int(r["gw"]),
            "n_enter": n_enter,
            "n_pos_touched": n_pos,
            "flex_flag": flex_flag,
            "eligible": eligible if meta is not None else "",
            "xi0_worse_gw": xi0_worse,
            "rule_choice": r["rule_choice"],
            "wire_ok": wire_ok if meta is not None else 0,
            "pair_feasible": r.get("pair_feasible", ""),
            "score_rule": r.get("score_rule", ""),
            # Cap/XI0 retained for Phase-2 reuse — NOT Phase-1 gate
            "xi0_rule": r.get("xi0_rule", ""),
            "xi0_cand": r.get("xi0_cand", ""),
            "xi0_ctrl": r.get("xi0_ctrl", ""),
            "cap_rule": r.get("cap_rule", ""),
            "cap_cand": r.get("cap_cand", ""),
            "cap_ctrl": r.get("cap_ctrl", ""),
        })

    eligible_rows = [r for r in rows if r["eligible"] == 1]
    xi_diff_n = len(rows)
    n_elig = len(eligible_rows)
    n_wire_fail = sum(1 for r in eligible_rows if int(r["wire_ok"]) != 1)
    worse = [r for r in rows if int(r["xi0_worse_gw"]) == 1]
    overlap = [r for r in eligible_rows if int(r["xi0_worse_gw"]) == 1]

    lines: list[str] = []
    lines.append(f"E057-A Phase-1 eligibility coverage: {CANDIDATE} vs fixtures=v1")
    lines.append(
        "Frozen: ELIGIBLE <=> XI_cand!=XI_ctrl AND FLEX_flag "
        "(n_enter>1 OR n_pos_touched>1); xi0_worse NOT a trigger; "
        "no Cap promote gate"
    )
    lines.append(
        f"Sources: {args.e055.name} (flex) + {args.e056.name} (RULE_UMAX)"
    )
    lines.append("")
    lines.append(f"n_xi_diff_gw={xi_diff_n}  n_eligible={n_elig}  missing_flex_join={missing_flex}")
    lines.append(
        f"n_xi0_worse={len(worse)}  eligible∩xi0_worse={len(overlap)} "
        f"(report-only overlap)"
    )
    if worse:
        lines.append(
            f"  coverage of worse by ELIGIBLE: "
            f"{100.0 * len(overlap) / len(worse):.1f}% ({len(overlap)}/{len(worse)})"
        )
    lines.append("")

    lines.append("=== selected_arm on ELIGIBLE ===")
    if eligible_rows:
        ctr = Counter(r["rule_choice"] for r in eligible_rows)
        for k in ("hold", "pair", "ctrl", "cand"):
            if ctr[k]:
                lines.append(f"  {k}={ctr[k]} ({100.0 * ctr[k] / n_elig:.1f}%)")
    else:
        lines.append("  (empty)")
    lines.append("")

    lines.append("=== ELIGIBLE by season ===")
    for season in SUPPORTED_SEASONS:
        sub = [r for r in eligible_rows if r["season"] == season]
        wov = [r for r in sub if int(r["xi0_worse_gw"]) == 1]
        ctr = Counter(r["rule_choice"] for r in sub)
        lines.append(
            f"  {season} n_elig={len(sub)} ∩worse={len(wov)} "
            + " ".join(f"{k}={ctr[k]}" for k in ("hold", "pair", "ctrl", "cand") if ctr[k])
        )
    lines.append("")

    lines.append("=== Report-only: ELIGIBLE ∩ xi0_worse arm mix ===")
    if overlap:
        ctr = Counter(r["rule_choice"] for r in overlap)
        lines.append(
            "  " + ", ".join(f"{k}={ctr[k]}" for k in ("hold", "pair", "ctrl", "cand") if ctr[k])
        )
    else:
        lines.append("  (empty)")
    lines.append("")

    survive = n_elig >= 1 and n_wire_fail == 0 and missing_flex == 0
    if survive:
        status = "SURVIVE"
        verdict = (
            f"SURVIVE Phase-1 wiring "
            f"(n_eligible={n_elig}; wire_ok on all eligible; "
            f"ELIGIBLE uses FLEX only — not xi0_worse)"
        )
        nxt = "NEXT: Phase-2 Cap/XI0 on ELIGIBLE GWs only (no promote)."
    else:
        status = "PARK"
        reasons = []
        if n_elig < 1:
            reasons.append("n_eligible=0")
        if n_wire_fail:
            reasons.append(f"wire_fail={n_wire_fail}")
        if missing_flex:
            reasons.append(f"missing_flex_join={missing_flex}")
        verdict = f"PARK Phase-1 ({'; '.join(reasons)})"
        nxt = "NEXT: park product-surface wiring; do not open Phase-2 Cap gate."

    lines.append("=== VERDICT (frozen Phase-1 wiring rule) ===")
    lines.append(verdict)
    lines.append(nxt)
    lines.append("xi0_worse remains diagnostic only. No Cap promote. Production untouched.")
    text = "\n".join(lines) + "\n"

    ev_path = OUT_DIR / "e057_eligibility_phase1_events.csv"
    sum_path = OUT_DIR / "e057_eligibility_phase1_summary.txt"
    verd_path = OUT_DIR / "e057_eligibility_phase1_verdict.txt"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    with ev_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    sum_path.write_text(text, encoding="utf-8")
    verd_path.write_text(
        f"E057-A Phase-1 verdict ({CANDIDATE} vs v1)\n"
        f"STATUS={status}\n"
        f"n_eligible={n_elig}\n"
        f"n_overlap_xi0_worse={len(overlap)}\n"
        f"See {sum_path.name}\n",
        encoding="utf-8",
    )
    sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
    print(f"Wrote {ev_path}")
    print(f"Wrote {sum_path}")
    print(f"Wrote {verd_path}")


if __name__ == "__main__":
    main()
