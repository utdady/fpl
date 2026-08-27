"""Calibrate frozen H-PACK1 ε from control-only one-exclusion gaps.

ε = P90 of pooled (U0* - U0(exclude player i)) across all historical GWs.
Control stack only: v2am_s + rates=v1 + fixtures=v1, objective=next.
No treatment data. No Cap peeking.

Usage:
    python scripts/calibrate_hpack1_epsilon.py
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.harness import SUPPORTED_SEASONS, build_snapshot, ensure_vaastav
from engine.metrics import record_path
from engine.project import project_all
from engine.stability_selection import (
    EPSILON_PERCENTILE,
    control_one_exclusion_gaps,
    write_epsilon,
)

SEED = 7
STRATEGY = "balanced"


def main() -> None:
    ensure_vaastav(SUPPORTED_SEASONS)
    all_gaps: list[float] = []
    n_gw = 0
    print(
        f"[hpack1] calibrating ε = P{EPSILON_PERCENTILE} control one-exclusion gaps; "
        "no treatment peek"
    )
    for season in SUPPORTED_SEASONS:
        for gw in range(1, 39):
            if not record_path(gw, season=season).exists():
                continue
            snap = build_snapshot(season, as_of_gw=gw)
            v1 = project_all(
                snap,
                horizon=1,
                strategy=STRATEGY,
                seed=SEED,
                minutes_version="v2am_s",
                rates_version="v1",
                fixtures_version="v1",
            )
            try:
                u0_star, gaps = control_one_exclusion_gaps(snap, v1, STRATEGY, objective="next")
            except RuntimeError as e:
                print(f"  skip {season} GW{gw}: {e}")
                continue
            all_gaps.extend(gaps)
            n_gw += 1
            if gw % 10 == 1:
                print(f"  [{season}] GW{gw} U0*={u0_star:.3f} gaps={len(gaps)}")

    if not all_gaps:
        raise SystemExit("no gaps collected")

    # P90 via order statistic
    sorted_gaps = sorted(all_gaps)
    idx = int(round((EPSILON_PERCENTILE / 100.0) * (len(sorted_gaps) - 1)))
    epsilon = sorted_gaps[idx]
    print(
        f"\nCollected {len(all_gaps)} gaps from {n_gw} GWs "
        f"mean={statistics.mean(all_gaps):.3f} "
        f"p50={statistics.median(all_gaps):.3f} "
        f"p{EPSILON_PERCENTILE}={epsilon:.3f}"
    )
    write_epsilon(epsilon, len(all_gaps))
    print("Wrote records/historical/hpack1_epsilon.json")


if __name__ == "__main__":
    main()
