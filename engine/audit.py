"""Pre-deadline interrogation. Does not change projection coefficients.

python -m engine.audit --strategy balanced
"""
from __future__ import annotations

import argparse
import math
import sys
from collections import Counter
from pathlib import Path

from engine.api import load_snapshot
from engine.models import Player, PlayerProjection, Snapshot, SquadSolution
from engine.optimize import BENCH_WEIGHT, solve_squad
from engine.project import STRATEGIES, project_all

CHECKLIST_OUT = {"i", "u", "n", "s"}


def _by_id(projections: list[PlayerProjection]) -> dict[int, PlayerProjection]:
    return {p.player.id: p for p in projections}


def weighted_objective(solution: SquadSolution, by_id: dict[int, PlayerProjection]) -> float:
    """Approximate ILP objective using the GW1 XI as the starter set."""
    xi = {p.id for p in solution.xi}
    total = 0.0
    for p in solution.players:
        u = by_id[p.id].horizon_utility
        total += u if p.id in xi else BENCH_WEIGHT * u
    return total


def names(players: list[Player]) -> set[str]:
    return {p.web_name for p in players}


def find_player(snapshot: Snapshot, web_name: str) -> Player | None:
    hits = [p for p in snapshot.players if p.web_name.lower() == web_name.lower()]
    return hits[0] if hits else None


# ---------- sanity ----------

def sanity_checklist(snapshot: Snapshot, solution: SquadSolution, by_id: dict[int, PlayerProjection]) -> str:
    rules = snapshot.squad
    xi_ids = {p.id for p in solution.xi}
    checks: list[tuple[str, bool, str]] = []

    checks.append(("15 players", len(solution.players) == rules.squad_size, str(len(solution.players))))
    checks.append(
        ("budget respected", solution.cost <= rules.budget and solution.bank >= 0,
         f"{solution.cost / 10:.1f}m bank {solution.bank / 10:.1f}m"),
    )
    for pos, n in rules.squad_select.items():
        got = sum(1 for p in solution.players if p.position == pos)
        checks.append((f"{n} {pos}", got == n, str(got)))
    club_counts = Counter(p.team_id for p in solution.players)
    checks.append(("<=3 per club", all(c <= rules.team_limit for c in club_counts.values()), str(dict(club_counts))))
    checks.append((f"XI size {rules.squad_play}", len(solution.xi) == rules.squad_play, str(len(solution.xi))))
    for pos in rules.min_play:
        n = sum(1 for p in solution.xi if p.position == pos)
        ok = rules.min_play[pos] <= n <= rules.max_play[pos]
        checks.append((f"XI {pos} in [{rules.min_play[pos]}, {rules.max_play[pos]}]", ok, str(n)))
    checks.append(("captain in XI", solution.captain.id in xi_ids, solution.captain.web_name))
    checks.append(("vice in XI", solution.vice.id in xi_ids, solution.vice.web_name))
    checks.append(("captain available", solution.captain.status not in CHECKLIST_OUT, solution.captain.status))
    checks.append(
        ("no unavailable in XI", all(p.status not in CHECKLIST_OUT for p in solution.xi),
         ",".join(p.web_name for p in solution.xi if p.status in CHECKLIST_OUT) or "ok"),
    )
    vp = by_id[solution.vice.id].next_p_start
    checks.append((f"vice P(start)={vp:.2f} (reported, not a gate)", True, ""))

    lines = ["--- Sanity checklist ---"]
    for label, ok, detail in checks:
        mark = "x" if ok else " "
        extra = f"  {detail}" if detail else ""
        lines.append(f"  [{mark}] {label}{extra}")
    return "\n".join(lines)


def club_counts(snapshot: Snapshot, solution: SquadSolution) -> str:
    lines = ["--- Club concentration ---"]
    counts = Counter(p.team_id for p in solution.players)
    for tid, n in sorted(counts.items(), key=lambda kv: (-kv[1], snapshot.team(kv[0]).short_name)):
        club = snapshot.team(tid)
        members = [p.web_name for p in solution.players if p.team_id == tid]
        flag = "  TRIPLE" if n >= 3 else ""
        lines.append(f"  {club.short_name:3} {n}  {', '.join(members)}{flag}")
    return "\n".join(lines)


