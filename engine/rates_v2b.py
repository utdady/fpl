"""E016 V2B multi-season xG/xA priors (club-stint split).

rates_version=v2b changes only the prior inside rates_for for xg90/xa90.
ATK/CONCEDE, dc/saves/bonus/cards, and minutes stay untouched.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from engine.harness import (
    PREV_SEASON,
    _id_code_map,
    _i,
    _f,
    _read_csv,
    ensure_vaastav,
    season_dir,
)
from engine.models import Player, Snapshot
from engine.project import blend, cost_prior_xa90, cost_prior_xg90

# Minimum historical minutes at the *current* club before using multi-season prior.
MIN_CLUB_MINUTES = 270


def _norm_team(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


def prior_season_chain(season: str) -> list[str]:
    """Full seasons strictly before `season`, newest first."""
    out: list[str] = []
    cur = PREV_SEASON.get(season)
    seen: set[str] = set()
    while cur and cur not in seen:
        seen.add(cur)
        out.append(cur)
        cur = PREV_SEASON.get(cur)
    return out


@dataclass
class ClubRatePool:
    minutes: int = 0
    xg: float = 0.0
    xa: float = 0.0

    def xg90(self) -> float:
        if self.minutes <= 0:
            return 0.0
        return self.xg / (self.minutes / 90.0)

    def xa90(self) -> float:
        if self.minutes <= 0:
            return 0.0
        return self.xa / (self.minutes / 90.0)


def aggregate_code_club_rates(seasons: list[str] | tuple[str, ...]) -> dict[tuple[int, str], ClubRatePool]:
    """Pool xG/xA/minutes by (player code, club name). Never mixes clubs."""
    return _aggregate_code_club_rates(tuple(seasons))


def _aggregate_code_club_rates(seasons: tuple[str, ...]) -> dict[tuple[int, str], ClubRatePool]:
    ensure_vaastav(seasons)
    pools: dict[tuple[int, str], ClubRatePool] = defaultdict(ClubRatePool)
    for season in seasons:
        sdir = season_dir(season)
        merged = sdir / "gws" / "merged_gw.csv"
        if not merged.exists():
            continue
        id_code = _id_code_map(season)
        rows = _read_csv(merged)
        has_xg = bool(rows) and "expected_goals" in rows[0]
        for row in rows:
            eid = _i(row.get("element"), 0)
            code = id_code.get(eid)
            if not code:
                continue
            team = _norm_team(row.get("team") or "")
            if not team:
                continue
            mins = _i(row.get("minutes"))
            if mins <= 0:
                continue
            key = (code, team)
            p = pools[key]
            p.minutes += mins
            goals = _i(row.get("goals_scored"))
            assists = _i(row.get("assists"))
            if has_xg:
                p.xg += _f(row.get("expected_goals"))
                p.xa += _f(row.get("expected_assists"))
            else:
                p.xg += float(goals)
                p.xa += float(assists)
    return dict(pools)


# Cache full prior pools per season-chain (rebuilt once per process).
_POOL_CACHE: dict[tuple[str, ...], dict[tuple[int, str], ClubRatePool]] = {}


def cached_pools_for_season(season: str) -> dict[tuple[int, str], ClubRatePool]:
    chain = tuple(prior_season_chain(season))
    if chain not in _POOL_CACHE:
        _POOL_CACHE[chain] = _aggregate_code_club_rates(chain) if chain else {}
    return _POOL_CACHE[chain]


def lookup_club_prior(
    pools: dict[tuple[int, str], ClubRatePool],
    code: int | None,
    team_name: str,
) -> tuple[float, float] | None:
    if not code:
        return None
    pool = pools.get((code, _norm_team(team_name)))
    if pool is None or pool.minutes < MIN_CLUB_MINUTES:
        return None
    return pool.xg90(), pool.xa90()


def build_rates_priors_for_snapshot(season: str, snapshot: Snapshot) -> dict[int, tuple[float, float]]:
    """player_id -> (prior_xg90, prior_xa90) for current club only.

    Uses complete prior seasons only (no current-season leakage into the prior).
    """
    pools = cached_pools_for_season(season)
    if not pools:
        return {}
    id_code = _id_code_map(season)
    team_name = {tid: t.name for tid, t in snapshot.teams.items()}
    out: dict[int, tuple[float, float]] = {}
    for player in snapshot.players:
        code = id_code.get(player.id)
        name = team_name.get(player.team_id, "")
        prior = lookup_club_prior(pools, code, name)
        if prior is not None:
            out[player.id] = prior
    return out


def rates_for_v2b(
    player: Player,
    prior_xg90: float | None,
    prior_xa90: float | None,
) -> dict[str, float]:
    """Same as rates_v1 except xG/xA prior is multi-season club prior when available."""
    px = prior_xg90 if prior_xg90 is not None else cost_prior_xg90(player.position, player.now_cost)
    pa = prior_xa90 if prior_xa90 is not None else cost_prior_xa90(player.position, player.now_cost)
    xg = blend(player.xg90, px, player.minutes)
    xa = blend(player.xa90, pa, player.minutes)
    if player.minutes < 450 and player.pen_order == 1:
        xg += 0.14
    if player.minutes < 450 and player.corners_order == 1:
        xa += 0.05

    if player.dc90 > 0.5:
        dc90 = player.dc90
    else:
        dc90 = {"GKP": 0.0, "DEF": 7.2, "MID": 8.0, "FWD": 5.0}[player.position]
        dc90 = blend(player.dc90, dc90, player.minutes, n_full=900)

    saves90 = player.saves90 if player.position == "GKP" else 0.0
    if player.position == "GKP" and saves90 < 0.5:
        saves90 = 3.0 if player.minutes >= 900 else 2.6

    games = max(player.games_hint, 1)
    y90 = (player.yellow / games) * (90 / 90)
    if player.minutes >= 450:
        y90 = player.yellow / max(player.minutes / 90.0, 1.0)
    else:
        y90 = {"GKP": 0.05, "DEF": 0.14, "MID": 0.12, "FWD": 0.10}[player.position]

    bonus90 = 0.0
    if player.minutes >= 450:
        bonus90 = player.bonus / max(player.minutes / 90.0, 1.0)
    return {
        "xg90": max(0.0, xg),
        "xa90": max(0.0, xa),
        "dc90": max(0.0, dc90),
        "saves90": max(0.0, saves90),
        "y90": max(0.0, min(0.45, y90)),
        "bonus90": max(0.0, min(1.2, bonus90)),
    }
