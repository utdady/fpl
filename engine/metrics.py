"""Shared prediction scoring metrics for live and historical capture."""
from __future__ import annotations

import csv
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

PRED_COLUMNS = [
    "gw", "player_id", "web_name", "team_id", "position", "now_cost",
    "mu", "sigma", "p_start", "p_sub", "p_60", "p_10_plus", "n_fixtures",
    "actual_points", "actual_minutes", "did_start", "captured_at", "scored_at",
]


def record_path(gw: int, season: str | None = None) -> Path:
    if season:
        return Path("records") / "historical" / season / f"gw{gw:02d}_v1.0.csv"
    return Path("records") / f"gw{gw:02d}_v1.0.csv"


def scores_csv(season: str | None = None) -> Path:
    if season:
        return Path("records") / "historical" / season / "scores.csv"
    return Path("records") / "scores.csv"


def safe_float(val) -> float | None:
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def spearman(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")

    def ranks(vals):
        sorted_idx = sorted(range(n), key=lambda i: vals[i])
        r = [0.0] * n
        for rank, i in enumerate(sorted_idx, 1):
            r[i] = rank
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx = statistics.mean(rx)
    my = statistics.mean(ry)
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den = math.sqrt(
        sum((rx[i] - mx) ** 2 for i in range(n))
        * sum((ry[i] - my) ** 2 for i in range(n))
    )
    return num / den if den else 0.0


def calibration_error(pairs: list[tuple[float, int]], n_bins: int = 5) -> float:
    if not pairs:
        return float("nan")
    bins: list[list] = [[] for _ in range(n_bins)]
    for prob, outcome in pairs:
        b = min(int(prob * n_bins), n_bins - 1)
        bins[b].append((prob, outcome))
    total = len(pairs)
    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        mean_prob = statistics.mean(p for p, _ in bucket)
        mean_out = statistics.mean(o for _, o in bucket)
        ece += (len(bucket) / total) * abs(mean_prob - mean_out)
    return ece


def summarize_rows(rows: list[dict], gw: int) -> dict[str, float] | None:
    scored = [r for r in rows if r.get("actual_points") not in (None, "")]
    if not scored:
        return None
    errors, sq_errors, pairs = [], [], []
    p_start_pairs: list[tuple[float, int]] = []
    p10_pairs: list[tuple[float, int]] = []
    for r in scored:
        mu = safe_float(r["mu"])
        act = safe_float(r["actual_points"])
        if mu is None or act is None:
            continue
        e = act - mu
        errors.append(e)
        sq_errors.append(e ** 2)
        pairs.append((mu, act))
        p_start = safe_float(r["p_start"])
        did_start = safe_float(r["did_start"])
        if p_start is not None and did_start is not None:
            p_start_pairs.append((p_start, int(did_start)))
        p10 = safe_float(r["p_10_plus"])
        if p10 is not None:
            p10_pairs.append((p10, int(act >= 10)))
    if not errors:
        return None
    return {
        "gw": gw,
        "n": len(errors),
        "mae": statistics.mean(abs(e) for e in errors),
        "rmse": math.sqrt(statistics.mean(sq_errors)),
        "bias": statistics.mean(errors),
        "spearman": spearman([mu for mu, _ in pairs], [act for _, act in pairs]),
        "p_start_ece": calibration_error(p_start_pairs),
        "p10_ece": calibration_error(p10_pairs),
    }


def print_summary(summary: dict[str, float]) -> None:
    gw = int(summary["gw"])
    n = int(summary["n"])
    print()
    print(f"=== GW {gw} Prediction Scorecard (n={n}) ===")
    print(f"  MAE:              {summary['mae']:.3f}")
    print(f"  RMSE:             {summary['rmse']:.3f}")
    print(f"  Bias (mean err):  {summary['bias']:+.3f}")
    print(f"  Spearman r:       {summary['spearman']:.3f}")
    print(f"  p_start ECE:      {summary['p_start_ece']:.3f}")
    print(f"  p_10_plus ECE:    {summary['p10_ece']:.3f}")
    print()


def append_scores_row(summary: dict[str, float], season: str | None = None) -> Path:
    path = scores_csv(season)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["gw", "n", "mae", "rmse", "bias", "spearman", "scored_at"]
    header_needed = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if header_needed:
            writer.writeheader()
        writer.writerow({
            "gw": int(summary["gw"]),
            "n": int(summary["n"]),
            "mae": round(summary["mae"], 4),
            "rmse": round(summary["rmse"], 4),
            "bias": round(summary["bias"], 4),
            "spearman": round(summary["spearman"], 4),
            "scored_at": datetime.now(timezone.utc).isoformat(),
        })
    return path
