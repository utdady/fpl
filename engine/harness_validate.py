"""Harness validation: prove as-of-T snapshots contain no future information.

Usage:
    python -m engine.harness_validate --season 2025-26 --gw 1
    python -m engine.harness_validate --season 2024-25 --gw 1
"""
from __future__ import annotations

import argparse
import sys

from engine.harness import SUPPORTED_SEASONS, aggregate_gw_stats, build_snapshot, ensure_vaastav, gw_prices


class ValidationResult:
    def __init__(self) -> None:
        self.checks: list[tuple[str, bool, str]] = []

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((name, ok, detail))

    @property
    def passed(self) -> bool:
        return all(ok for _, ok, _ in self.checks)

    def report(self) -> str:
        lines = ["--- Harness validation ---"]
        for name, ok, detail in self.checks:
            mark = "PASS" if ok else "FAIL"
            extra = f"  ({detail})" if detail else ""
            lines.append(f"  [{mark}] {name}{extra}")
        lines.append("")
        lines.append("RESULT: PASS" if self.passed else "RESULT: FAIL")
        return "\n".join(lines)


def validate_snapshot(season: str, gw: int) -> ValidationResult:
    ensure_vaastav((season,))
    snap = build_snapshot(season, as_of_gw=gw)
    res = ValidationResult()

    res.add("player count >= 500", len(snap.players) >= 500, str(len(snap.players)))
    res.add("all ep_next excluded", all(p.ep_next is None for p in snap.players))
    res.add("all chance fields excluded", all(p.chance_this is None and p.chance_next is None for p in snap.players))

    if gw == 1:
        zero_mins = sum(1 for p in snap.players if p.minutes == 0)
        res.add("pre-GW1 current-season minutes are zero", zero_mins == len(snap.players), f"{zero_mins}/{len(snap.players)}")
        zero_pts = sum(1 for p in snap.players if p.total_points == 0)
        res.add("pre-GW1 current-season points are zero", zero_pts == len(snap.players), f"{zero_pts}/{len(snap.players)}")
    else:
        agg = aggregate_gw_stats(season, through_gw=gw - 1)
        mism = 0
        for p in snap.players:
            a = agg.get(p.id)
            if a and p.minutes != a.minutes:
                mism += 1
        res.add("minutes match cumulative through GW-1", mism == 0, f"mismatches={mism}")

    prices = gw_prices(season, gw)
    if prices:
        mism = 0
        for p in snap.players:
            if p.id in prices and p.now_cost != prices[p.id]:
                mism += 1
        res.add("prices match GW opening values", mism == 0, f"mismatches={mism}")
    else:
        res.add("GW price file exists", False, f"missing gw{gw}.csv")

    target_fixtures = [f for f in snap.fixtures if f.event == gw]
    res.add("fixtures exist for target GW", len(target_fixtures) > 0, str(len(target_fixtures)))
    unfinished = [f for f in target_fixtures if not f.finished]
    res.add("target GW fixtures marked unfinished", len(unfinished) == len(target_fixtures))

    next_ev = snap.next_event()
    res.add("next_event points at target GW", next_ev.id == gw, f"got {next_ev.id}")

    # Plausibility: top projected names should not be empty / all zeros
    with_rates = [p for p in snap.players if p.xg90 > 0 or p.minutes > 0]
    res.add("players have rate signal", len(with_rates) > 100, str(len(with_rates)))

    return res


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate historical harness as-of-T discipline.")
    parser.add_argument("--season", required=True, choices=SUPPORTED_SEASONS)
    parser.add_argument("--gw", type=int, default=1, help="Target gameweek to predict")
    args = parser.parse_args()

    print(f"[harness_validate] season={args.season} target_gw={args.gw}")
    result = validate_snapshot(args.season, args.gw)
    print(result.report())
    if not result.passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
