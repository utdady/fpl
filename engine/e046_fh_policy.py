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


LIVE_SEMANTICS = (
    "Past GWs use as-of-t freezes when available; current and future GWs "
    "are scored under the current information set I_N only "
    "(unique online completion of argmax U_FH with sticky held)."
)


@dataclass(frozen=True)
class FhRecommendation:
    policy_id: str
    t_star: int
    u_fh: float
    u_blank: float
    u_held: float
    blank_ids: tuple[int, ...]
    blank_names: tuple[str, ...]
    held_ids: tuple[int, ...]
    held_freeze_gw: int | None
    claim: str
    rows: tuple[FhRow, ...]
    live_semantics: str


def freeze_held_0(season: str) -> tuple[list[int], int]:
    """HELD_0 = blank-slate 15 at first usable GW (E046-A)."""
    from engine.harness import build_snapshot, ensure_vaastav, gw_actuals
    from engine.metrics import record_path

    ensure_vaastav((season,))
    ensure_e046_data((season,))
    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        snap = build_snapshot(season, as_of_gw=gw)
        if not gw_actuals(season, gw):
            continue
        projs = project_e046(snap, horizon=1)
        try:
            sol = blank_slate(snap, projs)
        except RuntimeError:
            continue
        return [p.id for p in sol.players], gw
    raise RuntimeError(f"{season}: no usable GW to freeze HELD_0")


def fh_row_from_projections(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    held_ids: list[int],
    gw: int,
) -> FhRow:
    xi_h, _b, capt_h, u_held, excl = held_xi(snapshot, projections, held_ids)
    if excl is not None:
        return FhRow(gw, 0.0, 0.0, 0.0, True, excl)
    try:
        sol = blank_slate(snapshot, projections)
    except RuntimeError as e:
        return FhRow(gw, 0.0, u_held, 0.0, True, f"blank:{e}")
    by_id = {p.player.id: p for p in projections}
    u_blank = next_xi_utility(sol.xi, sol.captain, by_id)
    return FhRow(
        gw=gw,
        u_blank=float(u_blank),
        u_held=float(u_held),
        u_fh=float(u_blank - u_held),
        excluded=False,
        exclude_reason="",
    )


def rows_as_of_t_season(season: str) -> tuple[list[FhRow], list[int], int]:
    """Historical evaluator path: sticky HELD_0 + as-of-t U_FH each GW."""
    from engine.harness import build_snapshot, ensure_vaastav, gw_actuals
    from engine.metrics import record_path

    ensure_vaastav((season,))
    ensure_e046_data((season,))
    held_ids, held_gw = freeze_held_0(season)
    rows: list[FhRow] = []
    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        snap = build_snapshot(season, as_of_gw=gw)
        if not gw_actuals(season, gw):
            continue
        projs = project_e046(snap, horizon=1)
        rows.append(fh_row_from_projections(snap, projs, held_ids, gw))
    return rows, held_ids, held_gw


def rows_live_remaining(
    snapshot: Snapshot,
    held_ids: list[int],
) -> list[FhRow]:
    """Score current + future GWs under I_N with sticky held_ids."""
    from engine.e040_tc_policy import bind_next_to_event

    next_e = snapshot.next_event()
    remaining = [e.id for e in snapshot.events if e.id >= next_e.id and e.id <= 38]
    if not remaining:
        return []
    projections = project_e046(snapshot, horizon=len(remaining))
    rows: list[FhRow] = []
    for gw in remaining:
        bound = bind_next_to_event(projections, gw)
        rows.append(fh_row_from_projections(snapshot, bound, held_ids, gw))
    return rows


def freeze_held_live(snapshot: Snapshot) -> list[int]:
    """I_N held freeze: blank-slate 15 on the live snapshot (no owned squad)."""
    projs = project_e046(snapshot, horizon=1)
    sol = blank_slate(snapshot, projs)
    return [p.id for p in sol.players]


