"""E022 packaging: minutes-reliability weight on fixture muDelta into decision U.

Contract (LAB_LOG E022):
  U = (1 - q) * mu_v1 + q * mu_v2d
  q = clip(recent4 / 90, 0, 1)
  as_of_gw <= 4 -> q = 1

Prediction mu_v2d is left intact for MAE; only decision utilities change.
"""
from __future__ import annotations

from dataclasses import replace

from engine.models import PlayerProjection
from engine.project import utility

Q_RECENT_DENOM = 90.0
Q_EARLY_GW = 4  # as_of_gw <= this -> q = 1


def minutes_reliability_q(recent4: int, as_of_gw: int) -> float:
    if as_of_gw <= Q_EARLY_GW:
        return 1.0
    return max(0.0, min(1.0, float(recent4) / Q_RECENT_DENOM))


def packaged_mu(mu_v1: float, mu_v2d: float, q: float) -> float:
    return (1.0 - q) * mu_v1 + q * mu_v2d


def apply_packaged_next_utility(
    projs_v2d: list[PlayerProjection],
    projs_v1: list[PlayerProjection],
    recent_minutes: dict[int, int],
    as_of_gw: int,
    strategy: str,
) -> list[PlayerProjection]:
    """Return v2d projections with next_utility / horizon_utility from packaged U.

    next_mu stays mu_v2d (MAE scored on prediction, not U).
    """
    by_v1 = {p.player.id: p for p in projs_v1}
    out: list[PlayerProjection] = []
    for pv in projs_v2d:
        pid = pv.player.id
        p1 = by_v1.get(pid)
        if p1 is None:
            out.append(pv)
            continue
        q = minutes_reliability_q(recent_minutes.get(pid, 0), as_of_gw)
        u_mu = packaged_mu(p1.next_mu, pv.next_mu, q)
        # Balanced strategy: utility(U)=U. Keep sigma/p10 from v2d for non-balanced.
        next_u = utility(u_mu, pv.next_sigma, pv.next_p_10, strategy)
        # Horizon-1 harness uses objective=next; still rewrite horizon_utility
        # so accidental horizon solves cannot bypass packaging.
        hor_u = utility(u_mu, pv.horizon_sigma, pv.next_p_10, strategy)
        out.append(replace(pv, next_utility=next_u, horizon_utility=hor_u))
    return out
