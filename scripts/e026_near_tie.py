"""E026 diagnostic: Cap-FAIL vs Cap-PASS control-μ near-ties.

Post-processes E024b movers. No new projections. No mechanism / q / α.

Branching question for H-PACK1:
  Are FAIL ranking failures concentrated where |μ_ctrl_enter − μ_ctrl_left|
  is small (near-ties → stability/near-optimal selection),
  or do they also overturn large control gaps (→ confidence/challenger)?

Pre-registered fixed buckets (pts of control μ):
  near   : |Δμ_ctrl| < 0.25
  mid    : 0.25 ≤ |Δμ_ctrl| < 0.75
  large  : |Δμ_ctrl| ≥ 0.75

Usage:
    python scripts/e026_near_tie.py
"""
from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "records" / "historical" / "e024b_cap_fail_movers.csv"
OUT_PAIRS = ROOT / "records" / "historical" / "e026_near_tie_pairs.csv"
OUT_TXT = ROOT / "records" / "historical" / "e026_near_tie_summary.txt"
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}

# Pre-registered absolute control-μ gap cuts (not tuned on Cap).
NEAR = 0.25
MID = 0.75


def gap_bucket(abs_gap: float) -> str:
    if abs_gap < NEAR:
        return "near"
    if abs_gap < MID:
        return "mid"
    return "large"


def load_rows() -> list[dict]:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC}; run scripts/e024b_cap_fail_movers.py first")
    with SRC.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["gw"] = int(r["gw"])
        r["player_id"] = int(r["player_id"])
        r["decision_utility"] = float(r["decision_utility"])
        r["actual_minutes"] = float(r["actual_minutes"])
        r["actual_points"] = float(r["actual_points"])
        r["ctrl_mu"] = float(r["ctrl_mu"])
        r["mu_delta"] = float(r["mu_delta"])
    return rows


def build_pairs(rows: list[dict]) -> list[dict]:
    by_gw: dict[tuple[str, int], dict[str, list[dict]]] = defaultdict(
        lambda: {"entered": [], "left": []}
    )
    for r in rows:
        by_gw[(r["season"], r["gw"])][r["movement"]].append(r)

    pairs: list[dict] = []
    for (season, gw), sides in sorted(by_gw.items()):
        gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
        for e in sides["entered"]:
            for left in sides["left"]:
                d_ctrl = e["ctrl_mu"] - left["ctrl_mu"]
                abs_gap = abs(d_ctrl)
                du = e["decision_utility"] - left["decision_utility"]
                dpts = e["actual_points"] - left["actual_points"]
                both60 = int(e["actual_minutes"] >= 60 and left["actual_minutes"] >= 60)
                pairs.append({
                    "season": season,
                    "e024_gate": gate,
                    "gw": gw,
                    "enter_id": e["player_id"],
                    "enter_name": e["web_name"],
                    "enter_pos": e["position"],
                    "left_id": left["player_id"],
                    "left_name": left["web_name"],
                    "left_pos": left["position"],
                    "ctrl_mu_enter": round(e["ctrl_mu"], 4),
                    "ctrl_mu_left": round(left["ctrl_mu"], 4),
                    "d_ctrl": round(d_ctrl, 4),
                    "abs_ctrl_gap": round(abs_gap, 4),
                    "gap_bucket": gap_bucket(abs_gap),
                    "du": round(du, 4),
                    "dpts": round(dpts, 4),
                    "enter_mu_delta": e["mu_delta"],
                    "both60": both60,
                    "same_pos": int(e["position"] == left["position"]),
                    "model_pref_enter": int(du > 0),
                    "actual_pref_enter": int(dpts > 0),
                    "tie_pts": int(dpts == 0),
                    "ctrl_pref_enter": int(d_ctrl > 0),
                    "ctrl_pref_left": int(d_ctrl < 0),
                    "rank_err": int(du > 0 and dpts < 0),
                })
    return pairs


def _pair_stats(subset: list[dict]) -> str:
    n = len(subset)
    if not n:
        return "n=0"
    mean_gap = statistics.mean(p["abs_ctrl_gap"] for p in subset)
    mean_dctrl = statistics.mean(p["d_ctrl"] for p in subset)
    mean_du = statistics.mean(p["du"] for p in subset)
    mean_dpts = statistics.mean(p["dpts"] for p in subset)
    nontie = [p for p in subset if not p["tie_pts"]]
    win = 100.0 * sum(p["actual_pref_enter"] for p in nontie) / len(nontie) if nontie else float("nan")
    model_pref = [p for p in subset if p["model_pref_enter"] and not p["tie_pts"]]
    conc = (
        100.0 * sum(p["actual_pref_enter"] for p in model_pref) / len(model_pref)
        if model_pref else float("nan")
    )
    # Treatment overturns a control preference for left
    overturn = [p for p in subset if p["ctrl_pref_left"] and p["model_pref_enter"]]
    overturn_bad = [p for p in overturn if p["dpts"] < 0]
    err = [p for p in subset if p["rank_err"]]
    return (
        f"n={n} mean_|dctrl|={mean_gap:.3f} mean_dctrl={mean_dctrl:.3f} "
        f"mean_dU={mean_du:.3f} mean_dpts={mean_dpts:.3f} "
        f"entrant_win%={win:.1f} concordance%={conc:.1f} "
        f"overturn_n={len(overturn)} overturn_bad_n={len(overturn_bad)} "
        f"rank_err_n={len(err)}"
    )