def vice_formulas(solution: SquadSolution, by_id: dict[int, PlayerProjection]) -> str:
    lines = ["--- Vice under both formulas (captain rule unchanged) ---"]
    lines.append(f"  actual vice (P(start)*mu): {solution.vice.web_name}")
    scored = []
    for p in solution.xi:
        if p.id == solution.captain.id:
            continue
        proj = by_id[p.id]
        safe = proj.next_p_start * proj.next_mu
        agg = proj.next_p_start * (proj.next_mu + 3.0 * proj.next_p_10)
        scored.append((p, proj, safe, agg))
    safe_pick = max(scored, key=lambda t: t[2])
    agg_pick = max(scored, key=lambda t: t[3])
    lines.append(f"  P(start)*mu winner:        {safe_pick[0].web_name}  ({safe_pick[2]:.2f})")
    lines.append(f"  P(start)*(mu+3*p10) winner:{agg_pick[0].web_name}  ({agg_pick[3]:.2f})")
    for p, proj, safe, agg in sorted(scored, key=lambda t: -t[2]):
        lines.append(
            f"    {p.web_name:16} P(st) {proj.next_p_start:.2f}  mu {proj.next_mu:5.2f}  "
            f"p10 {proj.next_p_10:.2f}  safe {safe:5.2f}  agg {agg:5.2f}"
        )
    return "\n".join(lines)


def loo_tag(delta: float) -> str:
    if not math.isfinite(delta):
        return "unknown"
    if delta >= 2.0:
        return "essential"
    if delta >= 0.4:
        return "marginal"
    return "interchangeable"


LOO_COLUMNS = [
    "player_id",
    "web_name",
    "position",
    "cost",
    "next_mu",
    "horizon_u",
    "p_start",
    "delta",
    "tag",
    "incoming",
    "strategy",
    "as_of",
]

CF_COLUMNS = [
    "player_id",
    "web_name",
    "action",
    "delta",
    "baseline_u",
    "alt_u",
    "strategy",
    "as_of",
]


def export_loo_rows(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    solution: SquadSolution | None = None,
    strategy: str = "balanced",
) -> list[dict]:
    by_id = _by_id(projections)
    solution = solution or solve_squad(snapshot, projections, strategy=strategy)
    base_u = weighted_objective(solution, by_id)
    as_of = snapshot.as_of.isoformat() if snapshot.as_of else ""
    rows: list[dict] = []
    for p in solution.players:
        try:
            alt = solve_squad(snapshot, projections, strategy=strategy, must_exclude={p.id})
        except RuntimeError:
            rows.append(
                {
                    "player_id": p.id,
                    "web_name": p.web_name,
                    "position": p.position,
                    "cost": p.now_cost,
                    "next_mu": round(by_id[p.id].next_mu, 4),
                    "horizon_u": round(by_id[p.id].horizon_utility, 4),
                    "p_start": round(by_id[p.id].next_p_start, 4),
                    "delta": "",
                    "tag": "solver_failed",
                    "incoming": "",
                    "strategy": strategy,
                    "as_of": as_of,
                }
            )
            continue
        alt_u = weighted_objective(alt, by_id)
        delta = base_u - alt_u
        incoming = names(alt.players) - names(solution.players)
        rows.append(
            {
                "player_id": p.id,
                "web_name": p.web_name,
                "position": p.position,
                "cost": p.now_cost,
                "next_mu": round(by_id[p.id].next_mu, 4),
                "horizon_u": round(by_id[p.id].horizon_utility, 4),
                "p_start": round(by_id[p.id].next_p_start, 4),
                "delta": round(delta, 4) if math.isfinite(delta) else "",
                "tag": loo_tag(delta),
                "incoming": ", ".join(sorted(incoming)) if incoming else "",
                "strategy": strategy,
                "as_of": as_of,
            }
        )
    rows.sort(key=lambda r: -(float(r["delta"]) if r["delta"] != "" else -1e9))
    return rows


def export_counterfactual_rows(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    solution: SquadSolution | None = None,
    strategy: str = "balanced",
    target_name: str = "Haaland",
) -> list[dict]:
    by_id = _by_id(projections)
    solution = solution or solve_squad(snapshot, projections, strategy=strategy)
    base_u = weighted_objective(solution, by_id)
    as_of = snapshot.as_of.isoformat() if snapshot.as_of else ""
    target = find_player(snapshot, target_name)
    if target is None:
        return []
    rows: list[dict] = []
    for action, alt in (
        ("exclude", solve_squad(snapshot, projections, strategy=strategy, must_exclude={target.id})),
        ("lock", solve_squad(snapshot, projections, strategy=strategy, must_include={target.id})),
    ):
        alt_u = weighted_objective(alt, by_id)
        if action == "exclude":
            delta = base_u - alt_u
        else:
            delta = alt_u - base_u
        rows.append(
            {
                "player_id": target.id,
                "web_name": target.web_name,
                "action": action,
                "delta": round(delta, 4),
                "baseline_u": round(base_u, 4),
                "alt_u": round(alt_u, 4),
                "strategy": strategy,
                "as_of": as_of,
            }
        )
    return rows


