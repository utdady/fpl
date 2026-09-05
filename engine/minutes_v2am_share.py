"""E042-A: club–position minutes share on top of frozen v2am_s.

minutes_version=v2am_share (LAB_LOG E042-A):
  1. b0 = build_role_start_struct (cold/hot / MAX_BASE unchanged)
  2. s_i = current-club minutes share within (team, position) over W=4
  3. Identity → b1=b0; else b1=(1-λ)b0 + λ·MAX_BASE·s, clipped
  4. availability() unchanged (applied later in minutes_probs)
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache

from engine.harness import _i, _read_csv, season_dir
from engine.minutes import availability
from engine.minutes_struct import MAX_BASE, build_role_start_struct
from engine.models import Player

SHARE_WINDOW = 4  # W frozen E042-A
LAMBDA = 0.35
B1_FLOOR = 0.04


@dataclass(frozen=True)
class ShareDiag:
    player_id: int
    web_name: str
    team_id: int
    position: str
    b0: float
    share: float
    club_minutes: int
    group_minutes: int
    n_gws_on_club: int
    group_size: int
    eligible: bool
    identity_reason: str
    b1: float
    availability0: float


def _norm_team(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


@lru_cache(maxsize=8)
def _merged_gw_rows(season: str) -> tuple[tuple[int, int, str, int], ...]:
    """Cached (gw, element, team_norm, minutes) rows for a season."""
    merged = season_dir(season) / "gws" / "merged_gw.csv"
    if not merged.exists():
        return ()
    out: list[tuple[int, int, str, int]] = []
    for row in _read_csv(merged):
        gw = _i(row.get("GW") or row.get("round"), 0)
        eid = _i(row.get("element"), 0)
        if not gw or not eid:
            continue
        out.append((gw, eid, _norm_team(row.get("team") or ""), _i(row.get("minutes"))))
    return tuple(out)


def club_window_minutes(
    season: str,
    as_of_gw: int,
    players: list[Player],
    team_names: dict[int, str],
    *,
    window: int = SHARE_WINDOW,
) -> tuple[dict[int, int], dict[int, int]]:
    """Per-element minutes and GW-count on current club in (T-W)..(T-1).

    Returns (club_minutes, n_gws_on_club). DGW rows are summed into the GW total.
    """
    club_minutes = {p.id: 0 for p in players}
    n_gws = {p.id: 0 for p in players}
    if as_of_gw <= 1:
        return club_minutes, n_gws

    current_team_norm = {p.id: _norm_team(team_names[p.team_id]) for p in players}
    from_gw = max(1, as_of_gw - window)
    through_gw = as_of_gw - 1
    by_eg: dict[tuple[int, int], int] = defaultdict(int)
    for gw, eid, tnorm, mins in _merged_gw_rows(season):
        if gw < from_gw or gw > through_gw:
            continue
        if eid not in current_team_norm:
            continue
        if tnorm != current_team_norm[eid]:
            continue
        by_eg[(eid, gw)] += mins

    for (eid, _gw), mins in by_eg.items():
        club_minutes[eid] = club_minutes.get(eid, 0) + mins
        n_gws[eid] = n_gws.get(eid, 0) + 1
    return club_minutes, n_gws


def apply_share_blend(
    players: list[Player],
    b0: dict[int, float],
    club_minutes: dict[int, int],
    n_gws_on_club: dict[int, int],
    *,
    lam: float = LAMBDA,
    as_of_gw: int = 2,
) -> tuple[dict[int, float], list[ShareDiag]]:
    """Return b1 role_start and per-player diagnostics."""
    groups: dict[tuple[int, str], list[Player]] = defaultdict(list)
    for p in players:
        groups[(p.team_id, p.position)].append(p)

    b1: dict[int, float] = {}
    diags: list[ShareDiag] = []

    for (team_id, pos), group in groups.items():
        group_size = len(group)
        group_mins = sum(club_minutes.get(p.id, 0) for p in group)

        group_identity = ""
        if as_of_gw <= 1:
            group_identity = "gw1"
        elif group_size < 2:
            group_identity = "thin_group"
        elif group_mins <= 0:
            group_identity = "zero_denom"

        for p in group:
            base = float(b0[p.id])
            cm = int(club_minutes.get(p.id, 0))
            ng = int(n_gws_on_club.get(p.id, 0))
            avail0 = float(availability(p, 0))
            reason = group_identity
            share = 0.0

            if reason:
                pass
            elif ng <= 0:
                reason = "no_club_gws"
            else:
                share = cm / group_mins  # group_mins > 0 here
                blended = (1.0 - lam) * base + lam * MAX_BASE * share
                b1[p.id] = min(MAX_BASE, max(B1_FLOOR, blended))
                diags.append(
                    ShareDiag(
                        player_id=p.id,
                        web_name=p.web_name,
                        team_id=team_id,
                        position=pos,
                        b0=base,
                        share=share,
                        club_minutes=cm,
                        group_minutes=group_mins,
                        n_gws_on_club=ng,
                        group_size=group_size,
                        eligible=True,
                        identity_reason="",
                        b1=b1[p.id],
                        availability0=avail0,
                    )
                )
                continue

            b1[p.id] = base
            diags.append(
                ShareDiag(
                    player_id=p.id,
                    web_name=p.web_name,
                    team_id=team_id,
                    position=pos,
                    b0=base,
                    share=share,
                    club_minutes=cm,
                    group_minutes=group_mins,
                    n_gws_on_club=ng,
                    group_size=group_size,
                    eligible=False,
                    identity_reason=reason,
                    b1=base,
                    availability0=avail0,
                )
            )

    return b1, diags


def build_role_start_v2am_share(
    players: list[Player],
    *,
    season: str | None,
    as_of_gw: int,
    recent_minutes: dict[int, int] | None = None,
    apply_recent: bool = False,
    team_names: dict[int, str] | None = None,
) -> tuple[dict[int, float], list[ShareDiag]]:
    """v2am_s base then E042-A share blend. Live without season → identity."""
    b0 = build_role_start_struct(
        players, recent_minutes=recent_minutes, apply_recent=apply_recent
    )
    if not season or not team_names or as_of_gw <= 1:
        diags = [
            ShareDiag(
                player_id=p.id,
                web_name=p.web_name,
                team_id=p.team_id,
                position=p.position,
                b0=float(b0[p.id]),
                share=0.0,
                club_minutes=0,
                group_minutes=0,
                n_gws_on_club=0,
                group_size=1,
                eligible=False,
                identity_reason="live_or_gw1" if as_of_gw <= 1 else "no_season",
                b1=float(b0[p.id]),
                availability0=float(availability(p, 0)),
            )
            for p in players
        ]
        return b0, diags

    club_m, n_gws = club_window_minutes(
        season, as_of_gw, players, team_names, window=SHARE_WINDOW
    )
    return apply_share_blend(
        players, b0, club_m, n_gws, lam=LAMBDA, as_of_gw=as_of_gw
    )
