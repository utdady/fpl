"""E046-A frozen Free Hit policy (historical evaluator + future product share).

Contract (docs/LAB_LOG.md E046-A):
  Degeneracy lock: B0 = sticky HELD_0 (never weekly blank-slate).
  C: t* = argmax_t U_FH(t), tie → lowest GW
  U_FH(t) = next_xi_utility(BLANK) - next_xi_utility(XI_held)
  Stack: v2am_fpla + rates=v1 + fixtures v1; balanced; objective=next; seed=7
  g* = 20 (B1 only)

Any change requires a new preregistered experiment.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from engine.fplcache_avail import ensure_fplcache_avail
from engine.models import Player, PlayerProjection, Snapshot
from engine.optimize import pick_captains, solve_squad, solve_xi
from engine.project import project_all

SEED = 7
STRATEGY = "balanced"
OBJECTIVE = "next"
MINUTES_VERSION = "v2am_fpla"
RATES_VERSION = "v1"
FIXTURES_VERSION = "v1"
G_STAR = 20
POLICY_ID = "E046-A"
MIN_HELD_FOR_XI = 11

CLAIM = (
    "Under the frozen E046-A policy, the model recommends Free Hit "
    "in the GW where blank-slate XI utility lift over the sticky held XI is highest."
)

INDEPENDENCE = (
    "Independent of Triple Captain (E040-A) and Bench Boost (E041-A): "
    "this is not a combined chip calendar. Joint feasibility is not claimed."
)


@dataclass(frozen=True)
class FhRow:
    gw: int
    u_blank: float
    u_held: float
    u_fh: float
    excluded: bool
    exclude_reason: str


def select_t_star(rows: Iterable[FhRow]) -> FhRow:
    """C: argmax U_FH among non-excluded rows; tie → lowest GW."""
    usable = [r for r in rows if not r.excluded]
    if not usable:
        raise ValueError("select_t_star requires at least one non-excluded FhRow")
    return sorted(usable, key=lambda r: (-r.u_fh, r.gw))[0]


def effective_g_star(included_gws: list[int], g_star: int = G_STAR) -> int | None:
    """If g* excluded, nearest lower included GW; else nearest higher."""
    if not included_gws:
        return None
    if g_star in included_gws:
        return g_star
    lower = [g for g in included_gws if g < g_star]
    if lower:
        return max(lower)
    higher = [g for g in included_gws if g > g_star]
    return min(higher) if higher else None


def project_e046(snapshot: Snapshot, *, horizon: int = 1) -> list[PlayerProjection]:
    return project_all(
        snapshot,
        horizon=horizon,
        strategy=STRATEGY,
        seed=SEED,
        minutes_version=MINUTES_VERSION,
        rates_version=RATES_VERSION,
        fixtures_version=FIXTURES_VERSION,
    )


def next_xi_utility(
    xi: list[Player],
    captain: Player,
    by_id: dict[int, PlayerProjection],
) -> float:
    return sum(by_id[p.id].next_utility for p in xi) + by_id[captain.id].next_utility


def blank_slate(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
):
    return solve_squad(
        snapshot, projections, strategy=STRATEGY, objective=OBJECTIVE
    )


def held_xi(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    held_ids: list[int],
) -> tuple[list[Player], list[Player], Player, float, str | None]:
    """Return (xi, bench, capt, u_held, exclude_reason)."""
    by_id = {p.player.id: p for p in projections}
    by_player = {p.id: p for p in snapshot.players}
    squad: list[Player] = []
    for pid in held_ids:
        p = by_player.get(pid)
        if p is None or pid not in by_id:
            continue
        squad.append(p)
    if len(squad) < MIN_HELD_FOR_XI:
        return [], [], snapshot.players[0], 0.0, f"held_n={len(squad)}<{MIN_HELD_FOR_XI}"
    try:
        xi, bench = solve_xi(snapshot, squad, by_id)
        capt, _ = pick_captains(xi, by_id)
    except RuntimeError as e:
        return [], [], snapshot.players[0], 0.0, f"solve_xi:{e}"
    u = next_xi_utility(xi, capt, by_id)
    return xi, bench, capt, u, None


def ensure_e046_data(seasons: tuple[str, ...] | None = None) -> None:
    ensure_fplcache_avail(seasons)
