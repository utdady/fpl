"""H-PACK1: stability-aware marginal selection (E027).

Decision layer only. μ / MAE path unchanged.

Contract:
  U0 = control squad ILP objective (same weighted starter+bench form as solve_squad)
  U1 = treatment squad ILP objective
  Stage 1: U0* = max U0
  Stage 2: max U1 s.t. U0 >= U0* - ε

ε is frozen from control-only calibration (see calibrate_hpack1_epsilon.py).
"""
from __future__ import annotations

import json
from pathlib import Path

from engine.models import Player, PlayerProjection, Snapshot, SquadSolution
from engine.optimize import BENCH_WEIGHT, alternatives, pick_captains, solve_squad, solve_xi
import pulp

EPSILON_PATH = Path("records") / "historical" / "hpack1_epsilon.json"
EPSILON_PERCENTILE = 90  # frozen before harness run


def _index(projections: list[PlayerProjection]) -> dict[int, PlayerProjection]:
    return {p.player.id: p for p in projections}


def _eligible_players(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    must_include: set[int] | None = None,
    must_exclude: set[int] | None = None,
) -> list[Player]:
    by_id = _index(projections)
    include = must_include or set()
    exclude = must_exclude or set()
    return [
        p
        for p in snapshot.players
        if p.id not in exclude
        and p.id in by_id
        and (p.can_select or p.id in include)
        and (p.id in include or by_id[p.id].horizon_utility > -20)
    ]


def squad_objective_value(
    squad: list[Player],
    xi: list[Player],
    by_id: dict[int, PlayerProjection],
    objective: str = "next",
) -> float:
    """Weighted starter+bench objective matching solve_squad ILP."""
    xi_ids = {p.id for p in xi}
    total = 0.0
    for p in squad:
        proj = by_id[p.id]
        util = proj.next_utility if objective == "next" else proj.horizon_utility
        weight = 1.0 if p.id in xi_ids else BENCH_WEIGHT
        total += util * weight
    return total


def control_one_exclusion_gaps(
    snapshot: Snapshot,
    control_projections: list[PlayerProjection],
    strategy: str,
    objective: str = "next",
) -> tuple[float, list[float]]:
    """Return U0* and list of U0* - U0(exclude i) for each player in optimal squad."""
    sol = solve_squad(snapshot, control_projections, strategy=strategy, objective=objective)
    by_id = _index(control_projections)
    u0_star = squad_objective_value(sol.players, sol.xi, by_id, objective=objective)
    gaps: list[float] = []
    for p in sol.players:
        try:
            alt = solve_squad(
                snapshot,
                control_projections,
                strategy=strategy,
                objective=objective,
                must_exclude={p.id},
            )
        except RuntimeError:
            continue
        u_excl = squad_objective_value(alt.players, alt.xi, by_id, objective=objective)
        gap = u0_star - u_excl
        if gap >= 0:
            gaps.append(gap)
    return u0_star, gaps


