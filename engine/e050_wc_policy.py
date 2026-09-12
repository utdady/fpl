"""E050-A frozen Wildcard policy (historical evaluator).

Contract (docs/LAB_LOG.md E050-A):
  Degeneracy lock: B0 = sticky HELD_0 (never weekly blank-slate).
  After WC: REPLACE held with BLANK(t_chip).players (not FH revert).
  C: t* = argmax_t U_WC(t), tie → lowest GW
  U_WC(t) = sum_{τ>=t} [U_xi(BLANK(t).players,τ) - U_xi(HELD_0,τ)] under I_t
  Stack: v2am_fpla + rates=v1 + fixtures v1; balanced; objective=next; seed=7
  g* = 20 (B1 only); N_WC = 1

Any change requires a new preregistered experiment.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from engine.e040_tc_policy import bind_next_to_event
from engine.e046_fh_policy import (
    G_STAR,
    blank_slate,
    effective_g_star,
    freeze_held_0,
    held_xi,
    next_xi_utility,
)
from engine.fplcache_avail import ensure_fplcache_avail
from engine.models import PlayerProjection, Snapshot
from engine.project import project_all

SEED = 7
STRATEGY = "balanced"
OBJECTIVE = "next"
MINUTES_VERSION = "v2am_fpla"
RATES_VERSION = "v1"
FIXTURES_VERSION = "v1"
POLICY_ID = "E050-A"
N_WC = 1

CLAIM = (
    "Under the frozen E050-A policy, the model recommends Wildcard "
    "in the GW where forward blank-slate XI utility lift over sticky HELD_0 "
    "is highest (persistent replace, not Free Hit revert)."
)

INDEPENDENCE = (
    "Independent of Triple Captain (E040-A), Bench Boost (E041-A), and "
    "Free Hit (E046-A): this is not a combined chip calendar. "
    "Joint feasibility is not claimed."
)


@dataclass(frozen=True)
class WcRow:
    gw: int
    u_wc: float
    n_tau: int
    blank_ids: tuple[int, ...]
    excluded: bool
    exclude_reason: str


def select_t_star(rows: Iterable[WcRow]) -> WcRow:
    """C: argmax U_WC among non-excluded rows; tie → lowest GW."""
    usable = [r for r in rows if not r.excluded]
    if not usable:
        raise ValueError("select_t_star requires at least one non-excluded WcRow")
    return sorted(usable, key=lambda r: (-r.u_wc, r.gw))[0]


def project_e050(snapshot: Snapshot, *, horizon: int = 1) -> list[PlayerProjection]:
    return project_all(
        snapshot,
        horizon=horizon,
        strategy=STRATEGY,
        seed=SEED,
        minutes_version=MINUTES_VERSION,
        rates_version=RATES_VERSION,
        fixtures_version=FIXTURES_VERSION,
    )


def ensure_e050_data(seasons: tuple[str, ...] | None = None) -> None:
    ensure_fplcache_avail(seasons)


def u_xi_for_ids(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    held_ids: list[int],
) -> tuple[float, str | None]:
    """Return (U_xi, exclude_reason)."""
    _xi, _b, _c, u, excl = held_xi(snapshot, projections, held_ids)
    if excl is not None:
        return 0.0, excl
    return float(u), None


def compute_u_wc(
    snapshot: Snapshot,
    held0_ids: list[int],
    candidate_gw: int,
) -> WcRow:
    """Forward U_WC under I_t for candidate fire week candidate_gw."""
    next_e = snapshot.next_event()
    remaining = [
        e.id
        for e in snapshot.events
        if e.id >= max(next_e.id, candidate_gw) and e.id <= 38
    ]
    if not remaining:
        return WcRow(candidate_gw, 0.0, 0, (), True, "no_remaining")

    projections = project_e050(snapshot, horizon=len(remaining))
    bound_t = bind_next_to_event(projections, candidate_gw)
    try:
        sol = blank_slate(snapshot, bound_t)
    except RuntimeError as e:
        return WcRow(candidate_gw, 0.0, 0, (), True, f"blank:{e}")

    blank_ids = [p.id for p in sol.players]
    total = 0.0
    n_tau = 0
    for tau in remaining:
        bound = bind_next_to_event(projections, tau)
        u_b, excl_b = u_xi_for_ids(snapshot, bound, blank_ids)
        u_h, excl_h = u_xi_for_ids(snapshot, bound, held0_ids)
        if excl_b is not None or excl_h is not None:
            continue
        total += u_b - u_h
        n_tau += 1

    if n_tau == 0:
        return WcRow(
            candidate_gw, 0.0, 0, tuple(blank_ids), True, "no_scoreable_tau"
        )
    return WcRow(
        gw=candidate_gw,
        u_wc=float(total),
        n_tau=n_tau,
        blank_ids=tuple(blank_ids),
        excluded=False,
        exclude_reason="",
    )


def season_cap_with_replace(
    *,
    included_gws: list[int],
    cap_held0: dict[int, float],
    cap_blank: dict[int, float],
    blank_ids_by_gw: dict[int, list[int]],
    chip_gw: int | None,
    snap_act_cap_fn,
) -> float:
    """Season Cap under one WC at chip_gw with REPLACE semantics."""
    if chip_gw is None or chip_gw not in cap_held0:
        return sum(cap_held0[g] for g in included_gws)

    blank_ids = blank_ids_by_gw.get(chip_gw)
    if not blank_ids:
        return sum(cap_held0[g] for g in included_gws)

    total = 0.0
    for gw in included_gws:
        if gw < chip_gw:
            total += cap_held0[gw]
        elif gw == chip_gw:
            total += cap_blank[gw]
        else:
            total += float(snap_act_cap_fn(gw, blank_ids))
    return total


LIVE_SEMANTICS = (
    "Past GWs use as-of-t freezes when available; current and future GWs "
    "are scored under the current information set I_N only "
    "(unique online completion of argmax U_WC with sticky held; "
    "firing REPLACE held with blank 15 thereafter — not FH revert)."
)

GATE_NOTE = (
    "E050-A SURVIVE: AGG C-B1=+247; FAIL cleared. "
    "C loses to calendar B1 on 2022-23 (-174) and 2024-25 (-10) alone; "
    "gate uses four-season sums (same discipline as E040/E046)."
)


@dataclass(frozen=True)
class WcRecommendation:
    policy_id: str
    t_star: int
    u_wc: float
    n_tau: int
    blank_ids: tuple[int, ...]
    blank_names: tuple[str, ...]
    held_ids: tuple[int, ...]
    held_freeze_gw: int | None
    claim: str
    rows: tuple[WcRow, ...]
    live_semantics: str


def _names_for_ids(snapshot: Snapshot, ids: tuple[int, ...] | list[int]) -> tuple[str, ...]:
    by_id = {p.id: p.web_name for p in snapshot.players}
    return tuple(by_id.get(i, str(i)) for i in ids)


def freeze_held_live(snapshot: Snapshot) -> list[int]:
    """I_N held freeze: blank-slate 15 on the live snapshot (no owned squad)."""
    projs = project_e050(snapshot, horizon=1)
    sol = blank_slate(snapshot, projs)
    return [p.id for p in sol.players]


def rows_as_of_t_season(season: str) -> tuple[list[WcRow], list[int], int]:
    """Historical path: sticky HELD_0 + forward U_WC under each as-of-t snap."""
    from engine.harness import build_snapshot, ensure_vaastav, gw_actuals
    from engine.metrics import record_path

    ensure_vaastav((season,))
    ensure_e050_data((season,))
    held_ids, held_gw = freeze_held_0(season)
    rows: list[WcRow] = []
    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        snap = build_snapshot(season, as_of_gw=gw)
        if not gw_actuals(season, gw):
            continue
        rows.append(compute_u_wc(snap, held_ids, gw))
    return rows, held_ids, held_gw


def rows_live_remaining(
    snapshot: Snapshot,
    held_ids: list[int],
) -> list[WcRow]:
    """Score each remaining GW as a WC candidate under I_N."""
    next_e = snapshot.next_event()
    remaining = [e.id for e in snapshot.events if e.id >= next_e.id and e.id <= 38]
    return [compute_u_wc(snapshot, held_ids, gw) for gw in remaining]


def recommend_from_rows(
    rows: list[WcRow],
    held_ids: list[int],
    *,
    held_freeze_gw: int | None,
    snapshot: Snapshot | None = None,
) -> WcRecommendation:
    best = select_t_star(rows)
    blank_names: tuple[str, ...] = ()
    if snapshot is not None and best.blank_ids:
        blank_names = _names_for_ids(snapshot, best.blank_ids)
    return WcRecommendation(
        policy_id=POLICY_ID,
        t_star=best.gw,
        u_wc=best.u_wc,
        n_tau=best.n_tau,
        blank_ids=best.blank_ids,
        blank_names=blank_names,
        held_ids=tuple(held_ids),
        held_freeze_gw=held_freeze_gw,
        claim=CLAIM,
        rows=tuple(rows),
        live_semantics=LIVE_SEMANTICS,
    )


def recommend_historical(season: str) -> WcRecommendation:
    from engine.harness import build_snapshot

    rows, held_ids, held_gw = rows_as_of_t_season(season)
    if not any(not r.excluded for r in rows):
        raise RuntimeError(f"{season}: no non-excluded GWs for E050-A WC")
    best = select_t_star(rows)
    snap = build_snapshot(season, as_of_gw=best.gw)
    return recommend_from_rows(
        rows, held_ids, held_freeze_gw=held_gw, snapshot=snap
    )


def recommend_live(
    snapshot: Snapshot,
    held_ids: list[int] | None = None,
) -> WcRecommendation:
    held = list(held_ids) if held_ids is not None else freeze_held_live(snapshot)
    if len(held) < 11:
        raise RuntimeError(f"E050-A WC needs >= 11 held ids; got {len(held)}")
    rows = rows_live_remaining(snapshot, held)
    if not any(not r.excluded for r in rows):
        raise RuntimeError("No remaining GWs to score for E050-A WC recommendation")
    return recommend_from_rows(rows, held, held_freeze_gw=None, snapshot=snapshot)


def format_recommendation(rec: WcRecommendation) -> str:
    blank = ", ".join(rec.blank_names) if rec.blank_names else "(see blank_ids)"
    held_note = (
        f"GW{rec.held_freeze_gw}" if rec.held_freeze_gw is not None else "I_N / --squad"
    )
    lines = [
        f"Policy: {rec.policy_id} (frozen Wildcard)",
        rec.claim,
        INDEPENDENCE,
        "",
        f"  planned GW:  {rec.t_star}",
        f"  U_WC(t*):    {rec.u_wc:.4f}  (forward sum over n_tau={rec.n_tau})",
        f"  blank 15:    {blank}",
        f"  held freeze: {held_note} ({len(rec.held_ids)} ids)",
        "  after fire:  REPLACE held with blank 15 (not Free Hit revert)",
        "",
        f"Live semantics: {rec.live_semantics}",
        f"Scored GWs: {len(rec.rows)} "
        f"({sum(1 for r in rec.rows if not r.excluded)} included)",
        GATE_NOTE,
    ]
    return "\n".join(lines) + "\n"
