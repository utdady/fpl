"""V2A-M-v2 (E015): structural as-of-T start probabilities.

Pre-registered rules (fixed thresholds, not LOSO-tuned):
- Never assign base 0.90 from season totals alone (soft max 0.85).
- When as_of_gw > 4, use last-4-GW minutes (as-of-T only):
  - cold: season_minutes >= 800 and recent_4 < 90 -> cap base at 0.55
  - hot:  recent_4 >= 270 -> floor base at 0.72 (still <= 0.85)
- No new-club prior. No post-hoc bucket remap.
- GK within-club role logic kept; starter soft-capped at 0.85.
"""
from __future__ import annotations

from collections import defaultdict

from engine.minutes import availability, _outfield_start
from engine.models import Player

RECENT_WINDOW = 4
COLD_RECENT_MIN = 90
COLD_CAP = 0.55
HOT_RECENT_MIN = 270
HOT_FLOOR = 0.72
MAX_BASE = 0.85
COLD_SEASON_MIN = 800  # only demote established season totals that went cold


def _soft_cap_base(p: float) -> float:
    return min(MAX_BASE, p)


def _outfield_start_struct(player: Player, recent_minutes: int, apply_recent: bool) -> float:
    # Same ladder as V1, but top rung is 0.85 not 0.90.
    mins = player.minutes
    starts = player.starts
    cost = player.now_cost
    if mins >= 2700 or starts >= 32:
        p = MAX_BASE
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

    if apply_recent:
        if mins >= COLD_SEASON_MIN and recent_minutes < COLD_RECENT_MIN:
            p = min(p, COLD_CAP)
        elif recent_minutes >= HOT_RECENT_MIN:
            p = max(p, HOT_FLOOR)
    return _soft_cap_base(p)


def build_role_start_struct(
    players: list[Player],
    recent_minutes: dict[int, int] | None = None,
    apply_recent: bool = False,
) -> dict[int, float]:
    """Within-club GK role + structural outfield bases."""
    recent_minutes = recent_minutes or {}
    groups: dict[tuple[int, str], list[Player]] = defaultdict(list)
    for p in players:
        groups[(p.team_id, p.position)].append(p)

    out: dict[int, float] = {}
    for (_, pos), group in groups.items():
        ranked = sorted(
            group,
            key=lambda p: (availability(p, 0), p.ep_next if p.ep_next is not None else -1.0,
                           p.selected_by, p.minutes, p.now_cost),
            reverse=True,
        )
        if pos == "GKP":
            starter = ranked[0]
            for i, p in enumerate(ranked):
                if i == 0 and availability(p, 0) > 0:
                    raw = 0.85 if (p.minutes >= 900 or p.starts >= 10 or (p.ep_next or 0) >= 2.0) else 0.75
                    if apply_recent and p.minutes >= COLD_SEASON_MIN and recent_minutes.get(p.id, 0) < COLD_RECENT_MIN:
                        raw = min(raw, COLD_CAP)
                    out[p.id] = raw
                elif p.now_cost <= 45:
                    out[p.id] = 0.04
                else:
                    out[p.id] = 0.08
            if (starter.ep_next or 0) < 1.2 and starter.minutes < 900:
                by_mins = sorted(
                    group,
                    key=lambda p: (availability(p, 0), p.minutes, p.now_cost),
                    reverse=True,
                )
                out[by_mins[0].id] = 0.85
                for p in by_mins[1:]:
                    out[p.id] = 0.04 if p.now_cost <= 45 else 0.08
        else:
            for p in group:
                out[p.id] = _outfield_start_struct(
                    p, recent_minutes.get(p.id, 0), apply_recent=apply_recent
                )
    return out