def recommend_from_rows(
    rows: list[FhRow],
    held_ids: list[int],
    *,
    held_freeze_gw: int | None,
    snapshot: Snapshot | None = None,
    projections_at_star: list[PlayerProjection] | None = None,
) -> FhRecommendation:
    best = select_t_star(rows)
    blank_ids: tuple[int, ...] = ()
    blank_names: tuple[str, ...] = ()
    if snapshot is not None and projections_at_star is not None:
        try:
            sol = blank_slate(snapshot, projections_at_star)
            blank_ids = tuple(p.id for p in sol.xi)
            blank_names = tuple(p.web_name for p in sol.xi)
        except RuntimeError:
            pass
    return FhRecommendation(
        policy_id=POLICY_ID,
        t_star=best.gw,
        u_fh=best.u_fh,
        u_blank=best.u_blank,
        u_held=best.u_held,
        blank_ids=blank_ids,
        blank_names=blank_names,
        held_ids=tuple(held_ids),
        held_freeze_gw=held_freeze_gw,
        claim=CLAIM,
        rows=tuple(rows),
        live_semantics=LIVE_SEMANTICS,
    )


def recommend_historical(season: str) -> FhRecommendation:
    from engine.harness import build_snapshot

    rows, held_ids, held_gw = rows_as_of_t_season(season)
    if not any(not r.excluded for r in rows):
        raise RuntimeError(f"{season}: no non-excluded GWs for E046-A FH")
    best = select_t_star(rows)
    snap = build_snapshot(season, as_of_gw=best.gw)
    projs = project_e046(snap, horizon=1)
    return recommend_from_rows(
        rows,
        held_ids,
        held_freeze_gw=held_gw,
        snapshot=snap,
        projections_at_star=projs,
    )


def recommend_live(
    snapshot: Snapshot,
    held_ids: list[int] | None = None,
) -> FhRecommendation:
    held = list(held_ids) if held_ids is not None else freeze_held_live(snapshot)
    if len(held) < MIN_HELD_FOR_XI:
        raise RuntimeError(
            f"E046-A FH needs >= {MIN_HELD_FOR_XI} held ids; got {len(held)}"
        )
    rows = rows_live_remaining(snapshot, held)
    usable = [r for r in rows if not r.excluded]
    if not usable:
        raise RuntimeError("No remaining GWs to score for E046-A FH recommendation")
    from engine.e040_tc_policy import bind_next_to_event

    best = select_t_star(rows)
    next_e = snapshot.next_event()
    remaining = [e.id for e in snapshot.events if e.id >= next_e.id and e.id <= 38]
    projections = project_e046(snapshot, horizon=len(remaining))
    bound = bind_next_to_event(projections, best.gw)
    return recommend_from_rows(
        rows,
        held,
        held_freeze_gw=None,
        snapshot=snapshot,
        projections_at_star=bound,
    )


def format_recommendation(rec: FhRecommendation) -> str:
    blank = ", ".join(rec.blank_names) if rec.blank_names else "(see blank_ids)"
    held_note = (
        f"GW{rec.held_freeze_gw}" if rec.held_freeze_gw is not None else "I_N / --squad"
    )
    lines = [
        f"Policy: {rec.policy_id} (frozen Free Hit)",
        rec.claim,
        INDEPENDENCE,
        "",
        f"  planned GW:  {rec.t_star}",
        f"  U_FH(t*):    {rec.u_fh:.4f}  (blank {rec.u_blank:.4f} - held {rec.u_held:.4f})",
        f"  blank XI:    {blank}",
        f"  held freeze: {held_note} ({len(rec.held_ids)} ids)",
        "",
        f"Live semantics: {rec.live_semantics}",
        f"Scored GWs: {len(rec.rows)} "
        f"({sum(1 for r in rec.rows if not r.excluded)} included)",
        "Note: E046-A SURVIVE was razor-thin (+2 AGG vs calendar B1); "
        "independent of TC/BB; not a joint chip calendar.",
    ]
    return "\n".join(lines) + "\n"
