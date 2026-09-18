"""k-best squad candidates from the frozen Model A ILP.

Layers (keep separate):
  CandidateGeneration → CandidatePool → CandidateDiagnostics → Presentation (later)

Generation uses the production `solve_squad` horizon objective plus exact-15
no-good cuts. Diagnostics are computed on that shared pool. Do not re-solve
with a different objective per label. No ROBUST/FLEX/UPSIDE names here.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from engine.models import Player, PlayerProjection, Snapshot, SquadSolution
from engine.optimize import solve_squad
from engine.stability_selection import squad_objective_value

MINUTES_RISK_P_START = 0.75


@dataclass(frozen=True)
class CandidateDiagnostics:
    rank: int
    ids: frozenset[int]
    names: tuple[str, ...]
    u: float
    delta_u: float
    distance: int
    jaccard: float
    bank: int
    cost: int
    club_max: int
    minutes_risk: int
    captain_id: int
    captain: str
    vice_id: int
    vice: str
    enters: tuple[str, ...]
    exits: tuple[str, ...]


@dataclass(frozen=True)
class Candidate:
    rank: int
    solution: SquadSolution
    diagnostics: CandidateDiagnostics


def _ids(sol: SquadSolution) -> frozenset[int]:
    return frozenset(p.id for p in sol.players)


def _name(player: Player) -> str:
    return player.web_name or f"#{player.id}"


def _club_max(players: list[Player]) -> int:
    counts = Counter(p.team_id for p in players)
    return max(counts.values()) if counts else 0


def diagnose(
    sol: SquadSolution,
    rank: int,
    s1: SquadSolution,
    by_id: dict[int, PlayerProjection],
    objective: str,
) -> CandidateDiagnostics:
    ids = _ids(sol)
    s1_ids = _ids(s1)
    inter = ids & s1_ids
    union = ids | s1_ids
    u = squad_objective_value(sol.players, sol.xi, by_id, objective=objective)
    u1 = squad_objective_value(s1.players, s1.xi, by_id, objective=objective)
    enters = tuple(sorted(_name(p) for p in sol.players if p.id not in s1_ids))
    exits = tuple(sorted(_name(p) for p in s1.players if p.id not in ids))
    return CandidateDiagnostics(
        rank=rank,
        ids=ids,
        names=tuple(_name(p) for p in sol.players),
        u=u,
        delta_u=u1 - u,
        distance=15 - len(inter),
        jaccard=(len(inter) / len(union)) if union else 1.0,
        bank=sol.bank,
        cost=sol.cost,
        club_max=_club_max(sol.players),
        minutes_risk=sum(
            1
            for p in sol.players
            if by_id[p.id].next_p_start < MINUTES_RISK_P_START
        ),
        captain_id=sol.captain.id,
        captain=_name(sol.captain),
        vice_id=sol.vice.id,
        vice=_name(sol.vice),
        enters=enters,
        exits=exits,
    )


def solve_k_best(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    *,
    strategy: str,
    k: int = 10,
    objective: str = "horizon",
    must_include: set[int] | None = None,
    must_exclude: set[int] | None = None,
) -> list[Candidate]:
    """Generate S1…Sk from the same frozen objective via exact-15 cuts."""
    if k < 1:
        raise ValueError("k must be >= 1")
    by_id = {p.player.id: p for p in projections}
    excluded: list[set[int]] = []
    pool: list[Candidate] = []
    s1: SquadSolution | None = None
    for rank in range(1, k + 1):
        try:
            sol = solve_squad(
                snapshot,
                projections,
                strategy=strategy,
                must_include=must_include,
                must_exclude=must_exclude,
                objective=objective,
                exclude_squads=excluded,
            )
        except RuntimeError:
            break
        ids = set(_ids(sol))
        if any(ids == banned for banned in excluded):
            break
        if s1 is None:
            s1 = sol
        diag = diagnose(sol, rank, s1, by_id, objective)
        pool.append(Candidate(rank=rank, solution=sol, diagnostics=diag))
        excluded.append(ids)
    return pool


def format_squad(sol: SquadSolution) -> str:
    """Readable 15 for live inspection (XI then bench)."""
    xi = ", ".join(f"{_name(p)}({p.position})" for p in sol.xi)
    bench = ", ".join(f"{_name(p)}({p.position})" for p in sol.bench)
    return (
        f"C {_name(sol.captain)} / VC {_name(sol.vice)} | "
        f"XI {xi} | bench {bench} | "
        f"cost {sol.cost} bank {sol.bank}"
    )
