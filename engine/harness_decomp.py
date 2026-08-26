"""V2 investigation: anomaly audit, nested regret, B0 gap, V1_GW1 counterfactual.

Usage:
    python -m engine.harness_decomp --season 2025-26 --from-gw 1 --to-gw 38
    python -m engine.harness_decomp --season 2024-25 --from-gw 1 --to-gw 38

Does not change production V1. Squad ILP default remains horizon utility.
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from engine.harness import SUPPORTED_SEASONS, build_snapshot, ensure_vaastav, gw_actuals, season_dir
from engine.harness_baselines import _fake, baseline_b0_xp
from engine.models import Player, PlayerProjection, Snapshot, SquadSolution
from engine.optimize import solve_squad, solve_xi, pick_captains
from engine.project import project_all


def _pts(actuals: dict[int, dict], pid: int) -> float:
    return float(actuals.get(pid, {}).get("actual_points", 0) or 0)


def xi_cap_points(xi: list[Player], captain: Player, actuals: dict[int, dict]) -> float:
    total = 0.0
    for p in xi:
        total += _pts(actuals, p.id)
    total += _pts(actuals, captain.id)
    return total


def best_captain(xi: list[Player], actuals: dict[int, dict]) -> Player:
    return max(xi, key=lambda p: _pts(actuals, p.id))


def actual_projections(snapshot: Snapshot, actuals: dict[int, dict]) -> list[PlayerProjection]:
    return [_fake(p, _pts(actuals, p.id)) for p in snapshot.players]


def by_id_actual(snapshot: Snapshot, actuals: dict[int, dict]) -> dict[int, PlayerProjection]:
    return {p.player.id: p for p in actual_projections(snapshot, actuals)}


# ---------------------------------------------------------------------------
# Structural anomaly (never uses V1/B0 scores)
# ---------------------------------------------------------------------------

def fixture_count(snapshot: Snapshot, gw: int) -> int:
    return sum(1 for f in snapshot.fixtures if f.event == gw)


def actuals_integrity(season: str, gw: int, actuals: dict[int, dict]) -> dict:
    path = season_dir(season) / "gws" / f"gw{gw}.csv"
    n_rows = 0
    ids: list[int] = []
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                n_rows += 1
                if row.get("element"):
                    try:
                        ids.append(int(float(row["element"])))
                    except (TypeError, ValueError):
                        pass
    n_unique = len(set(ids))
    n_dup = n_rows - n_unique if ids else 0
    n_minutes = sum(1 for d in actuals.values() if int(d.get("actual_minutes") or 0) > 0)
    return {
        "n_actual_rows": n_rows,
        "n_unique_actuals": n_unique,
        "n_duplicate_ids": max(0, n_dup),
        "n_with_minutes": n_minutes,
        "missing_file": not path.exists(),
    }


def classify_week(n_fixtures: int, integ: dict, n_snapshot: int) -> tuple[str, list[str]]:
    """evaluation_status from STRUCTURE only. Scores never enter this function."""
    flags: list[str] = []
    excluded: list[str] = []

    if integ["missing_file"] or integ["n_unique_actuals"] == 0:
        excluded.append("missing_actuals")
    join_floor = max(50, int(0.15 * n_snapshot))
    if integ["n_unique_actuals"] and integ["n_unique_actuals"] < join_floor:
        excluded.append("actuals_join_failure")
    if n_fixtures == 0 and integ["n_with_minutes"] == 0:
        excluded.append("no_fixtures_no_minutes")
    # Identical extra rows in Vaastav GW files are common junk, not evaluator failure.
    # Pathological duplication (more extra rows than unique players) is excluded.
    extra = integ["n_duplicate_ids"]
    if extra > max(20, integ["n_unique_actuals"]):
        excluded.append("pathological_duplicate_rows")
    elif extra > 5:
        flags.append("duplicate_gw_rows")

    if n_fixtures < 10:
        flags.append("bgw_or_short")
    if n_fixtures > 10:
        flags.append("dgw_or_long")
    if n_fixtures == 0:
        flags.append("zero_fixtures")

    if excluded:
        return "excluded", excluded + flags
    if flags:
        return "flagged", flags
    return "clean", []


@dataclass
class GWRow:
    season: str
    gw: int
    n_fixtures: int
    n_actual_rows: int
    n_unique_actuals: int
    n_duplicate_ids: int
    n_with_minutes: int
    n_snapshot: int
    evaluation_status: str
    structural_flags: str
    inspect_v1_lt_15: int = 0
    inspect_b0_gt_80: int = 0
    b0_xi_cap: float | None = None
    v1_xi_cap: float | None = None
    v1_gw1_xi_cap: float | None = None
    hindsight_oracle_cap: float | None = None
    squad_overlap: int | None = None
    xi_overlap: int | None = None
    hindsight_squad_regret: float | None = None
    hindsight_xi_regret: float | None = None
    hindsight_cap_regret: float | None = None
    vs_b0_gap: float | None = None
    solver_error: str = ""


def evaluate_gw(season: str, gw: int, strategy: str = "balanced") -> tuple[GWRow, list[dict]]:
    snapshot = build_snapshot(season, as_of_gw=gw)
    actuals = gw_actuals(season, gw)
    integ = actuals_integrity(season, gw, actuals)
    n_fx = fixture_count(snapshot, gw)
    status, flags = classify_week(n_fx, integ, len(snapshot.players))

    row = GWRow(
        season=season,
        gw=gw,
        n_fixtures=n_fx,
        n_actual_rows=integ["n_actual_rows"],
        n_unique_actuals=integ["n_unique_actuals"],
        n_duplicate_ids=integ["n_duplicate_ids"],
        n_with_minutes=integ["n_with_minutes"],
        n_snapshot=len(snapshot.players),
        evaluation_status=status,
        structural_flags=";".join(flags),
    )

    player_rows: list[dict] = []
    if status == "excluded":
        return row, player_rows

    v1 = project_all(snapshot, horizon=6, strategy=strategy, minutes_version="v1")
    b0 = baseline_b0_xp(season, gw, snapshot)
    act_projs = actual_projections(snapshot, actuals)

    try:
        sol_v1 = solve_squad(snapshot, v1, strategy=strategy, objective="horizon")
        sol_gw1 = solve_squad(snapshot, v1, strategy=strategy, objective="next")
        sol_b0 = solve_squad(snapshot, b0, strategy=strategy, objective="horizon")
        sol_oracle = solve_squad(snapshot, act_projs, strategy=strategy, objective="horizon")
    except RuntimeError as exc:
        row.solver_error = str(exc)
        row.evaluation_status = "excluded"
        row.structural_flags = (row.structural_flags + ";solver_failure").strip(";")
        return row, player_rows

    act_index = by_id_actual(snapshot, actuals)
    try:
        oracle_xi_from_v1, _ = solve_xi(snapshot, sol_v1.players, act_index)
        oracle_cap_from_v1_squad = best_captain(oracle_xi_from_v1, actuals)
        oracle_cap_from_v1_xi = best_captain(sol_v1.xi, actuals)
    except RuntimeError as exc:
        row.solver_error = str(exc)
        row.evaluation_status = "excluded"
        row.structural_flags = (row.structural_flags + ";xi_solver_failure").strip(";")
        return row, player_rows

    p_oracle = xi_cap_points(sol_oracle.xi, sol_oracle.captain, actuals)
    p_v1_squad_oracle_xi = xi_cap_points(oracle_xi_from_v1, oracle_cap_from_v1_squad, actuals)
    p_v1_xi_oracle_cap = xi_cap_points(sol_v1.xi, oracle_cap_from_v1_xi, actuals)
    p_v1 = xi_cap_points(sol_v1.xi, sol_v1.captain, actuals)
    p_b0 = xi_cap_points(sol_b0.xi, sol_b0.captain, actuals)
    p_gw1 = xi_cap_points(sol_gw1.xi, sol_gw1.captain, actuals)

    row.b0_xi_cap = p_b0
    row.v1_xi_cap = p_v1
    row.v1_gw1_xi_cap = p_gw1
    row.hindsight_oracle_cap = p_oracle
    row.squad_overlap = len({p.id for p in sol_v1.players} & {p.id for p in sol_b0.players})
    row.xi_overlap = len({p.id for p in sol_v1.xi} & {p.id for p in sol_b0.xi})
    row.hindsight_squad_regret = p_oracle - p_v1_squad_oracle_xi
    row.hindsight_xi_regret = p_v1_squad_oracle_xi - p_v1_xi_oracle_cap
    row.hindsight_cap_regret = p_v1_xi_oracle_cap - p_v1
    row.vs_b0_gap = p_b0 - p_v1
    row.inspect_v1_lt_15 = int(p_v1 < 15)
    row.inspect_b0_gt_80 = int(p_b0 > 80)

    v1_by = {p.player.id: p for p in v1}
    b0_by = {p.player.id: p for p in b0}
    v1_xi_ids = {p.id for p in sol_v1.xi}
    b0_xi_ids = {p.id for p in sol_b0.xi}
    v1_sq_ids = {p.id for p in sol_v1.players}
    b0_sq_ids = {p.id for p in sol_b0.players}
    union = v1_xi_ids | b0_xi_ids | {sol_v1.captain.id, sol_b0.captain.id}

    name_of = {p.id: p.web_name for p in snapshot.players}
    pos_of = {p.id: p.position for p in snapshot.players}
    cost_of = {p.id: p.now_cost for p in snapshot.players}

    for pid in sorted(union):
        vp = v1_by.get(pid)
        bp = b0_by.get(pid)
        in_v1 = int(pid in v1_xi_ids)
        in_b0 = int(pid in b0_xi_ids)
        v1_mu = vp.next_mu if vp else None
        b0_mu = bp.next_mu if bp else None
        v1_h = vp.horizon_utility if vp else None
        v1_ps = vp.next_p_start if vp else None
        act = _pts(actuals, pid)

        horizon_flag = 0
        if vp and in_v1 and not in_b0 and v1_h is not None:
            if v1_h > (v1_mu or 0) * 3:
                horizon_flag = 1
        minutes_flag = int(bool(vp and in_v1 and (vp.next_p_start or 0) < 0.55))
        fixture_flag = int(bool(vp and vp.by_gw.get(gw) and vp.by_gw[gw].n_fixtures != 1))
        price_flag = int(in_v1 and not in_b0 and cost_of.get(pid, 0) < 55)
        captain_flag = int(pid in {sol_v1.captain.id, sol_b0.captain.id} and sol_v1.captain.id != sol_b0.captain.id)
        proj_rank_flag = 0
        if vp and bp and in_v1 != in_b0:
            if in_v1 and (v1_mu or 0) >= (b0_mu or 0) and act < (b0_mu or 0):
                proj_rank_flag = 1
            if in_b0 and not in_v1 and act > (v1_mu or 0):
                proj_rank_flag = 1

        player_rows.append({
            "season": season,
            "gw": gw,
            "evaluation_status": row.evaluation_status,
            "player_id": pid,
            "web_name": name_of.get(pid, ""),
            "position": pos_of.get(pid, ""),
            "now_cost": cost_of.get(pid, ""),
            "in_b0_xi": in_b0,
            "in_v1_xi": in_v1,
            "in_b0_squad": int(pid in b0_sq_ids),
            "in_v1_squad": int(pid in v1_sq_ids),
            "is_v1_captain": int(pid == sol_v1.captain.id),
            "is_b0_captain": int(pid == sol_b0.captain.id),
            "actual_points": act,
            "v1_mu": round(v1_mu, 4) if v1_mu is not None else "",
            "b0_mu": round(b0_mu, 4) if b0_mu is not None else "",
            "v1_horizon_u": round(v1_h, 4) if v1_h is not None else "",
            "v1_p_start": round(v1_ps, 4) if v1_ps is not None else "",
            "horizon_flag": horizon_flag,
            "minutes_flag": minutes_flag,
            "fixture_flag": fixture_flag,
            "price_value_flag": price_flag,
            "captain_flag": captain_flag,
            "projection_rank_flag": proj_rank_flag,
        })

    return row, player_rows


def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    ys = sorted(xs)
    k = (len(ys) - 1) * p
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return ys[lo]
    return ys[lo] * (hi - k) + ys[hi] * (k - lo)


def _trimmed_mean(xs: list[float], proportion: float = 0.1) -> float:
    if not xs:
        return float("nan")
    ys = sorted(xs)
    n = len(ys)
    k = int(n * proportion)
    core = ys[k: n - k] if n > 2 * k else ys
    return statistics.mean(core) if core else float("nan")


def summarize(label: str, rows: list[GWRow]) -> None:
    def col(getter) -> list[float]:
        return [getter(r) for r in rows if getter(r) is not None]

    print(f"--- {label}  n={len(rows)} ---")
    if not rows:
        print("  (empty)")
        return
    fields = [
        ("B0", lambda r: r.b0_xi_cap),
        ("V1", lambda r: r.v1_xi_cap),
        ("V1_GW1", lambda r: r.v1_gw1_xi_cap),
        ("Oracle", lambda r: r.hindsight_oracle_cap),
        ("vs_B0_gap", lambda r: r.vs_b0_gap),
    ]
    print(f"  {'metric':12} {'mean':>8} {'median':>8} {'P25':>8} {'P75':>8} {'trim10':>8}")
    for name, getter in fields:
        xs = col(getter)
        if not xs:
            continue
        print(
            f"  {name:12} {statistics.mean(xs):8.2f} {statistics.median(xs):8.2f} "
            f"{_pct(xs, 0.25):8.2f} {_pct(xs, 0.75):8.2f} {_trimmed_mean(xs):8.2f}"
        )
    sr = col(lambda r: r.hindsight_squad_regret)
    xr = col(lambda r: r.hindsight_xi_regret)
    cr = col(lambda r: r.hindsight_cap_regret)
    if sr and xr and cr:
        tot = [a + b + c for a, b, c in zip(sr, xr, cr)]
        t = statistics.mean(tot) or 1.0
        print(
            f"  hindsight share  squad={100*statistics.mean(sr)/t:.1f}%  "
            f"XI={100*statistics.mean(xr)/t:.1f}%  cap={100*statistics.mean(cr)/t:.1f}%"
        )
    print()


def write_gw_csv(path: Path, rows: list[GWRow]) -> None:
    cols = [
        "season", "gw", "evaluation_status", "structural_flags",
        "n_fixtures", "n_actual_rows", "n_unique_actuals", "n_duplicate_ids",
        "n_with_minutes", "n_snapshot",
        "inspect_v1_lt_15", "inspect_b0_gt_80",
        "b0_xi_cap", "v1_xi_cap", "v1_gw1_xi_cap", "hindsight_oracle_cap",
        "squad_overlap", "xi_overlap",
        "hindsight_squad_regret", "hindsight_xi_regret", "hindsight_cap_regret",
        "vs_b0_gap", "solver_error",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: getattr(r, k) if getattr(r, k) is not None else "" for k in cols})


def write_player_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def print_top_gaps(rows: list[GWRow], k: int = 10) -> None:
    scored = [r for r in rows if r.vs_b0_gap is not None]
    scored.sort(key=lambda r: r.vs_b0_gap or 0, reverse=True)
    print(f"--- Top {k} B0-V1 gaps (inspection only, not exclusion) ---")
    for r in scored[:k]:
        print(
            f"  GW{r.gw:02d}  status={r.evaluation_status:8}  gap={r.vs_b0_gap:7.1f}  "
            f"B0={r.b0_xi_cap:6.1f}  V1={r.v1_xi_cap:6.1f}  V1_GW1={r.v1_gw1_xi_cap:6.1f}  "
            f"fx={r.n_fixtures}  flags={r.structural_flags or '-'}  "
            f"inspect_v1<15={r.inspect_v1_lt_15} inspect_b0>80={r.inspect_b0_gt_80}"
        )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="V2 decision-error decomposition.")
    parser.add_argument("--season", required=True, choices=SUPPORTED_SEASONS)
    parser.add_argument("--gw", type=int)
    parser.add_argument("--from-gw", type=int, dest="from_gw", default=1)
    parser.add_argument("--to-gw", type=int, dest="to_gw", default=38)
    parser.add_argument("--strategy", default="balanced")
    args = parser.parse_args()

    ensure_vaastav((args.season,))
    gws = [args.gw] if args.gw else range(args.from_gw, args.to_gw + 1)

    gw_rows: list[GWRow] = []
    player_rows: list[dict] = []
    for gw in gws:
        print(f"[harness_decomp] {args.season} GW{gw} ...")
        row, prs = evaluate_gw(args.season, gw, strategy=args.strategy)
        gw_rows.append(row)
        player_rows.extend(prs)

    out_dir = Path("records") / "historical" / args.season
    write_gw_csv(out_dir / "decision_gw.csv", gw_rows)
    write_player_csv(out_dir / "decision_decomp.csv", player_rows)

    print()
    print(f"=== {args.season} V2 investigation ===")
    print("Anomaly status is structural. inspect_* columns are descriptive, not exclusion.")
    print()
    print_top_gaps(gw_rows)
    all_scored = [r for r in gw_rows if r.v1_xi_cap is not None]
    summarize("ALL GWs (scored)", all_scored)
    summarize("CLEAN GWs", [r for r in all_scored if r.evaluation_status == "clean"])
    summarize("FLAGGED GWs", [r for r in all_scored if r.evaluation_status == "flagged"])
    n_ex = sum(1 for r in gw_rows if r.evaluation_status == "excluded")
    print(f"Excluded GWs (evaluator broken): {n_ex}")
    print()
    print(f"[harness_decomp] Wrote {out_dir / 'decision_gw.csv'}")
    print(f"[harness_decomp] Wrote {out_dir / 'decision_decomp.csv'}")


if __name__ == "__main__":
    main()
