"""B0-B3 historical baseline comparison across gameweeks."""
from __future__ import annotations

import argparse
import csv
import statistics
from dataclasses import dataclass
from pathlib import Path

from engine.harness import (
    SUPPORTED_SEASONS,
    build_snapshot,
    ensure_vaastav,
    gw_actuals,
    prior_points_by_element,
    prior_pp90_by_element,
)
from engine.harness_baselines import (
    baseline_b0_xp,
    baseline_b1_gw_prediction,
    baseline_b1_season_points,
    baseline_b2_gw_prediction,
    baseline_b2_naive_pp90,
    baseline_b3_v1,
)
from engine.metrics import spearman
from engine.models import PlayerProjection
from engine.optimize import solve_squad
from engine.project import project_all


@dataclass
class GWMetrics:
    gw: int
    model: str
    n: int
    mae: float
    rmse: float
    bias: float
    spearman: float
    xi_points: float | None = None
    captain_points: float | None = None


def _player_metrics(preds: dict[int, float], actuals: dict[int, int]) -> tuple[int, float, float, float, float]:
    errors = []
    pairs = []
    for pid, pred in preds.items():
        act = actuals.get(pid)
        if act is None:
            continue
        errors.append(act - pred)
        pairs.append((pred, act))
    if not errors:
        return 0, float("nan"), float("nan"), float("nan"), float("nan")
    mae = statistics.mean(abs(e) for e in errors)
    rmse = (statistics.mean(e ** 2 for e in errors)) ** 0.5
    bias = statistics.mean(errors)
    sp = spearman([p for p, _ in pairs], [a for _, a in pairs]) if len(pairs) >= 2 else float("nan")
    return len(errors), mae, rmse, bias, sp


def _xi_actual_points(solution, actuals: dict[int, dict]) -> float:
    total = 0.0
    for p in solution.xi:
        act = actuals.get(p.id, {}).get("actual_points", 0) or 0
        total += act
        if p.id == solution.captain.id:
            total += act
    return total


def evaluate_gw(season: str, gw: int, strategy: str = "balanced") -> list[GWMetrics]:
    ensure_vaastav((season,))
    snapshot = build_snapshot(season, as_of_gw=gw)
    v1 = project_all(snapshot, horizon=1, strategy=strategy, minutes_version="v1")
    prior_pts = prior_points_by_element(season)
    prior_pp90 = prior_pp90_by_element(season)
    actuals_raw = gw_actuals(season, gw)
    actual_pts = {pid: d["actual_points"] for pid, d in actuals_raw.items()}

    mae_models: list[tuple[str, dict[int, float], list[PlayerProjection]]] = [
        ("B0_xp", {p.player.id: p.next_mu for p in baseline_b0_xp(season, gw, snapshot)}, baseline_b0_xp(season, gw, snapshot)),
        ("B1_season_pts", baseline_b1_gw_prediction(snapshot, gw, prior_pts), baseline_b1_season_points(snapshot, gw, prior_pts)),
        ("B2_pp90", baseline_b2_gw_prediction(snapshot, gw, prior_pp90), baseline_b2_naive_pp90(snapshot, gw, prior_pp90)),
        ("B3_v1", {p.player.id: p.next_mu for p in v1}, baseline_b3_v1(v1)),
    ]

    out: list[GWMetrics] = []
    for name, preds, projs in mae_models:
        n, mae, rmse, bias, sp = _player_metrics(preds, actual_pts)
        xi_points = captain_points = None
        try:
            sol = solve_squad(snapshot, projs, strategy=strategy)
            xi_points = _xi_actual_points(sol, actuals_raw)
            captain_points = actuals_raw.get(sol.captain.id, {}).get("actual_points", 0)
        except RuntimeError:
            pass
        out.append(GWMetrics(gw, name, n, mae, rmse, bias, sp, xi_points, captain_points))
    return out


def aggregate(metrics: list[GWMetrics]) -> dict[str, dict[str, float]]:
    by_model: dict[str, list[GWMetrics]] = {}
    for m in metrics:
        by_model.setdefault(m.model, []).append(m)
    summary = {}
    for model, rows in by_model.items():
        summary[model] = {
            "gws": len(rows),
            "mae": statistics.mean(r.mae for r in rows),
            "rmse": statistics.mean(r.rmse for r in rows),
            "bias": statistics.mean(r.bias for r in rows),
            "spearman": statistics.mean(r.spearman for r in rows if r.spearman == r.spearman),
            "xi_points": statistics.mean(r.xi_points for r in rows if r.xi_points is not None),
            "captain_points": statistics.mean(r.captain_points for r in rows if r.captain_points is not None),
        }
    return summary


def write_report(season: str, metrics: list[GWMetrics], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["gw", "model", "n", "mae", "rmse", "bias", "spearman", "xi_points", "captain_points"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for m in metrics:
            w.writerow({
                "gw": m.gw,
                "model": m.model,
                "n": m.n,
                "mae": round(m.mae, 4),
                "rmse": round(m.rmse, 4),
                "bias": round(m.bias, 4),
                "spearman": round(m.spearman, 4),
                "xi_points": round(m.xi_points, 2) if m.xi_points is not None else "",
                "captain_points": round(m.captain_points, 2) if m.captain_points is not None else "",
            })


def print_summary_table(season: str, summary: dict[str, dict[str, float]]) -> None:
    print()
    print(f"=== {season} B0-B3 season aggregate (38 GWs) ===")
    print(f"{'model':14} {'MAE':>6} {'RMSE':>6} {'Spear':>6} {'XI+Cap':>7} {'Captain':>7}")
    for model in ["B0_xp", "B1_season_pts", "B2_pp90", "B3_v1"]:
        s = summary.get(model)
        if not s:
            continue
        print(f"{model:14} {s['mae']:6.3f} {s['rmse']:6.3f} {s['spearman']:6.3f} {s['xi_points']:7.2f} {s['captain_points']:7.2f}")
    print()
    print("Player MAE: per-GW point predictions vs actual GW points.")
    print("XI+Cap: ILP best-XI actual points with captain doubled.")
    print("B0_xp uses Vaastav xP (benchmark only; possible timing leakage).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare B0-B3 baselines on historical data.")
    parser.add_argument("--season", required=True, choices=SUPPORTED_SEASONS)
    parser.add_argument("--gw", type=int)
    parser.add_argument("--from-gw", type=int, dest="from_gw", default=1)
    parser.add_argument("--to-gw", type=int, dest="to_gw", default=38)
    parser.add_argument("--strategy", default="balanced")
    args = parser.parse_args()

    gws = [args.gw] if args.gw else range(args.from_gw, args.to_gw + 1)
    all_metrics: list[GWMetrics] = []
    for gw in gws:
        print(f"[harness_compare] {args.season} GW{gw} ...")
        all_metrics.extend(evaluate_gw(args.season, gw, strategy=args.strategy))

    out_path = Path("records") / "historical" / args.season / "b0_b3_comparison.csv"
    write_report(args.season, all_metrics, out_path)
    print_summary_table(args.season, aggregate(all_metrics))
    print(f"[harness_compare] Wrote {out_path}")


if __name__ == "__main__":
    main()
