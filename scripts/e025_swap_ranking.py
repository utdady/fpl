"""E025 diagnostic: Cap-FAIL vs Cap-PASS swap ranking concordance.

Post-processes E024b mover rows. No new projections. No q/α retune.

Among within-GW (entered × left) pairs where both played ≥60:
does Cap-FAIL show worse P(pts_e > pts_l | U_e > U_l) and worse mean Δpts?

Usage:
    python scripts/e025_swap_ranking.py
"""
from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "records" / "historical" / "e024b_cap_fail_movers.csv"
OUT_PAIRS = ROOT / "records" / "historical" / "e025_swap_pairs.csv"
OUT_TXT = ROOT / "records" / "historical" / "e025_swap_ranking_summary.txt"
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}


def _spearman(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    rx = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: xs[i]), start=1)}
    ry = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: ys[i]), start=1)}
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return 1.0 - (6.0 * d2) / (n * (n * n - 1))


def load_rows() -> list[dict]:
    if not SRC.exists():
        raise SystemExit(f"missing {SRC}; run scripts/e024b_cap_fail_movers.py first")
    with SRC.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["gw"] = int(r["gw"])
        r["player_id"] = int(r["player_id"])
        r["q"] = float(r["q"])
        r["mu_delta"] = float(r["mu_delta"])
        r["decision_utility"] = float(r["decision_utility"])
        r["actual_minutes"] = float(r["actual_minutes"])
        r["actual_points"] = float(r["actual_points"])
        r["ctrl_mu"] = float(r["ctrl_mu"])
        r["treat_mu"] = float(r["treat_mu"])
        r["packaged_u"] = float(r["packaged_u"])
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
                du = e["decision_utility"] - left["decision_utility"]
                dpts = e["actual_points"] - left["actual_points"]
                both60 = int(e["actual_minutes"] >= 60 and left["actual_minutes"] >= 60)
                both_play = int(e["actual_minutes"] > 0 and left["actual_minutes"] > 0)
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
                    "du": round(du, 4),
                    "dpts": round(dpts, 4),
                    "enter_u": e["decision_utility"],
                    "left_u": left["decision_utility"],
                    "enter_pts": e["actual_points"],
                    "left_pts": left["actual_points"],
                    "enter_mins": e["actual_minutes"],
                    "left_mins": left["actual_minutes"],
                    "enter_mu_delta": e["mu_delta"],
                    "both60": both60,
                    "both_play": both_play,
                    "model_pref_enter": int(du > 0),
                    "actual_pref_enter": int(dpts > 0),
                    "tie_pts": int(dpts == 0),
                })
    return pairs


def summarize(rows: list[dict], pairs: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E025: Cap-FAIL vs Cap-PASS swap ranking concordance")
    lines.append("Within-GW entered × left pairs from E024b movers; primary = both ≥60")
    lines.append("")

    def pair_block(label: str, subset: list[dict]) -> None:
        n = len(subset)
        if not n:
            lines.append(f"{label}: n=0")
            return
        mean_du = statistics.mean(p["du"] for p in subset)
        mean_dpts = statistics.mean(p["dpts"] for p in subset)
        nontie = [p for p in subset if not p["tie_pts"]]
        win = 100.0 * sum(p["actual_pref_enter"] for p in nontie) / len(nontie) if nontie else float("nan")
        model_pref = [p for p in subset if p["model_pref_enter"] and not p["tie_pts"]]
        conc = (
            100.0 * sum(p["actual_pref_enter"] for p in model_pref) / len(model_pref)
            if model_pref else float("nan")
        )
        # ranking error: model prefers enter, actual prefers left
        err = [p for p in subset if p["model_pref_enter"] and p["dpts"] < 0]
        mean_err_du = statistics.mean(p["du"] for p in err) if err else float("nan")
        mean_err_dpts = statistics.mean(p["dpts"] for p in err) if err else float("nan")
        lines.append(
            f"{label}: n={n} mean_dU={mean_du:.3f} mean_dpts={mean_dpts:.3f} "
            f"entrant_win%={win:.1f} (nontie={len(nontie)}) "
            f"concordance%={conc:.1f} (model_pref_nontie={len(model_pref)}) "
            f"rank_err_n={len(err)} mean_dU|err={mean_err_du:.3f} mean_dpts|err={mean_err_dpts:.3f}"
        )

    for gate in ("FAIL", "PASS"):
        g = [p for p in pairs if p["e024_gate"] == gate]
        g60 = [p for p in g if p["both60"]]
        gplay = [p for p in g if p["both_play"]]
        lines.append(f"=== {gate} pairs ===")
        pair_block(f"  {gate} all pairs", g)
        pair_block(f"  {gate} both_play", gplay)
        pair_block(f"  {gate} both60", g60)
        # lift tails among both60
        for thresh in (0.5, 1.0):
            hi = [p for p in g60 if p["enter_mu_delta"] >= thresh]
            pair_block(f"  {gate} both60 enter_muD>={thresh}", hi)
        lines.append("")

    # Spearman(U, pts) on movers who played 60+, by gate × movement
    lines.append("=== Spearman(decision_U, pts) among movers with mins≥60 ===")
    for gate in ("FAIL", "PASS"):
        for movement in ("entered", "left"):
            cell = [
                r for r in rows
                if r["season"] in (FAIL_SEASONS if gate == "FAIL" else PASS_SEASONS)
                and r["movement"] == movement
                and r["actual_minutes"] >= 60
            ]
            if len(cell) < 3:
                lines.append(f"  {gate} {movement}: n={len(cell)} spearman=nan")
                continue
            sp = _spearman(
                [r["decision_utility"] for r in cell],
                [r["actual_points"] for r in cell],
            )
            lines.append(f"  {gate} {movement}: n={len(cell)} spearman={sp:.3f}")
        pool = [
            r for r in rows
            if r["season"] in (FAIL_SEASONS if gate == "FAIL" else PASS_SEASONS)
            and r["actual_minutes"] >= 60
        ]
        sp = _spearman(
            [r["decision_utility"] for r in pool],
            [r["actual_points"] for r in pool],
        ) if len(pool) >= 3 else float("nan")
        lines.append(f"  {gate} entered∪left: n={len(pool)} spearman={sp:.3f}")
        lines.append("")

    # Same-position both60 (cleaner ILP substitute pairs)
    lines.append("=== both60 same-position pairs ===")
    for gate in ("FAIL", "PASS"):
        same = [
            p for p in pairs
            if p["e024_gate"] == gate and p["both60"] and p["enter_pos"] == p["left_pos"]
        ]
        pair_block(f"  {gate} both60 same_pos", same)

    text = "\n".join(lines) + "\n"
    print(text)
    return text


def main() -> None:
    print("[e025] swap ranking concordance on E024b movers; diagnostic only")
    rows = load_rows()
    pairs = build_pairs(rows)
    fields = [
        "season", "e024_gate", "gw", "enter_id", "enter_name", "enter_pos",
        "left_id", "left_name", "left_pos", "du", "dpts", "enter_u", "left_u",
        "enter_pts", "left_pts", "enter_mins", "left_mins", "enter_mu_delta",
        "both60", "both_play", "model_pref_enter", "actual_pref_enter", "tie_pts",
    ]
    OUT_PAIRS.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PAIRS.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(pairs)
    print(f"Wrote {OUT_PAIRS} ({len(pairs)} pairs)")
    summary = summarize(rows, pairs)
    OUT_TXT.write_text(summary, encoding="utf-8")
    print(f"Wrote {OUT_TXT}")


if __name__ == "__main__":
    main()
