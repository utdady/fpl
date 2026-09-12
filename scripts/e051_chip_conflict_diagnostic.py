"""E051: Joint chip conflict diagnostic (measurement only).

Consumes frozen single-chip gate outputs (t*) as inputs — does not retune
any chip U or g*. No joint scheduler on this card.

Primary path: read t* from historical ROI season CSVs (frozen gate artifacts).
Optional: --recompute SEASON calls recommend_historical (slow; WC especially).

Usage:
    python scripts/e051_chip_conflict_diagnostic.py
    python scripts/e051_chip_conflict_diagnostic.py --recompute 2024-25
"""
from __future__ import annotations

import argparse
import csv
import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = Path("records") / "historical"
SEASONS = ("2022-23", "2023-24", "2024-25", "2025-26")
CHIPS = ("TC", "BB", "FH", "WC")
# Frozen report-only priority (LAB_LOG E051) — not a product claim.
PRIORITY = ("WC", "FH", "TC", "BB")
HARD_PAIRS = {frozenset({"FH", "WC"})}  # both resquad
SOFT_PAIRS = {frozenset({"TC", "BB"})}  # real FPL can share GW; still report

ARTIFACTS = {
    "TC": OUT_DIR / "e040_triple_captain_roi_season.csv",
    "BB": OUT_DIR / "e041_bench_boost_roi_season.csv",
    "FH": OUT_DIR / "e046_free_hit_roi_season.csv",
    "WC": OUT_DIR / "e050_wildcard_roi_season.csv",
}


def load_t_stars_from_csv() -> dict[str, dict[str, int]]:
    """season -> {chip: t_star} from frozen gate season CSVs."""
    by_chip: dict[str, dict[str, int]] = {}
    for chip, path in ARTIFACTS.items():
        if not path.exists():
            raise FileNotFoundError(f"missing frozen gate artifact: {path}")
        with path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        by_chip[chip] = {r["season"]: int(r["t_star"]) for r in rows if r.get("t_star")}
    out: dict[str, dict[str, int]] = {}
    for season in SEASONS:
        out[season] = {}
        for chip in CHIPS:
            if season not in by_chip[chip]:
                raise KeyError(f"{chip} artifact missing season {season}")
            out[season][chip] = by_chip[chip][season]
    return out


def recompute_t_stars(season: str) -> dict[str, int]:
    """Call frozen recommend_historical for one season (slow)."""
    from engine.e040_tc_policy import recommend_historical as tc_rec
    from engine.e041_bb_policy import recommend_historical as bb_rec
    from engine.e046_fh_policy import recommend_historical as fh_rec
    from engine.e050_wc_policy import recommend_historical as wc_rec

    print(f"  recompute TC {season}…", flush=True)
    tc = tc_rec(season)
    print(f"  recompute BB {season}…", flush=True)
    bb = bb_rec(season)
    print(f"  recompute FH {season}…", flush=True)
    fh = fh_rec(season)
    print(f"  recompute WC {season}… (forward U_WC; slow)", flush=True)
    wc = wc_rec(season)
    return {
        "TC": int(tc.t_star),
        "BB": int(bb.t_star),
        "FH": int(fh.t_star),
        "WC": int(wc.t_star),
    }


