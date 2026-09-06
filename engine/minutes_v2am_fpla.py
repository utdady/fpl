"""E044-A: v2am_fpla — fplcache decision-time availability on v2am_s base.

minutes_version=v2am_fpla (LAB_LOG E044-A):
  overlay status/chance_*/can_select from last fplcache snap ≤ deadline
  b0 = v2am_s role_start; p_start via existing availability(player, 0)
"""
from __future__ import annotations

from dataclasses import dataclass

from engine.fplcache_avail import hydrate_players, load_overlay
from engine.minutes import availability
from engine.minutes_struct import build_role_start_struct
from engine.models import Player


@dataclass(frozen=True)
class FplaDiag:
    player_id: int
    web_name: str
    team_id: int
    position: str
    b0: float
    identity_reason: str
    status: str
    chance_this: int | None
    chance_next: int | None
    can_select: bool
    availability0: float
    joined: bool


def build_role_start_v2am_fpla(
    players: list[Player],
    *,
    season: str | None,
    as_of_gw: int,
    recent_minutes: dict[int, int] | None = None,
    apply_recent: bool = False,
) -> tuple[dict[int, float], list[Player], list[FplaDiag]]:
    """Return (role_start, hydrated_players, diags).

    Live / missing overlay → identity players (same objects) and v2am_s bases.
    """
    gw_identity = False
    join_reasons: list[str]
    if not season:
        hydrated = list(players)
        join_reasons = ["no_season"] * len(players)
        gw_identity = True
    else:
        overlay = load_overlay(season, as_of_gw)
        if overlay is None:
            hydrated = list(players)
            join_reasons = ["no_overlay"] * len(players)
            gw_identity = True
        else:
            hydrated, join_reasons = hydrate_players(players, overlay)

    b0 = build_role_start_struct(
        hydrated, recent_minutes=recent_minutes, apply_recent=apply_recent
    )
    diags: list[FplaDiag] = []
    for p, reason in zip(hydrated, join_reasons):
        joined = reason == "joined_id"
        ident = reason if (gw_identity or not joined) else ""
        diags.append(
            FplaDiag(
                player_id=p.id,
                web_name=p.web_name,
                team_id=p.team_id,
                position=p.position,
                b0=float(b0[p.id]),
                identity_reason=ident,
                status=p.status,
                chance_this=p.chance_this,
                chance_next=p.chance_next,
                can_select=p.can_select,
                availability0=float(availability(p, 0)),
                joined=joined and not gw_identity,
            )
        )
    return b0, hydrated, diags