def solve_squad_stability(
    snapshot: Snapshot,
    control_projections: list[PlayerProjection],
    treat_projections: list[PlayerProjection],
    strategy: str,
    epsilon: float,
    objective: str = "next",
) -> tuple[SquadSolution, float, float]:
    """Maximize treatment objective subject to control objective >= U0* - epsilon."""
    if objective not in {"horizon", "next"}:
        raise ValueError(f"unknown objective {objective!r}")

    by_c = _index(control_projections)
    by_t = _index(treat_projections)
    eligible = _eligible_players(snapshot, control_projections)
    ids = [p.id for p in eligible]
    if not ids:
        raise RuntimeError("no eligible players")

    rules = snapshot.squad
    cost = {p.id: p.now_cost for p in eligible}
    pos = {p.id: p.position for p in eligible}
    team = {p.id: p.team_id for p in eligible}

    if objective == "next":
        u0 = {p.id: by_c[p.id].next_utility for p in eligible}
        u1 = {p.id: by_t[p.id].next_utility for p in eligible}
    else:
        u0 = {p.id: by_c[p.id].horizon_utility for p in eligible}
        u1 = {p.id: by_t[p.id].horizon_utility for p in eligible}

    def _weight_expr(util: dict[int, float], x, s):
        return pulp.lpSum(
            util[i] * (BENCH_WEIGHT * x[i] + (1.0 - BENCH_WEIGHT) * s[i]) for i in ids
        )

    # Stage 1: control optimum
    prob0 = pulp.LpProblem("hpack1_u0", pulp.LpMaximize)
    x0 = pulp.LpVariable.dicts("x0", ids, 0, 1, pulp.LpInteger)
    s0 = pulp.LpVariable.dicts("s0", ids, 0, 1, pulp.LpInteger)
    prob0 += _weight_expr(u0, x0, s0)
    for i in ids:
        prob0 += s0[i] <= x0[i]
    prob0 += pulp.lpSum(x0[i] for i in ids) == rules.squad_size
    prob0 += pulp.lpSum(s0[i] for i in ids) == rules.squad_play
    prob0 += pulp.lpSum(cost[i] * x0[i] for i in ids) <= rules.budget
    for pcode, n in rules.squad_select.items():
        prob0 += pulp.lpSum(x0[i] for i in ids if pos[i] == pcode) == n
    for pcode in rules.min_play:
        n_start = pulp.lpSum(s0[i] for i in ids if pos[i] == pcode)
        prob0 += n_start >= rules.min_play[pcode]
        prob0 += n_start <= rules.max_play[pcode]
    for tid in {team[i] for i in ids}:
        prob0 += pulp.lpSum(x0[i] for i in ids if team[i] == tid) <= rules.team_limit

    status0 = prob0.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=25))
    u0_star = pulp.value(prob0.objective)
    if u0_star is None:
        raise RuntimeError(f"H-PACK1 stage-1 failed ({pulp.LpStatus[status0]})")

    # Stage 2: treatment within ε-band of control
    prob1 = pulp.LpProblem("hpack1_u1", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("x", ids, 0, 1, pulp.LpInteger)
    s = pulp.LpVariable.dicts("s", ids, 0, 1, pulp.LpInteger)
    prob1 += _weight_expr(u1, x, s)
    prob1 += _weight_expr(u0, x, s) >= float(u0_star) - epsilon
    for i in ids:
        prob1 += s[i] <= x[i]
    prob1 += pulp.lpSum(x[i] for i in ids) == rules.squad_size
    prob1 += pulp.lpSum(s[i] for i in ids) == rules.squad_play
    prob1 += pulp.lpSum(cost[i] * x[i] for i in ids) <= rules.budget
    for pcode, n in rules.squad_select.items():
        prob1 += pulp.lpSum(x[i] for i in ids if pos[i] == pcode) == n
    for pcode in rules.min_play:
        n_start = pulp.lpSum(s[i] for i in ids if pos[i] == pcode)
        prob1 += n_start >= rules.min_play[pcode]
        prob1 += n_start <= rules.max_play[pcode]
    for tid in {team[i] for i in ids}:
        prob1 += pulp.lpSum(x[i] for i in ids if team[i] == tid) <= rules.team_limit

    status1 = prob1.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=25))
    chosen_ids = [i for i in ids if x[i].value() and x[i].value() > 0.5]
    if len(chosen_ids) != rules.squad_size:
        raise RuntimeError(f"H-PACK1 stage-2 failed ({pulp.LpStatus[status1]})")

    u1_val = pulp.value(prob1.objective)
    u0_val = pulp.value(_weight_expr(u0, x, s))
    squad_players = [next(p for p in eligible if p.id == i) for i in chosen_ids]
    xi, bench = solve_xi(snapshot, squad_players, by_t)
    captain, vice = pick_captains(xi, by_t)
    spent = sum(p.now_cost for p in squad_players)
    gws = sorted({gw for proj in treat_projections for gw in proj.by_gw})
    sol = SquadSolution(
        players=sorted(squad_players, key=lambda p: (p.element_type, -by_t[p.id].horizon_mu)),
        xi=xi,
        bench=bench,
        captain=captain,
        vice=vice,
        cost=spent,
        bank=rules.budget - spent,
        horizon_utility=sum(by_t[p.id].horizon_utility for p in squad_players),
        next_xi_mu=sum(by_t[p.id].next_mu for p in xi) + by_t[captain.id].next_mu,
        next_xi_utility=sum(by_t[p.id].next_utility for p in xi) + by_t[captain.id].next_utility,
        alternatives=alternatives(eligible, squad_players, by_t),
        strategy=strategy,
        horizon_gws=gws,
    )
    return sol, float(u0_val), float(u1_val)


def load_epsilon(path: Path = EPSILON_PATH) -> float:
    if not path.exists():
        raise FileNotFoundError(
            f"missing {path}; run python scripts/calibrate_hpack1_epsilon.py first"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return float(data["epsilon"])


def write_epsilon(
    epsilon: float,
    n_gaps: int,
    path: Path = EPSILON_PATH,
    percentile: int = EPSILON_PERCENTILE,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "epsilon": round(epsilon, 6),
        "percentile": percentile,
        "method": "one_exclusion_gap",
        "description": (
            "P90 of pooled (U0* - U0(exclude i)) across control-only solves; "
            "control stack v2am_s + rates=v1 + fixtures=v1; objective=next"
        ),
        "n_gaps": n_gaps,
        "control_stack": "v2am_s+rates=v1+fixtures=v1",
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