def write_audit_csv(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    strategy: str = "balanced",
    loo_path: Path | None = None,
    cf_path: Path | None = None,
) -> tuple[int, int]:
    import csv
    from pathlib import Path as P

    loo_path = loo_path or P("records/audit_loo.csv")
    cf_path = cf_path or P("records/audit_counterfactual.csv")
    loo_rows = export_loo_rows(snapshot, projections, strategy=strategy)
    cf_rows = export_counterfactual_rows(snapshot, projections, strategy=strategy)
    for path, rows, columns in ((loo_path, loo_rows, LOO_COLUMNS), (cf_path, cf_rows, CF_COLUMNS)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    return len(loo_rows), len(cf_rows)


# ---------- leave-one-out ----------

def why_selected(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    solution: SquadSolution,
    strategy: str,
) -> str:
    by_id = _by_id(projections)
    base_u = weighted_objective(solution, by_id)
    lines = [
        "--- Leave-one-out (Delta = U* - U without i) ---",
        "  U is bench-weighted horizon utility using the GW1 XI as starters.",
        f"  U*(baseline) = {base_u:.2f}",
        "",
    ]
    rows = []
    for p in solution.players:
        try:
            alt = solve_squad(snapshot, projections, strategy=strategy, must_exclude={p.id})
        except RuntimeError:
            rows.append((float("nan"), p, by_id[p.id], {"[solver failed]"}, float("nan")))
            continue
        alt_u = weighted_objective(alt, by_id)
        delta = base_u - alt_u
        incoming = names(alt.players) - names(solution.players)
        proj = by_id[p.id]
        rows.append((delta, p, proj, incoming, alt_u))
    rows.sort(key=lambda r: -r[0])
    lines.append(
        f"  {'player':16} {'pos':3} {'price':6} {'next':>5} {'horizU':>7} {'P(st)':>5} {'P60':>5} {'P10+':>5} {'Delta':>7}  comes in"
    )
    for delta, p, proj, incoming, _alt_u in rows:
        tag = loo_tag(delta)
        who = ", ".join(sorted(incoming)) if incoming else "-"
        lines.append(
            f"  {p.web_name:16} {p.position:3} {p.now_cost/10:5.1f}m {proj.next_mu:5.2f} "
            f"{proj.horizon_utility:7.2f} {proj.next_p_start:5.2f} {proj.next_p_60:5.2f} "
            f"{proj.next_p_10:5.2f} {delta:7.2f}  {who:20} {tag}"
        )
    return "\n".join(lines)


# ---------- baselines ----------

def _fake(player: Player, score: float, p_start: float = 1.0) -> PlayerProjection:
    return PlayerProjection(
        player=player,
        by_gw={},
        horizon_mu=score,
        horizon_sigma=0.0,
        horizon_utility=score,
        next_mu=score,
        next_sigma=0.0,
        next_p_start=p_start,
        next_p_60=p_start,
        next_p_10=0.0,
        next_utility=score,
    )


def baseline_ep_next(snapshot: Snapshot) -> list[PlayerProjection]:
    return [_fake(p, p.ep_next or 0.0) for p in snapshot.players]


def baseline_last_season(snapshot: Snapshot) -> list[PlayerProjection]:
    return [_fake(p, float(p.total_points)) for p in snapshot.players]


def baseline_naive_pp90(snapshot: Snapshot) -> list[PlayerProjection]:
    """Points per 90 from last season, with a sample-size floor.

    minutes>=90 lets 1-match outliers dominate the ILP (Dowman, Ellborg, ...).
    """
    out = []
    for p in snapshot.players:
        if p.minutes >= 900:
            score = p.total_points / (p.minutes / 90.0)
        else:
            score = 0.0
        out.append(_fake(p, score))
    return out


def compare_baselines(
    snapshot: Snapshot,
    v1: list[PlayerProjection],
    strategy: str,
    v1_solution: SquadSolution,
) -> str:
    sources: list[tuple[str, list[PlayerProjection], str]] = [
        ("ep_next (GW1 official, not a 6-GW horizon)", baseline_ep_next(snapshot)),
        ("last_season total_points", baseline_last_season(snapshot)),
        ("naive points/90 (minutes>=900 else 0)", baseline_naive_pp90(snapshot)),
        ("v1", v1),
    ]
    lines = ["--- Same ILP, four projection sources ---"]
    solved: dict[str, set[str]] = {}
    v1_names = names(v1_solution.players)
    for label, projs in ((s[0], s[1]) for s in sources):
        key = label.split()[0]
        try:
            sol = v1_solution if key == "v1" else solve_squad(snapshot, projs, strategy=strategy)
            solved[key] = names(sol.players)
            overlap = len(solved[key] & v1_names)
            lines.append(f"[{label}]  overlap with V1 {overlap}/15")
            only_this = sorted(solved[key] - v1_names)
            only_v1 = sorted(v1_names - solved[key])
            if key != "v1":
                lines.append(f"  uniquely this: {', '.join(only_this) or '-'}")
                lines.append(f"  uniquely V1:   {', '.join(only_v1) or '-'}")
            lines.append(f"  squad: {', '.join(sorted(solved[key]))}")
            lines.append("")
        except RuntimeError as exc:
            lines.append(f"[{label}] solver failed: {exc}\n")
    return "\n".join(lines)


# ---------- Haaland lock / exclude ----------

def haaland_experiment(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    solution: SquadSolution,
    strategy: str,
) -> str:
    haaland = find_player(snapshot, "Haaland")
    if haaland is None:
        return "--- Haaland experiment ---\n  Haaland not in snapshot."
    by_id = _by_id(projections)
    base_u = weighted_objective(solution, by_id)
    in_squad = haaland.id in {p.id for p in solution.players}

    excluded = solve_squad(snapshot, projections, strategy=strategy, must_exclude={haaland.id})
    locked = solve_squad(snapshot, projections, strategy=strategy, must_include={haaland.id})
    ex_u = weighted_objective(excluded, by_id)
    lk_u = weighted_objective(locked, by_id)

    lines = [
        "--- Haaland lock / exclude ---",
        f"  currently in balanced 15: {in_squad}",
        f"  U baseline          {base_u:7.2f}",
        f"  U exclude Haaland   {ex_u:7.2f}   Delta vs baseline {base_u - ex_u:+.2f}",
        f"  U lock Haaland      {lk_u:7.2f}   Delta vs baseline {lk_u - base_u:+.2f}",
        "",
        f"  lock vs baseline, Haaland costs {base_u - lk_u:.2f} objective to force in"
        if not in_squad
        else f"  already in; exclude costs {base_u - ex_u:.2f}",
        "",
        "  locked 15 vs baseline 15:",
    ]
    base_n = names(solution.players)
    lock_n = names(locked.players)
    lines.append(f"    added:   {', '.join(sorted(lock_n - base_n)) or '-'}")
    lines.append(f"    dropped: {', '.join(sorted(base_n - lock_n)) or '-'}")
    lines.append("  locked XI: " + ", ".join(f"{p.web_name}" for p in locked.xi))
    lines.append(f"  locked C/VC: {locked.captain.web_name} / {locked.vice.web_name}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="V1 pre-deadline audit")
    parser.add_argument("--strategy", choices=STRATEGIES, default="balanced")
    parser.add_argument("--horizon", type=int, default=6)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--export-csv", action="store_true", help="Write records/audit_*.csv")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    snapshot = load_snapshot(refresh=args.refresh)
    projections = project_all(snapshot, horizon=args.horizon, strategy=args.strategy)
    solution = solve_squad(snapshot, projections, strategy=args.strategy)
    by_id = _by_id(projections)

    if args.export_csv:
        n_loo, n_cf = write_audit_csv(snapshot, projections, strategy=args.strategy)
        print(f"[audit] wrote {n_loo} LOO rows and {n_cf} counterfactual rows to records/")
        return 0

    nxt = snapshot.next_event()
    print(f"FPL V1 audit  |  {snapshot.season_label}  |  as of {snapshot.as_of.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{nxt.name}  strategy={args.strategy}  horizon={args.horizon}")
    print(f"Squad cost £{solution.cost/10:.1f}m  bank £{solution.bank/10:.1f}m  C {solution.captain.web_name}  VC {solution.vice.web_name}")
    print()
    print(sanity_checklist(snapshot, solution, by_id))
    print()
    print(club_counts(snapshot, solution))
    print()
    print(vice_formulas(solution, by_id))
    print()
    print(why_selected(snapshot, projections, solution, args.strategy))
    print()
    print(compare_baselines(snapshot, projections, args.strategy, solution))
    print()
    print(haaland_experiment(snapshot, projections, solution, args.strategy))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
