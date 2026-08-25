"""V2A-M: leave-one-season-out bucket recalibration of V1 p_start.

Does not change role logic, rates, fixtures, or ILP. No new-club prior.
Fit mapping on other seasons' frozen V1 records; apply before the minutes mixture
enters the Monte Carlo projection.
"""
from __future__ import annotations

import csv
from pathlib import Path

from engine.metrics import record_path, safe_float

# Same buckets as engine/obs.py E009
BUCKETS = [
    ("0.90-1.00", 0.90, 1.01),
    ("0.80-0.90", 0.80, 0.90),
    ("0.70-0.80", 0.70, 0.80),
    ("0.60-0.70", 0.60, 0.70),
    ("<0.60", 0.00, 0.60),
]


def bucket_name(p: float) -> str:
    for name, lo, hi in BUCKETS:
        if lo <= p < hi:
            return name
    return "<0.60"


def load_v1_scored_rows(season: str) -> list[dict]:
    out: list[dict] = []
    for gw in range(1, 39):
        path = record_path(gw, season=season)
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("actual_points") in (None, ""):
                    continue
                out.append(row)
    return out


def fit_bucket_map(train_seasons: list[str]) -> dict[str, float]:
    """Map V1 p_start bucket -> empirical P(start) on train seasons only."""
    counts: dict[str, list[int]] = {b[0]: [] for b in BUCKETS}
    for season in train_seasons:
        for row in load_v1_scored_rows(season):
            ps = safe_float(row.get("p_start"))
            if ps is None:
                continue
            did = row.get("did_start")
            if did in (None, ""):
                continue
            counts[bucket_name(ps)].append(int(float(did)))
    mapping: dict[str, float] = {}
    for name, _, _ in BUCKETS:
        ys = counts[name]
        if len(ys) < 30:
            # Fall back toward bucket midpoint if sparse
            lo = next(b[1] for b in BUCKETS if b[0] == name)
            hi = next(b[2] for b in BUCKETS if b[0] == name)
            mapping[name] = min(0.97, 0.5 * (lo + min(hi, 1.0)))
        else:
            mapping[name] = sum(ys) / len(ys)
    return mapping


def fit_loso_map(eval_season: str, all_seasons: tuple[str, ...]) -> dict[str, float]:
    train = [s for s in all_seasons if s != eval_season]
    if not train:
        raise ValueError("LOSO requires at least one training season")
    return fit_bucket_map(train)


def recalibrate_minutes(
    p_start: float,
    p_sub: float,
    mapping: dict[str, float],
) -> tuple[float, float, float]:
    """Replace p_start with LOSO empirical rate for its V1 bucket; rescale sub/60."""
    new_ps = float(mapping[bucket_name(p_start)])
    new_ps = min(0.97, max(0.0, new_ps))
    leftover = max(0.0, 1.0 - new_ps)
    old_leftover = max(1e-9, 1.0 - p_start)
    new_sub = min(leftover, p_sub * (leftover / old_leftover))
    new_p60 = min(0.97, new_ps * 0.93 + new_sub * 0.08)
    return new_ps, new_sub, new_p60


def mapping_report(mapping: dict[str, float]) -> str:
    lines = ["V2A-M LOSO p_start bucket map (empirical start rate):"]
    for name, _, _ in BUCKETS:
        lines.append(f"  {name:12} -> {100 * mapping[name]:5.1f}%")
    return "\n".join(lines)
