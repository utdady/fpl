"""Crude minutes model: start / sub / 60+ from status, news, last-season time, and within-team roles."""
from __future__ import annotations

from collections import defaultdict

from engine.models import Player


def availability(player: Player, gw_offset: int) -> float:
    """0-1 multiplier for whether the player is available in this horizon slot."""
    if not player.can_select or player.status in {"u", "n"}:
        return 0.0
    if player.status == "s":
        return 0.0 if gw_offset == 0 else 0.85
    if player.status == "i":
        chance = player.chance_next if gw_offset == 0 else player.chance_this
        if gw_offset == 0:
            return (chance or 0) / 100.0
        if chance is not None and chance == 0:
            return min(0.5, 0.07 * gw_offset)
        return min(0.7, 0.15 + 0.12 * gw_offset)
    if player.status == "d":
        chance = player.chance_next if gw_offset == 0 else player.chance_this
        ch = (chance if chance is not None else 50) / 100.0
        if gw_offset == 0:
            return ch
        return min(1.0, 0.7 + 0.3 * ch)
    return 1.0


def _role_score(player: Player) -> tuple:
    ep = player.ep_next if player.ep_next is not None else -1.0
    return (availability(player, 0), ep, player.selected_by, player.minutes, player.now_cost)


def build_role_start(players: list[Player]) -> dict[int, float]:
    """Within each club, only one GK is treated as the starter.

    Last-season minutes alone would make every backup who started elsewhere
    look like a locked #1.
    """
    groups: dict[tuple[int, str], list[Player]] = defaultdict(list)
    for p in players:
        groups[(p.team_id, p.position)].append(p)

    out: dict[int, float] = {}
    for (team_id, pos), group in groups.items():
        ranked = sorted(group, key=_role_score, reverse=True)
        if pos == "GKP":
            starter = ranked[0]
            for i, p in enumerate(ranked):
                if i == 0 and availability(p, 0) > 0:
                    out[p.id] = 0.90 if (p.minutes >= 900 or p.starts >= 10 or (p.ep_next or 0) >= 2.0) else 0.75
                elif p.now_cost <= 45:
                    out[p.id] = 0.04
                else:
                    out[p.id] = 0.08
            # If FPL itself gives the 'starter' a tiny ep_next, fall back to minutes.
            if (starter.ep_next or 0) < 1.2 and starter.minutes < 900:
                by_mins = sorted(group, key=lambda p: (availability(p, 0), p.minutes, p.now_cost), reverse=True)
                out[by_mins[0].id] = 0.88
                for p in by_mins[1:]:
                    out[p.id] = 0.04 if p.now_cost <= 45 else 0.08
        else:
            for p in group:
                out[p.id] = _outfield_start(p)
    return out


def _outfield_start(player: Player) -> float:
    mins = player.minutes
    starts = player.starts
    cost = player.now_cost
    if mins >= 2700 or starts >= 32:
        p = 0.90
    elif mins >= 2000 or starts >= 24:
        p = 0.82
    elif mins >= 1400 or starts >= 16:
        p = 0.68
    elif mins >= 800 or starts >= 8:
        p = 0.48
    elif mins >= 300 or starts >= 3:
        p = 0.28
    elif cost >= 70:
        p = 0.72
    elif cost >= 55:
        p = 0.45
    elif cost <= 45:
        p = 0.10
    else:
        p = 0.18
    if player.position == "DEF" and cost <= 45:
        p = min(p, 0.22)
    if player.ep_next is not None and player.ep_next <= 0.4 and player.status == "a":
        p = min(p, 0.12)
    return p


def minutes_probs(
    player: Player,
    gw_offset: int,
    role_start: dict[int, float] | None = None,
) -> tuple[float, float, float]:
    """Return (p_start, p_sub, p_60)."""
    avail = availability(player, gw_offset)
    if avail <= 0:
        return 0.0, 0.0, 0.0

    base = role_start[player.id] if role_start is not None else _outfield_start(player)
    p_start = min(0.97, base * avail)
    leftover = max(0.0, 1.0 - p_start)
    if player.position == "GKP":
        p_sub = leftover * (0.04 if player.now_cost <= 45 else 0.08)
    elif player.minutes >= 1500:
        p_sub = leftover * 0.18
    elif player.now_cost >= 55:
        p_sub = leftover * 0.28
    else:
        p_sub = leftover * 0.22
    p_sub = min(leftover, p_sub)
    p_60 = p_start * 0.93 + p_sub * 0.08
    return p_start, p_sub, min(0.97, p_60)
