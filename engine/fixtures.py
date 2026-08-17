"""Match-level expected goals from FPL overall team strength. Attack/defence splits are 0 pre-season."""
from __future__ import annotations

from engine.models import Fixture, Snapshot, Team

LEAGUE_AVG = 1.35

# strength_overall_* is a 2-5 scale at season start. Keep it coarse, but
# don't compress elite attacks into 'slightly above average'.
ATK = {2: 1.05, 3: 1.32, 4: 1.95, 5: 2.30}
CONCEDE = {2: 1.70, 3: 1.38, 4: 1.05, 5: 0.78}


def _str(val: int | None) -> int:
    if val is None or val <= 0:
        return 3
    return int(max(2, min(5, val)))


def expected_goals(home: Team, away: Team) -> tuple[float, float]:
    """Return (E[home_goals], E[away_goals])."""
    hs = _str(home.strength_home)
    aws = _str(away.strength_away)
    e_home = ATK[hs] * (CONCEDE[aws] / LEAGUE_AVG) * 1.10
    e_away = ATK[aws] * (CONCEDE[hs] / LEAGUE_AVG) * 0.88
    return _clamp(e_home), _clamp(e_away)


def _clamp(x: float) -> float:
    return max(0.45, min(3.4, x))


def player_match_context(snapshot: Snapshot, team_id: int, fx: Fixture) -> dict:
    home = snapshot.team(fx.team_h)
    away = snapshot.team(fx.team_a)
    e_home, e_away = expected_goals(home, away)
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