def summarize(pairs: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E026: Cap-FAIL vs Cap-PASS control-μ near-tie diagnostic")
    lines.append(
        f"Pre-registered buckets: near |dctrl|<{NEAR}, "
        f"mid [{NEAR},{MID}), large ≥{MID}"
    )
    lines.append("Primary filter: both ≥60 minutes")
    lines.append("")

    primary = [p for p in pairs if p["both60"]]
    for gate in ("FAIL", "PASS"):
        g = [p for p in primary if p["e024_gate"] == gate]
        n = len(g)
        lines.append(f"=== {gate} both60 (n={n}) ===")
        if n:
            lines.append(f"  overall: {_pair_stats(g)}")
            # bucket share
            for b in ("near", "mid", "large"):
                cell = [p for p in g if p["gap_bucket"] == b]
                share = 100.0 * len(cell) / n
                lines.append(f"  {b:5} share={share:5.1f}%  {_pair_stats(cell)}")
            # rank errors by bucket
            errs = [p for p in g if p["rank_err"]]
            if errs:
                lines.append(f"  rank_err total n={len(errs)}")
                for b in ("near", "mid", "large"):
                    cell = [p for p in errs if p["gap_bucket"] == b]
                    share = 100.0 * len(cell) / len(errs)
                    lines.append(
                        f"    rank_err→{b}: n={len(cell)} share={share:.1f}%  {_pair_stats(cell)}"
                    )
            # control preferred left (clear baseline structure) overturned by treatment
            clear_left = [p for p in g if p["d_ctrl"] <= -NEAR]
            lines.append(f"  ctrl_gap≤-{NEAR} (control clearly prefers left): {_pair_stats(clear_left)}")
        lines.append("")

    # same-position both60
    lines.append("=== both60 same_pos ===")
    for gate in ("FAIL", "PASS"):
        g = [p for p in primary if p["e024_gate"] == gate and p["same_pos"]]
        n = len(g)
        lines.append(f"  {gate} n={n}")
        if not n:
            continue
        for b in ("near", "mid", "large"):
            cell = [p for p in g if p["gap_bucket"] == b]
            share = 100.0 * len(cell) / n
            lines.append(f"    {b:5} share={share:5.1f}%  {_pair_stats(cell)}")
    lines.append("")

    # Branching readout
    lines.append("=== branching readout (FAIL vs PASS both60) ===")
    for gate in ("FAIL", "PASS"):
        g = [p for p in primary if p["e024_gate"] == gate]
        n = len(g) or 1
        near_share = 100.0 * sum(1 for p in g if p["gap_bucket"] == "near") / n
        large_share = 100.0 * sum(1 for p in g if p["gap_bucket"] == "large") / n
        errs = [p for p in g if p["rank_err"]]
        ne = len(errs) or 1
        err_near = 100.0 * sum(1 for p in errs if p["gap_bucket"] == "near") / ne
        err_large = 100.0 * sum(1 for p in errs if p["gap_bucket"] == "large") / ne
        lines.append(
            f"  {gate}: pair_near%={near_share:.1f} pair_large%={large_share:.1f} "
            f"rank_err_near%={err_near:.1f} rank_err_large%={err_large:.1f}"
        )

    text = "\n".join(lines) + "\n"
    print(text)
    return text


def main() -> None:
    print("[e026] control-μ near-tie diagnostic; fixed buckets; no mechanism")
    rows = load_rows()
    pairs = build_pairs(rows)
    fields = [
        "season", "e024_gate", "gw", "enter_id", "enter_name", "enter_pos",
        "left_id", "left_name", "left_pos", "ctrl_mu_enter", "ctrl_mu_left",
        "d_ctrl", "abs_ctrl_gap", "gap_bucket", "du", "dpts", "enter_mu_delta",
        "both60", "same_pos", "model_pref_enter", "actual_pref_enter", "tie_pts",
        "ctrl_pref_enter", "ctrl_pref_left", "rank_err",
    ]
    OUT_PAIRS.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PAIRS.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(pairs)
    print(f"Wrote {OUT_PAIRS} ({len(pairs)} pairs)")
    summary = summarize(pairs)
    OUT_TXT.write_text(summary, encoding="utf-8")
    print(f"Wrote {OUT_TXT}")


if __name__ == "__main__":
    main()
