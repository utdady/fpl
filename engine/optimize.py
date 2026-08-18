"""ILP squad and XI selection. Strategy is applied via projected utility, not post-hoc weights."""
from __future__ import annotations

from engine.models import Player, PlayerProjection, Snapshot, SquadSolution
import pulp

# Bench points are real but much less than XI points. Weighting the 15-man
# sum equally is how Haaland loses to three mid-price forwards.
BENCH_WEIGHT = 0.12


def _index(projections: list[PlayerProjection]) -> dict[int, PlayerProjection]:
    return {p.player.id: p for p in projections}


def solve_squad(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    strategy: str,
    must_include: set[int] | None = None,
    must_exclude: set[int] | None = None,
    objective: str = "horizon",
) -> SquadSolution:
    """objective: 'horizon' (production V1) or 'next' (diagnostic GW-myopic squad)."""
    rules = snapshot.squad
    by_id = _index(projections)
    include = must_include or set()
    exclude = must_exclude or set()
    eligible = [
        p
        for p in snapshot.players
        if p.id not in exclude
        and p.id in by_id
        and (p.can_select or p.id in include)
        and (p.id in include or by_id[p.id].horizon_utility > -20)
    ]
    ids = [p.id for p in eligible]
    missing = include - set(ids)
    if missing:
        raise RuntimeError(f"must_include not eligible: {sorted(missing)}")
    cost = {p.id: p.now_cost for p in eligible}
    pos = {p.id: p.position for p in eligible}
    team = {p.id: p.team_id for p in eligible}
    if objective not in {"horizon", "next"}:
        raise ValueError(f"unknown objective {objective!r}")
    if objective == "next":
        util = {p.id: by_id[p.id].next_utility for p in eligible}
    else:
        util = {p.id: by_id[p.id].horizon_utility for p in eligible}

    prob = pulp.LpProblem("fpl_squad", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("x", ids, 0, 1, pulp.LpInteger)
    s = pulp.LpVariable.dicts("s", ids, 0, 1, pulp.LpInteger)

    # Effective playing utility: starters count fully, bench at BENCH_WEIGHT.
    prob += pulp.lpSum(
        util[i] * (BENCH_WEIGHT * x[i] + (1.0 - BENCH_WEIGHT) * s[i]) for i in ids
    )
    for i in ids:
        prob += s[i] <= x[i]
    prob += pulp.lpSum(x[i] for i in ids) == rules.squad_size
    prob += pulp.lpSum(s[i] for i in ids) == rules.squad_play
    prob += pulp.lpSum(cost[i] * x[i] for i in ids) <= rules.budget
    for pcode, n in rules.squad_select.items():
        prob += pulp.lpSum(x[i] for i in ids if pos[i] == pcode) == n, f"squad_{pcode}"
    for pcode in rules.min_play:
        n_start = pulp.lpSum(s[i] for i in ids if pos[i] == pcode)
        prob += n_start >= rules.min_play[pcode], f"min_{pcode}"
        prob += n_start <= rules.max_play[pcode], f"max_{pcode}"
    for tid in {team[i] for i in ids}:
        prob += pulp.lpSum(x[i] for i in ids if team[i] == tid) <= rules.team_limit, f"club_{tid}"
    for i in include:
        prob += x[i] == 1, f"lock_{i}"

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=25))
    chosen_ids = [i for i in ids if x[i].value() and x[i].value() > 0.5]
    if len(chosen_ids) != rules.squad_size:
        raise RuntimeError(
            f"Squad solver failed ({pulp.LpStatus[status]}); got {len(chosen_ids)} players"
        )

    squad_players = [next(p for p in eligible if p.id == i) for i in chosen_ids]
    xi, bench = solve_xi(snapshot, squad_players, by_id)
    captain, vice = pick_captains(xi, by_id)
    spent = sum(p.now_cost for p in squad_players)
    next_xi_mu = sum(by_id[p.id].next_mu for p in xi) + by_id[captain.id].next_mu
    next_xi_u = sum(by_id[p.id].next_utility for p in xi) + by_id[captain.id].next_utility
    alts = alternatives(eligible, squad_players, by_id)
    gws = sorted({gw for proj in projections for gw in proj.by_gw})
    return SquadSolution(
        players=sorted(squad_players, key=lambda p: (p.element_type, -by_id[p.id].horizon_mu)),
        xi=xi,
        bench=bench,
        captain=captain,
        vice=vice,
        cost=spent,
        bank=rules.budget - spent,
        horizon_utility=sum(by_id[p.id].horizon_utility for p in squad_players),
        next_xi_mu=next_xi_mu,
        next_xi_utility=next_xi_u,
        alternatives=alts,
        strategy=strategy,
        horizon_gws=gws,
    )


def solve_xi(
    snapshot: Snapshot,
    squad: list[Player],
    by_id: dict[int, PlayerProjection],
) -> tuple[list[Player], list[Player]]:
    rules = snapshot.squad
    ids = [p.id for p in squad]
    pos = {p.id: p.position for p in squad}
    util = {p.id: by_id[p.id].next_utility for p in squad}

    prob = pulp.LpProblem("fpl_xi", pulp.LpMaximize)
    y = pulp.LpVariable.dicts("y", ids, 0, 1, pulp.LpInteger)
    prob += pulp.lpSum(util[i] * y[i] for i in ids)
    prob += pulp.lpSum(y[i] for i in ids) == rules.squad_play
    for pcode in rules.min_play:
        n_pos = pulp.lpSum(y[i] for i in ids if pos[i] == pcode)
        prob += n_pos >= rules.min_play[pcode], f"min_{pcode}"
        prob += n_pos <= rules.max_play[pcode], f"max_{pcode}"

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=10))
    start_ids = [i for i in ids if y[i].value() and y[i].value() > 0.5]
    if len(start_ids) != rules.squad_play:
        raise RuntimeError(f"XI solver failed ({pulp.LpStatus[status]})")

    order = {"GKP": 0, "DEF": 1, "MID": 2, "FWD": 3}
    xi = sorted(
        [p for p in squad if p.id in start_ids],
        key=lambda p: (order[p.position], -by_id[p.id].next_mu),
    )
    bench = sorted(
        [p for p in squad if p.id not in start_ids],
        key=lambda p: (0 if p.position == "GKP" else 1, -by_id[p.id].next_mu),
    )
    return xi, bench


def pick_captains(
    xi: list[Player],
    by_id: dict[int, PlayerProjection],
) -> tuple[Player, Player]:
    ranked = sorted(xi, key=lambda p: by_id[p.id].next_utility, reverse=True)
    captain = ranked[0]
    rest = [p for p in ranked if p.id != captain.id]
    vice = max(rest, key=lambda p: by_id[p.id].next_p_start * by_id[p.id].next_mu)
    return captain, vice


def alternatives(
    eligible: list[Player],
    squad: list[Player],
    by_id: dict[int, PlayerProjection],
    k: int = 3,
) -> list[tuple[str, Player, float]]:
    squad_ids = {p.id for p in squad}
    out: list[tuple[str, Player, float]] = []
    for pos in ("GKP", "DEF", "MID", "FWD"):
        pool = [p for p in eligible if p.position == pos and p.id not in squad_ids]
        pool.sort(key=lambda p: by_id[p.id].next_mu, reverse=True)
        for p in pool[:k]:
            out.append((pos, p, by_id[p.id].next_mu))
    return out