def same_gw_pairs(t_by_chip: dict[str, int]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for a, b in itertools.combinations(CHIPS, 2):
        if t_by_chip[a] == t_by_chip[b]:
            pairs.append((a, b))
    return pairs


def multi_collision(t_by_chip: dict[str, int]) -> bool:
    from collections import Counter

    return any(c >= 3 for c in Counter(t_by_chip.values()).values())


def priority_kept(t_by_chip: dict[str, int]) -> tuple[list[str], list[str]]:
    """Apply at-most-one-chip-per-GW with frozen WC>FH>TC>BB priority.

    Returns (kept chips, dropped chips).
    """
    # Sort chips by priority rank; claim GWs greedily.
    rank = {c: i for i, c in enumerate(PRIORITY)}
    ordered = sorted(CHIPS, key=lambda c: (rank[c], t_by_chip[c]))
    used_gws: set[int] = set()
    kept: list[str] = []
    dropped: list[str] = []
    for chip in ordered:
        gw = t_by_chip[chip]
        if gw in used_gws:
            dropped.append(chip)
        else:
            kept.append(chip)
            used_gws.add(gw)
    return kept, dropped


def analyze(t_stars: dict[str, dict[str, int]]) -> dict:
    season_rows: list[dict] = []
    pair_counts = {frozenset(p): 0 for p in itertools.combinations(CHIPS, 2)}
    seasons_with_collision = 0
    seasons_with_hard = 0
    seasons_with_multi = 0

    for season in SEASONS:
        t = t_stars[season]
        pairs = same_gw_pairs(t)
        multi = multi_collision(t)
        hard = [p for p in pairs if frozenset(p) in HARD_PAIRS]
        soft = [p for p in pairs if frozenset(p) in SOFT_PAIRS]
        other = [
            p
            for p in pairs
            if frozenset(p) not in HARD_PAIRS and frozenset(p) not in SOFT_PAIRS
        ]
        if pairs:
            seasons_with_collision += 1
        if hard:
            seasons_with_hard += 1
        if multi:
            seasons_with_multi += 1
        for p in pairs:
            pair_counts[frozenset(p)] += 1
        kept, dropped = priority_kept(t)
        season_rows.append({
            "season": season,
            "t_TC": t["TC"],
            "t_BB": t["BB"],
            "t_FH": t["FH"],
            "t_WC": t["WC"],
            "pairwise_count": len(pairs),
            "pairs": "|".join(f"{a}-{b}" for a, b in pairs) if pairs else "",
            "hard_FH_WC": int(bool(hard)),
            "soft_TC_BB": int(bool(soft)),
            "other_pairs": "|".join(f"{a}-{b}" for a, b in other) if other else "",
            "multi": int(multi),
            "priority_kept": "|".join(kept),
            "priority_dropped": "|".join(dropped) if dropped else "",
            "indep_naive_feasible": int(len(pairs) == 0),
        })

    n = len(SEASONS)
    collision_rate = seasons_with_collision / n
    # Branch (LAB_LOG E051): rate==0 → negligible; else conflicts present.
    if seasons_with_collision == 0:
        verdict = "NEGLIGIBLE"
        branch = "DO_NOT_OPEN_E051A"
    else:
        verdict = "CONFLICTS_PRESENT"
        branch = "E051A_EARNED_FOR_RESOLUTION"
    return {
        "season_rows": season_rows,
        "pair_counts": pair_counts,
        "collision_rate": collision_rate,
        "seasons_with_collision": seasons_with_collision,
        "seasons_with_hard": seasons_with_hard,
        "seasons_with_multi": seasons_with_multi,
        "verdict": verdict,
        "branch": branch,
    }


def format_report(result: dict, *, source: str) -> str:
    lines: list[str] = []
    lines.append("E051: Joint chip conflict diagnostic (measurement only)")
    lines.append(f"Source: {source}")
    lines.append("Inputs: frozen E040-A / E041-A / E046-A / E050-A t* (no U retune)")
    lines.append("Hard conflict pair: FH-WC (both resquad). Soft report: TC-BB.")
    lines.append("Priority (report-only, not product): WC > FH > TC > BB")
    lines.append("Cap opportunity: NOT computed — single-chip ROI Caps are not")
    lines.append("  additive across ownership models; unified Cap = E051-A if earned.")
    lines.append("")
    lines.append("=== Per season t* ===")
    for r in result["season_rows"]:
        lines.append(
            f"  {r['season']}: TC={r['t_TC']} BB={r['t_BB']} "
            f"FH={r['t_FH']} WC={r['t_WC']} | "
            f"pairs={r['pairwise_count']} [{r['pairs'] or '-'}] "
            f"hard_FH_WC={r['hard_FH_WC']} soft_TC_BB={r['soft_TC_BB']} "
            f"multi={r['multi']}"
        )
        if r["priority_dropped"]:
            lines.append(
                f"           priority kept=[{r['priority_kept']}] "
                f"dropped=[{r['priority_dropped']}] "
                f"naive_feasible={r['indep_naive_feasible']}"
            )
        else:
            lines.append(
                f"           priority kept=all naive_feasible={r['indep_naive_feasible']}"
            )
    lines.append("")
    lines.append("=== Pair frequencies (seasons with SAME_GW) ===")
    for pair in itertools.combinations(CHIPS, 2):
        fs = frozenset(pair)
        tag = ""
        if fs in HARD_PAIRS:
            tag = " [HARD]"
        elif fs in SOFT_PAIRS:
            tag = " [SOFT]"
        lines.append(f"  {pair[0]}-{pair[1]}: {result['pair_counts'][fs]}/4{tag}")
    lines.append("")
    lines.append("=== Aggregate ===")
    lines.append(
        f"  seasons_with_any_collision: {result['seasons_with_collision']}/4 "
        f"(rate={result['collision_rate']:.2f})"
    )
    lines.append(f"  seasons_with_hard_FH_WC: {result['seasons_with_hard']}/4")
    lines.append(f"  seasons_with_multi(>=3): {result['seasons_with_multi']}/4")
    lines.append("")
    lines.append("=== PRIMARY BRANCH ===")
    lines.append(f"  VERDICT: {result['verdict']}")
    lines.append(f"  BRANCH:  {result['branch']}")
    if result["verdict"] == "NEGLIGIBLE":
        lines.append("  CALL: conflicts negligible — do NOT open E051-A scheduler")
    else:
        lines.append(
            "  CALL: conflicts present — E051-A may freeze ONE resolution class "
            "+ unified Cap model; do NOT retune chip U/g*; do NOT promote "
            "WC>FH>TC>BB without E051-A"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="E051 chip conflict diagnostic")
    parser.add_argument(
        "--recompute",
        choices=SEASONS,
        default=None,
        help="Recompute one season via recommend_historical (slow)",
    )
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    t_stars = load_t_stars_from_csv()
    source = "frozen gate season CSVs (E040/E041/E046/E050)"
    if args.recompute:
        print(f"[e051] recompute override for {args.recompute}", flush=True)
        t_stars[args.recompute] = recompute_t_stars(args.recompute)
        source = f"CSV + recommend_historical({args.recompute})"

    result = analyze(t_stars)
    text = format_report(result, source=source)
    print(text, flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    season_path = OUT_DIR / "e051_chip_conflict_season.csv"
    fields = list(result["season_rows"][0].keys())
    with season_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(result["season_rows"])

    summary_path = OUT_DIR / "e051_chip_conflict_summary.txt"
    summary_path.write_text(text, encoding="utf-8")
    verdict_path = OUT_DIR / "e051_chip_conflict_verdict.txt"
    verdict_path.write_text(
        f"VERDICT: {result['verdict']}\n"
        f"BRANCH: {result['branch']}\n"
        f"collision_rate={result['collision_rate']:.4f}\n"
        f"seasons_with_collision={result['seasons_with_collision']}/4\n"
        f"seasons_with_hard_FH_WC={result['seasons_with_hard']}/4\n",
        encoding="utf-8",
    )
    print(f"Wrote {season_path}", flush=True)
    print(f"Wrote {summary_path}", flush=True)
    print(f"Wrote {verdict_path}", flush=True)


if __name__ == "__main__":
    main()
