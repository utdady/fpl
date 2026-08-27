"""E019 V2C role-transition minutes (on top of frozen v2am_s).

minutes_version=v2c:
  1. Start from build_role_start_struct (V2A-M knobs unchanged).
  2. For club-transition *outfield* players only, demote by competition depth.
  3. Hot recent4 >= 270 skips demotion. Soft max 0.85 still applies.
  4. GK path unchanged.
"""
from __future__ import annotations

from collections import defaultdict

from engine.harness import (
    PREV_SEASON,
    _i,
    _id_code_map,
    _read_csv,
    ensure_vaastav,
    season_dir,
)
from engine.minutes_struct import (
    COLD_RECENT_MIN,
    HOT_RECENT_MIN,
    MAX_BASE,
    RECENT_WINDOW,
    build_role_start_struct,
)
from engine.models import Player

# Pinned E019 constants (reuse existing ladder / B5 evidence thresholds).
COMP_PRIOR_MIN = 1800
COMP_SEASON_FALLBACK = 900
CAP_NCOMP_GE2 = 0.48
CAP_NCOMP_EQ1 = 0.68


def _norm_team(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


def interseason_transition_ids(season: str) -> set[int]:
    """Current-season element ids whose code changed FPL team vs previous season.

    Same rule as obs.new_club_ids (code missing from prev OR team id differs).
    """
    prev = PREV_SEASON.get(season)
    if not prev:
        return set()
    ensure_vaastav((season, prev))
    old_team: dict[int, int] = {}
    for row in _read_csv(season_dir(prev) / "players_raw.csv"):
        code = _i(row.get("code"))
        if code:
            old_team[code] = _i(row.get("team"))
    out: set[int] = set()
    for row in _read_csv(season_dir(season) / "players_raw.csv"):
        eid = _i(row.get("id"))
        code = _i(row.get("code"))
        team = _i(row.get("team"))
        if not eid or not code:
            continue
        if code not in old_team or old_team[code] != team:
            out.add(eid)
    return out


def intraseason_transition_ids(season: str, as_of_gw: int) -> set[int]:
    """Element ids whose Vaastav team name changed within the season as-of-T.

    Compares team at first GW with minutes to team at latest completed GW < as_of_gw.
    """
    if as_of_gw <= 2:
        return set()
    ensure_vaastav((season,))
    merged = season_dir(season) / "gws" / "merged_gw.csv"
    if not merged.exists():
        return set()
    first_team: dict[int, str] = {}
    first_gw: dict[int, int] = {}
    last_team: dict[int, str] = {}
    last_gw: dict[int, int] = {}
    for row in _read_csv(merged):
        gw = _i(row.get("GW") or row.get("round"), 0)
        if gw < 1 or gw >= as_of_gw:
            continue
        eid = _i(row.get("element"), 0)
        if not eid:
            continue
        team = _norm_team(row.get("team") or "")
        if not team:
            continue
        mins = _i(row.get("minutes"))
        if mins > 0:
            if eid not in first_gw or gw < first_gw[eid]:
                first_gw[eid] = gw
                first_team[eid] = team
        if eid not in last_gw or gw > last_gw[eid]:
            last_gw[eid] = gw
            last_team[eid] = team
    out: set[int] = set()
    for eid, ft in first_team.items():
        lt = last_team.get(eid)
        if lt and lt != ft:
            out.add(eid)
    return out


def club_transition_ids(season: str, as_of_gw: int) -> set[int]:
    return interseason_transition_ids(season) | intraseason_transition_ids(season, as_of_gw)


def prior_minutes_at_club_by_code(prev_season: str) -> dict[tuple[int, str], int]:
    """(player code, normalized club name) -> minutes in prev_season."""
    ensure_vaastav((prev_season,))
    id_code = _id_code_map(prev_season)
    merged = season_dir(prev_season) / "gws" / "merged_gw.csv"
    if not merged.exists():
        return {}
    acc: dict[tuple[int, str], int] = defaultdict(int)
    for row in _read_csv(merged):
        eid = _i(row.get("element"), 0)
        code = id_code.get(eid)
        if not code:
            continue
        team = _norm_team(row.get("team") or "")
        if not team:
            continue
        mins = _i(row.get("minutes"))
        if mins > 0:
            acc[(code, team)] += mins
    return dict(acc)


def _club_has_prior_pool(prior_mins: dict[tuple[int, str], int], team_name: str) -> bool:
    key = _norm_team(team_name)
    return any(mins > 0 for (code, t), mins in prior_mins.items() if t == key)


def competition_count(
    player: Player,
    group: list[Player],
    team_name: str,
    id_code: dict[int, int],
    prior_mins: dict[tuple[int, str], int],
) -> int:
    """n_comp among other teammates at same position (E019 pinned rule)."""
    use_season = not _club_has_prior_pool(prior_mins, team_name)
    tnorm = _norm_team(team_name)
    n = 0
    for other in group:
        if other.id == player.id:
            continue
        if use_season:
            if other.minutes >= COMP_SEASON_FALLBACK:
                n += 1
        else:
            code = id_code.get(other.id)
            if code and prior_mins.get((code, tnorm), 0) >= COMP_PRIOR_MIN:
                n += 1
    return n


def build_role_start_v2c(
    players: list[Player],
    *,
    season: str,
    as_of_gw: int,
    recent_minutes: dict[int, int] | None = None,
    apply_recent: bool = False,
    team_names: dict[int, str] | None = None,
    demotion_skip_recent: int = HOT_RECENT_MIN,
) -> dict[int, float]:
    """V2A-M base + competition demotion for club-transition outfield only.

    demotion_skip_recent: skip competition demotion when recent4 >= this
    (E019 default HOT_RECENT_MIN=270; E020 v2c_e uses COLD_RECENT_MIN=90).
    """
    recent_minutes = recent_minutes or {}
    base = build_role_start_struct(
        players, recent_minutes=recent_minutes, apply_recent=apply_recent
    )
    transition = club_transition_ids(season, as_of_gw)
    if not transition:
        return base

    prev = PREV_SEASON.get(season)
    prior_mins: dict[tuple[int, str], int] = {}
    if prev:
        prior_mins = prior_minutes_at_club_by_code(prev)
    id_code = _id_code_map(season)
    team_names = team_names or {}

    groups: dict[tuple[int, str], list[Player]] = defaultdict(list)
    for p in players:
        groups[(p.team_id, p.position)].append(p)

    out = dict(base)
    for (team_id, pos), group in groups.items():
        if pos == "GKP":
            continue  # E019/E020: GK path unchanged
        name = team_names.get(team_id, "")
        for p in group:
            if p.id not in transition:
                continue
            # Form skip: evidenced non-cold (E020) or hot (E019) role — no demotion.
            if apply_recent and recent_minutes.get(p.id, 0) >= demotion_skip_recent:
                continue
            n_comp = competition_count(p, group, name, id_code, prior_mins)
            p0 = out[p.id]
            if n_comp >= 2:
                out[p.id] = min(p0, CAP_NCOMP_GE2)
            elif n_comp == 1:
                out[p.id] = min(p0, CAP_NCOMP_EQ1)
            # n_comp == 0: unchanged
            out[p.id] = min(MAX_BASE, out[p.id])
    return out


def build_role_start_v2c_e(
    players: list[Player],
    *,
    season: str,
    as_of_gw: int,
    recent_minutes: dict[int, int] | None = None,
    apply_recent: bool = False,
    team_names: dict[int, str] | None = None,
) -> dict[int, float]:
    """E020: same demotion rungs as v2c; skip demotion if recent4 >= 90 (cold gate)."""
    return build_role_start_v2c(
        players,
        season=season,
        as_of_gw=as_of_gw,
        recent_minutes=recent_minutes,
        apply_recent=apply_recent,
        team_names=team_names,
        demotion_skip_recent=COLD_RECENT_MIN,
    )
