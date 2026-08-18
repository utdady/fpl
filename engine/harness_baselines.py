"""Historical baseline projections for harness comparison."""
from __future__ import annotations

from engine.harness import gw_xp, prior_points_by_element, prior_pp90_by_element
from engine.models import Player, PlayerProjection, Snapshot


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


def baseline_b0_xp(season: str, gw: int, snapshot: Snapshot) -> list[PlayerProjection]:
    """Official FPL xP from Vaastav GW file. Benchmark only; possible timing leakage."""
    xp = gw_xp(season, gw)
    return [_fake(p, xp.get(p.id, 0.0)) for p in snapshot.players]


def baseline_b1_season_points(
    snapshot: Snapshot,
    gw: int,
    prior_pts: dict[int, int],
) -> list[PlayerProjection]:
    """ILP utility from season points (GW1: prior season total; GW2+: current cumulative)."""
    out = []
    for p in snapshot.players:
        if gw == 1:
            score = float(prior_pts.get(p.id, 0))
        else:
            score = float(p.total_points)
        out.append(_fake(p, score))
    return out


def baseline_b1_gw_prediction(
    snapshot: Snapshot,
    gw: int,
    prior_pts: dict[int, int],
) -> dict[int, float]:
    """Per-GW point prediction on same scale as V1 mu (for MAE)."""
    preds: dict[int, float] = {}
    for p in snapshot.players:
        if gw == 1:
            preds[p.id] = prior_pts.get(p.id, 0) / 38.0
        elif gw > 1 and p.total_points > 0:
            preds[p.id] = p.total_points / (gw - 1)
        else:
            preds[p.id] = prior_pts.get(p.id, 0) / 38.0
    return preds


def baseline_b2_naive_pp90(
    snapshot: Snapshot,
    gw: int,
    prior_pp90: dict[int, float],
) -> list[PlayerProjection]:
    """Points per 90 with minutes>=900 floor (ILP utility)."""
    out = []
    for p in snapshot.players:
        if gw == 1:
            score = prior_pp90.get(p.id, 0.0)
        elif p.minutes >= 900:
            score = p.total_points / (p.minutes / 90.0)
        else:
            score = 0.0
        out.append(_fake(p, score))
    return out


def baseline_b2_gw_prediction(
    snapshot: Snapshot,
    gw: int,
    prior_pp90: dict[int, float],
) -> dict[int, float]:
    """Per-GW prediction proxy: pp90 treated as expected GW points if starting."""
    preds: dict[int, float] = {}
    for p in snapshot.players:
        if gw == 1:
            preds[p.id] = prior_pp90.get(p.id, 0.0)
        elif p.minutes >= 900:
            preds[p.id] = p.total_points / (p.minutes / 90.0)
        else:
            preds[p.id] = prior_pp90.get(p.id, 0.0)
    return preds


def baseline_b3_v1(projections: list[PlayerProjection]) -> list[PlayerProjection]:
    return projections
