"""E021 V2D learned fixture strengths (prior-season match goals).

fixtures_version=v2d replaces hand ATK/CONCEDE tables with empirical
per-team attack / defensive-vulnerability rates from complete prior seasons.
Home/away multipliers 1.10 / 0.88 and LEAGUE_AVG / clamp stay frozen.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from engine.fixtures import LEAGUE_AVG, _clamp
from engine.harness import _i, _read_csv, ensure_vaastav, season_dir
from engine.models import Fixture, Snapshot, Team
from engine.rates_v2b import prior_season_chain

# Frozen from fixtures.py / E021 contract.
HOME_MULT = 1.10
AWAY_MULT = 0.88


def _norm_team(name: str) -> str:
    return " ".join((name or "").strip().lower().split())


@dataclass
class TeamStrength:
    attack: float  # mean goals scored per match
    defend: float  # mean goals conceded per match (vulnerability)


def _team_id_to_name(season: str) -> dict[int, str]:
    out: dict[int, str] = {}
    for row in _read_csv(season_dir(season) / "teams.csv"):
        tid = _i(row.get("id"))
        if tid:
            out[tid] = _norm_team(row.get("name") or "")
    return out


def aggregate_prior_strengths(seasons: list[str] | tuple[str, ...]) -> dict[str, TeamStrength]:
    """Normalized club name -> attack/defend rates from finished matches."""
    ensure_vaastav(tuple(seasons))
    gf: dict[str, float] = defaultdict(float)
    ga: dict[str, float] = defaultdict(float)
    n: dict[str, int] = defaultdict(int)

    for season in seasons:
        id_name = _team_id_to_name(season)
        path = season_dir(season) / "fixtures.csv"
        if not path.exists():
            continue
        for row in _read_csv(path):
            if str(row.get("finished") or "").lower() not in {"true", "1"}:
                continue
            hs = row.get("team_h_score")
            aws = row.get("team_a_score")
            if hs in (None, "") or aws in (None, ""):
                continue
            h_id = _i(row.get("team_h"))
            a_id = _i(row.get("team_a"))
            h_name = id_name.get(h_id, "")
            a_name = id_name.get(a_id, "")
            if not h_name or not a_name:
                continue
            h_goals = float(hs)
            a_goals = float(aws)
            gf[h_name] += h_goals
            ga[h_name] += a_goals
            n[h_name] += 1
            gf[a_name] += a_goals
            ga[a_name] += h_goals
            n[a_name] += 1

    out: dict[str, TeamStrength] = {}
    for name, games in n.items():
        if games <= 0:
            continue
        out[name] = TeamStrength(attack=gf[name] / games, defend=ga[name] / games)
    return out


# Cache by prior-season chain tuple.
_STRENGTH_CACHE: dict[tuple[str, ...], dict[str, TeamStrength]] = {}


def strengths_for_season(season: str) -> dict[str, TeamStrength]:
    """Strengths fitted on complete seasons strictly before `season`."""
    chain = tuple(prior_season_chain(season))
    if chain not in _STRENGTH_CACHE:
        _STRENGTH_CACHE[chain] = aggregate_prior_strengths(chain) if chain else {}
    return _STRENGTH_CACHE[chain]


def lookup_strength(
    strengths: dict[str, TeamStrength],
    team: Team,
) -> TeamStrength:
    """Promoted / unknown clubs → league-average attack & defend (= LEAGUE_AVG)."""
    name = _norm_team(team.name)
    s = strengths.get(name)
    if s is None:
        return TeamStrength(attack=LEAGUE_AVG, defend=LEAGUE_AVG)
    return s


def expected_goals_v2d(
    home: Team,
    away: Team,
    strengths: dict[str, TeamStrength],
) -> tuple[float, float]:
    """E[home], E[away] using learned rates; same multiplicative structure as v1."""
    h = lookup_strength(strengths, home)
    a = lookup_strength(strengths, away)
    e_home = h.attack * (a.defend / LEAGUE_AVG) * HOME_MULT
    e_away = a.attack * (h.defend / LEAGUE_AVG) * AWAY_MULT
    return _clamp(e_home), _clamp(e_away)


def player_match_context_v2d(
    snapshot: Snapshot,
    team_id: int,
    fx: Fixture,
    strengths: dict[str, TeamStrength],
) -> dict:
    home = snapshot.team(fx.team_h)
    away = snapshot.team(fx.team_a)
    e_home, e_away = expected_goals_v2d(home, away, strengths)
    is_home = team_id == fx.team_h
    team_xg = e_home if is_home else e_away
    opp_xg = e_away if is_home else e_home
    opp = away if is_home else home
    fdr = fx.fdr_home if is_home else fx.fdr_away
    return {
        "is_home": is_home,
        "team_xg": team_xg,
        "opp_xg": opp_xg,
        "opp": opp,
        "fdr": fdr,
        "attack_mult": team_xg / LEAGUE_AVG,
        "p_cs": pow(2.718281828459045, -opp_xg),
    }
