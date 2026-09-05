"""E040-A frozen Triple Captain policy (shared offline ↔ product).

Contract (docs/LAB_LOG.md E040-A):
  C: t* = argmax_t U_capt(t), tie → lowest GW
  U_capt(t) = next_utility of pick_captains on production XI at t
  Stack: v2am_s + rates=v1 + fixtures v1; balanced; objective=next; seed=7

Live semantics (charter §19):
  Past GWs: as-of-t (same as historical evaluator) when rebuildable.
  Current + future: scored under current information set I_N only.

Any change to this policy requires a new preregistered experiment.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from engine.models import PlayerProjection, Snapshot
from engine.optimize import pick_captains, solve_squad
from engine.project import project_all, utility

# Frozen E040-A constants — do not retune without a new prereg.
SEED = 7
STRATEGY = "balanced"
OBJECTIVE = "next"
MINUTES_VERSION = "v2am_s"
RATES_VERSION = "v1"
FIXTURES_VERSION = "v1"
G_STAR = 20  # B1 benchmark only; not used by C
POLICY_ID = "E040-A"


@dataclass(frozen=True)
class CaptRow:
    gw: int
    captain_id: int
    captain_name: str
    u_capt: float
    source: str  # "as_of_t" | "live_I_N"


@dataclass(frozen=True)
class TCRecommendation:
    policy_id: str
    t_star: int
    captain_id: int
    captain_name: str
    u_capt: float
    claim: str
    rows: tuple[CaptRow, ...]
    live_semantics: str


CLAIM = (
    "Under the frozen E040-A policy, the model recommends Triple Captain "
    "in the GW where projected captain utility is highest."
)

LIVE_SEMANTICS = (
    "Past GWs use as-of-t freezes when available; current and future GWs "
    "are scored under the current information set I_N only "
    "(unique online completion of argmax U_capt)."
)


def select_t_star(rows: Iterable[CaptRow]) -> CaptRow:
    """C: argmax U_capt; tie → lowest GW."""
    rows = list(rows)
    if not rows:
        raise ValueError("select_t_star requires at least one CaptRow")
    return sorted(rows, key=lambda r: (-r.u_capt, r.gw))[0]


def captain_row_from_projections(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    gw: int,
    *,
    source: str,
) -> CaptRow | None:
    """Solve production squad on next_utility; return U_capt for this scoring."""
    try:
        sol = solve_squad(
            snapshot, projections, strategy=STRATEGY, objective=OBJECTIVE
        )
    except RuntimeError:
        return None
    by_id = {p.player.id: p for p in projections}
    capt, _ = pick_captains(sol.xi, by_id)
    u = by_id[capt.id].next_utility
    return CaptRow(
        gw=gw,
        captain_id=capt.id,
        captain_name=capt.web_name,
        u_capt=float(u),
        source=source,
    )


def project_e040(
    snapshot: Snapshot,
    *,
    horizon: int = 1,
    seed: int = SEED,
) -> list[PlayerProjection]:
    return project_all(
        snapshot,
        horizon=horizon,
        strategy=STRATEGY,
        seed=seed,
        minutes_version=MINUTES_VERSION,
        rates_version=RATES_VERSION,
        fixtures_version=FIXTURES_VERSION,
    )


def bind_next_to_event(
    projections: list[PlayerProjection],
    event_id: int,
    strategy: str = STRATEGY,
) -> list[PlayerProjection]:
    """Rebind next_* fields to a specific GW's projection (live I_N scoring)."""
    out: list[PlayerProjection] = []
    for p in projections:
        gw = p.by_gw.get(event_id)
        if gw is None or gw.n_fixtures == 0:
            nxt_u = -50.0
            out.append(
                replace(
                    p,
                    next_mu=0.0,
                    next_sigma=0.0,
                    next_p_start=0.0,
                    next_p_60=0.0,
                    next_p_10=0.0,
                    next_utility=nxt_u,
                )
            )
            continue
        nxt_u = utility(gw.mu, gw.sigma, gw.p_10_plus, strategy)
        out.append(
            replace(
                p,
                next_mu=gw.mu,
                next_sigma=gw.sigma,
                next_p_start=gw.p_start,
                next_p_60=gw.p_60,
                next_p_10=gw.p_10_plus,
                next_utility=nxt_u,
            )
        )
    return out


def rows_as_of_t_season(season: str) -> list[CaptRow]:
    """Historical evaluator path: as-of-t for each GW with records."""
    from engine.harness import build_snapshot, ensure_vaastav, gw_actuals
    from engine.metrics import record_path

    ensure_vaastav((season,))
    rows: list[CaptRow] = []
    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        snap = build_snapshot(season, as_of_gw=gw)
        if not gw_actuals(season, gw):
            continue
        projections = project_e040(snap, horizon=1)
        row = captain_row_from_projections(snap, projections, gw, source="as_of_t")
        if row is not None:
            rows.append(row)
    return rows


def rows_live_remaining(snapshot: Snapshot) -> list[CaptRow]:
    """Score current + future GWs under I_N (current snapshot)."""
    next_e = snapshot.next_event()
    remaining = [e.id for e in snapshot.events if e.id >= next_e.id]
    if not remaining:
        return []
    # Cap at GW 38 for E040 W.
    remaining = [g for g in remaining if g <= 38]
    if not remaining:
        return []
    horizon = len(remaining)
    projections = project_e040(snapshot, horizon=horizon)
    rows: list[CaptRow] = []
    for gw in remaining:
        bound = bind_next_to_event(projections, gw)
        row = captain_row_from_projections(
            snapshot, bound, gw, source="live_I_N"
        )
        if row is not None:
            rows.append(row)
    return rows


def recommend_from_rows(rows: list[CaptRow]) -> TCRecommendation:
    best = select_t_star(rows)
    return TCRecommendation(
        policy_id=POLICY_ID,
        t_star=best.gw,
        captain_id=best.captain_id,
        captain_name=best.captain_name,
        u_capt=best.u_capt,
        claim=CLAIM,
        rows=tuple(rows),
        live_semantics=LIVE_SEMANTICS,
    )


def recommend_historical(season: str) -> TCRecommendation:
    return recommend_from_rows(rows_as_of_t_season(season))


def recommend_live(snapshot: Snapshot) -> TCRecommendation:
    rows = rows_live_remaining(snapshot)
    if not rows:
        raise RuntimeError("No remaining GWs to score for E040-A TC recommendation")
    return recommend_from_rows(rows)


def format_recommendation(rec: TCRecommendation) -> str:
    lines = [
        f"Policy: {rec.policy_id} (frozen Triple Captain)",
        rec.claim,
        "",
        f"  planned GW:  {rec.t_star}",
        f"  captain:     {rec.captain_name} (id={rec.captain_id})",
        f"  U_capt(t*):  {rec.u_capt:.4f}",
        f"  incremental: ~{rec.u_capt:.4f} projected pts vs normal captain "
        f"(TC adds one extra copy of captain xP under mu)",
        "",
        f"Live semantics: {rec.live_semantics}",
        f"Scored GWs: {len(rec.rows)}",
    ]
    return "\n".join(lines) + "\n"
