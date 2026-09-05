"""E043-A: lagged short-turnaround load on top of frozen v2am_s.

minutes_version=v2am_sched (LAB_LOG E043-A):
  d_prev_gap = (prior_utc - prior2_utc).total_seconds()/86400
  prior, prior2 = last two PL kickoffs with event < T
  trigger: d_prev_gap < 5.0 → b1 = min(b0, 0.60) for eligible outfield incumbents
  No target-GW KO / forward density / non-PL.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

from engine.harness import _i, _i_opt, _read_csv, season_dir
from engine.minutes import availability
from engine.minutes_struct import build_role_start_struct
from engine.models import Player

GAP_TRIGGER_DAYS = 5.0
SHORT_TURN_CAP = 0.60
INCUMBENT_MINUTES = 800


@dataclass(frozen=True)
class SchedDiag:
    player_id: int
    web_name: str
    team_id: int
    position: str
    b0: float
    d_prev_gap: float | None
    trigger: bool
    eligible: bool
    identity_reason: str
    b1: float
    availability0: float


def _parse_ko(raw: str | None) -> datetime | None:
    if not raw or not str(raw).strip():
        return None
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))


@lru_cache(maxsize=8)
def _fixture_kickoffs(season: str) -> tuple[tuple[int, int, int, int, datetime], ...]:
    """(fixture_id, event, team_h, team_a, kickoff_utc) for parseable PL rows."""
    path = season_dir(season) / "fixtures.csv"
    if not path.exists():
        return ()
    out: list[tuple[int, int, int, int, datetime]] = []
    for row in _read_csv(path):
        ev = _i_opt(row.get("event"))
        if ev is None:
            continue
        try:
            ko = _parse_ko(row.get("kickoff_time"))
        except ValueError:
            continue
        if ko is None:
            continue
        out.append((_i(row.get("id")), ev, _i(row.get("team_h")), _i(row.get("team_a")), ko))
    return tuple(out)


def club_prev_gap_days(
    season: str,
    as_of_gw: int,
) -> tuple[dict[int, float | None], set[int], bool]:
    """Per-club d_prev_gap, set of clubs with event==T fixtures, league_bgw flag.

    d_prev_gap uses only kickoffs with event < as_of_gw.
    """
    rows = _fixture_kickoffs(season)
    clubs_in_t: set[int] = set()
    for _fid, ev, hid, aid, _ko in rows:
        if ev == as_of_gw:
            clubs_in_t.add(hid)
            clubs_in_t.add(aid)
    league_bgw = len(clubs_in_t) == 0

    by_club: dict[int, list[datetime]] = defaultdict(list)
    for _fid, ev, hid, aid, ko in rows:
        if ev >= as_of_gw:
            continue
        by_club[hid].append(ko)
        by_club[aid].append(ko)

    gaps: dict[int, float | None] = {}
    all_teams = set(by_club) | clubs_in_t
    for tid in all_teams:
        kos = sorted(by_club.get(tid, []))
        if len(kos) < 2:
            gaps[tid] = None
        else:
            prior, prior2 = kos[-1], kos[-2]
            gaps[tid] = (prior - prior2).total_seconds() / 86400.0
    return gaps, clubs_in_t, league_bgw


def apply_sched_blend(
    players: list[Player],
    b0: dict[int, float],
    gaps: dict[int, float | None],
    clubs_in_t: set[int],
    *,
    league_bgw: bool,
    as_of_gw: int,
) -> tuple[dict[int, float], list[SchedDiag]]:
    b1: dict[int, float] = {}
    diags: list[SchedDiag] = []

    for p in players:
        base = float(b0[p.id])
        avail0 = float(availability(p, 0))
        gap = gaps.get(p.team_id)
        reason = ""
        trigger = False
        eligible = False

        if league_bgw:
            reason = "league_bgw"
        elif as_of_gw <= 1:
            reason = "gw1"
        elif p.team_id not in clubs_in_t:
            reason = "club_blank"
        elif p.position == "GKP":
            reason = "gkp"
        elif p.minutes < INCUMBENT_MINUTES:
            reason = "not_incumbent"
        elif gap is None:
            reason = "insufficient_history"
        else:
            eligible = True
            trigger = gap < GAP_TRIGGER_DAYS
            if trigger:
                b1[p.id] = min(base, SHORT_TURN_CAP)
            else:
                b1[p.id] = base
            diags.append(
                SchedDiag(
                    player_id=p.id,
                    web_name=p.web_name,
                    team_id=p.team_id,
                    position=p.position,
                    b0=base,
                    d_prev_gap=gap,
                    trigger=trigger,
                    eligible=True,
                    identity_reason="",
                    b1=b1[p.id],
                    availability0=avail0,
                )
            )
            continue

        b1[p.id] = base
        diags.append(
            SchedDiag(
                player_id=p.id,
                web_name=p.web_name,
                team_id=p.team_id,
                position=p.position,
                b0=base,
                d_prev_gap=gap,
                trigger=False,
                eligible=False,
                identity_reason=reason,
                b1=base,
                availability0=avail0,
            )
        )

    return b1, diags


def build_role_start_v2am_sched(
    players: list[Player],
    *,
    season: str | None,
    as_of_gw: int,
    recent_minutes: dict[int, int] | None = None,
    apply_recent: bool = False,
) -> tuple[dict[int, float], list[SchedDiag]]:
    """v2am_s base then E043-A lagged short-turnaround. Live without season → identity."""
    b0 = build_role_start_struct(
        players, recent_minutes=recent_minutes, apply_recent=apply_recent
    )
    if not season:
        diags = [
            SchedDiag(
                player_id=p.id,
                web_name=p.web_name,
                team_id=p.team_id,
                position=p.position,
                b0=float(b0[p.id]),
                d_prev_gap=None,
                trigger=False,
                eligible=False,
                identity_reason="no_season",
                b1=float(b0[p.id]),
                availability0=float(availability(p, 0)),
            )
            for p in players
        ]
        return b0, diags

    gaps, clubs_in_t, league_bgw = club_prev_gap_days(season, as_of_gw)
    return apply_sched_blend(
        players,
        b0,
        gaps,
        clubs_in_t,
        league_bgw=league_bgw,
        as_of_gw=as_of_gw,
    )
