"""E045-A: rates_version=v1_ep — blend dated fplcache ep_next into next-GW μ.

μ1 = (1-λ)·μ0 + λ·e   with λ=0.35
Does not hydrate Player.ep_next (minutes path stays blind).
Keeps control σ and p_10_plus; only μ (and utility from μ) shifts.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from engine.fplcache_ep import EP_LAMBDA, blend_mu, load_ep_next
from engine.models import PlayerProjection

DECAY = 0.90  # match engine.project.DECAY; avoid circular import


def _utility(mu: float, sigma: float, p10: float, strategy: str) -> float:
    if strategy == "safe":
        return mu - 0.40 * sigma
    if strategy == "aggressive":
        return mu + 3.0 * p10
    return mu


@dataclass(frozen=True)
class EpDiag:
    player_id: int
    web_name: str
    mu0: float
    ep_next: float | None
    mu1: float
    blended: bool
    identity_reason: str


def apply_ep_blend(
    projections: list[PlayerProjection],
    *,
    season: str | None,
    as_of_gw: int,
    strategy: str,
    live_ep: dict[int, float] | None = None,
    lam: float = EP_LAMBDA,
) -> tuple[list[PlayerProjection], list[EpDiag]]:
    """Blend next-GW μ only. Horizon beyond next GW unchanged."""
    overlay: dict[int, float] | None
    gw_reason = ""
    if season:
        overlay = load_ep_next(season, as_of_gw)
        if overlay is None:
            overlay = {}
            gw_reason = "no_overlay"
    elif live_ep:
        overlay = live_ep
    else:
        overlay = {}
        gw_reason = "no_season"

    out: list[PlayerProjection] = []
    diags: list[EpDiag] = []
    for proj in projections:
        pid = proj.player.id
        mu0 = float(proj.next_mu)
        if gw_reason:
            e = None
            reason = gw_reason
            mu1, blended = mu0, False
        else:
            e = overlay.get(pid)
            if e is None and live_ep is not None and season is None:
                e = live_ep.get(pid)
            mu1, blended = blend_mu(mu0, e, lam=lam)
            reason = "" if blended else "missing_ep"

        by_gw = dict(proj.by_gw)
        if by_gw:
            first_gw = min(by_gw.keys())
            g0 = by_gw[first_gw]
            by_gw[first_gw] = replace(g0, mu=mu1)

        h_mu = 0.0
        h_var = 0.0
        h_u = 0.0
        for offset, gw in enumerate(sorted(by_gw.keys())):
            pred = by_gw[gw]
            w = DECAY ** offset
            h_mu += w * pred.mu
            h_var += (w * pred.sigma) ** 2
            h_u += w * _utility(pred.mu, pred.sigma, pred.p_10_plus, strategy)

        out.append(
            PlayerProjection(
                player=proj.player,
                by_gw=by_gw,
                horizon_mu=h_mu,
                horizon_sigma=(h_var ** 0.5),
                horizon_utility=h_u,
                next_mu=mu1,
                next_sigma=proj.next_sigma,
                next_p_start=proj.next_p_start,
                next_p_60=proj.next_p_60,
                next_p_10=proj.next_p_10,
                next_utility=_utility(mu1, proj.next_sigma, proj.next_p_10, strategy),
            )
        )
        diags.append(
            EpDiag(
                player_id=pid,
                web_name=proj.player.web_name,
                mu0=mu0,
                ep_next=e,
                mu1=mu1,
                blended=blended,
                identity_reason=reason,
            )
        )
    return out, diags
