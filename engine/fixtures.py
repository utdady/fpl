"""Match-level expected goals from FPL overall team strength. Attack/defence splits are 0 pre-season."""
from __future__ import annotations

from collections.abc import Callable, Iterable

from engine.models import Fixture, Snapshot, Team

LEAGUE_AVG = 1.35
HOME_ADV = 1.10
AWAY_ADV = 0.88

# strength_overall_* is a 2-5 scale at season start. Keep it coarse, but
# don't compress elite attacks into 'slightly above average'.
ATK = {2: 1.05, 3: 1.32, 4: 1.95, 5: 2.30}
CONCEDE = {2: 1.70, 3: 1.38, 4: 1.05, 5: 0.78}

# E048-A / E049-A frozen endpoints (LAB_LOG) — modern overall → [2,5] axis.
STR_LO = 1000
STR_HI = 1350

ATK_KNOTS: tuple[tuple[float, float], ...] = (
    (2.0, ATK[2]),
    (3.0, ATK[3]),
    (4.0, ATK[4]),
    (5.0, ATK[5]),
)
CONCEDE_KNOTS: tuple[tuple[float, float], ...] = (
    (2.0, CONCEDE[2]),
    (3.0, CONCEDE[3]),
    (4.0, CONCEDE[4]),
    (5.0, CONCEDE[5]),
)


def _str(val: int | None) -> int:
    """Production / fixtures=v1: modern ~1000+ overall clamps to bucket 5."""
    if val is None or val <= 0:
        return 3
    return int(max(2, min(5, val)))


def _str_sfix(val: int | None) -> int:
    """E048-A fixtures=v1_sfix: legacy 2..5 identity; else linear STR_LO..STR_HI → 2..5."""
    if val is None or val <= 0:
        return 3
    iv = int(val)
    if 2 <= iv <= 5:
        return iv
    x = max(STR_LO, min(STR_HI, iv))
    t = (x - STR_LO) / (STR_HI - STR_LO)
    b = 2 + int(round(3 * t))
    return max(2, min(5, b))


def raw_to_u(val: int | None) -> float:
    """E049-A: map overall strength onto continuous designed axis [2,5]."""
    if val is None or val <= 0:
        return 3.0
    iv = int(val)
    if 2 <= iv <= 5:
        return float(iv)
    x = max(STR_LO, min(STR_HI, iv))
    t = (x - STR_LO) / (STR_HI - STR_LO)
    return 2.0 + 3.0 * t


def pw_lerp(u: float, knots: tuple[tuple[float, float], ...]) -> float:
    """Piecewise-linear through knots; u clipped to [first, last] knot u."""
    u0_min, _ = knots[0]
    u_max, y_max = knots[-1]
    u = max(u0_min, min(u_max, float(u)))
    for (u0, y0), (u1, y1) in zip(knots, knots[1:]):
        if u <= u1 + 1e-15:
            if u1 == u0:
                return y0
            w = (u - u0) / (u1 - u0)
            return y0 + w * (y1 - y0)
    return y_max


def atk_pw(val: int | None) -> float:
    return pw_lerp(raw_to_u(val), ATK_KNOTS)


def concede_pw(val: int | None) -> float:
    return pw_lerp(raw_to_u(val), CONCEDE_KNOTS)


def expected_goals(
    home: Team,
    away: Team,
    *,
    bucket_fn: Callable[[int | None], int] = _str,
) -> tuple[float, float]:
    """Return (E[home_goals], E[away_goals]) via discrete ATK/CONCEDE buckets."""
    hs = bucket_fn(home.strength_home)
    aws = bucket_fn(away.strength_away)
    e_home = ATK[hs] * (CONCEDE[aws] / LEAGUE_AVG) * HOME_ADV
    e_away = ATK[aws] * (CONCEDE[hs] / LEAGUE_AVG) * AWAY_ADV
    return _clamp(e_home), _clamp(e_away)


def expected_goals_pw(home: Team, away: Team) -> tuple[float, float]:
    """E049-A: same xG algebra with continuous piecewise ATK/CONCEDE."""
    hs = atk_pw(home.strength_home)
    aws_atk = atk_pw(away.strength_away)
    hs_c = concede_pw(home.strength_home)
    aws_c = concede_pw(away.strength_away)
    e_home = hs * (aws_c / LEAGUE_AVG) * HOME_ADV
    e_away = aws_atk * (hs_c / LEAGUE_AVG) * AWAY_ADV
    return _clamp(e_home), _clamp(e_away)


def intensity_means(teams: Iterable[Team]) -> tuple[float, float]:
    """E052-A: league means of positive overall strengths (overlay / snapshot)."""
    hs = [float(t.strength_home) for t in teams if t.strength_home and t.strength_home > 0]
    aws = [float(t.strength_away) for t in teams if t.strength_away and t.strength_away > 0]
    m_h = sum(hs) / len(hs) if hs else 0.0
    m_a = sum(aws) / len(aws) if aws else 0.0
    return m_h, m_a


def _intensity(val: int | None, mean: float) -> float:
    if val is None or val <= 0 or mean <= 0:
        return 1.0
    return float(val) / mean


def expected_goals_sxg(
    home: Team,
    away: Team,
    *,
    m_h: float,
    m_a: float,
) -> tuple[float, float]:
    """E052-A: continuous relative xG; no ATK/CONCEDE / _str / STR_LO/HI."""
    ih = _intensity(home.strength_home, m_h)
    ia = _intensity(away.strength_away, m_a)
    e_home = LEAGUE_AVG * (ih / ia) * HOME_ADV
    e_away = LEAGUE_AVG * (ia / ih) * AWAY_ADV
    return _clamp(e_home), _clamp(e_away)


def adxg_intensity_means(overlay: dict) -> tuple[float, float, float, float]:
    """E053-A: league means of positive attack/defence fields."""
    atk_h = [float(v.attack_home) for v in overlay.values() if v.attack_home and v.attack_home > 0]
    atk_a = [float(v.attack_away) for v in overlay.values() if v.attack_away and v.attack_away > 0]
    def_h = [float(v.defence_home) for v in overlay.values() if v.defence_home and v.defence_home > 0]
    def_a = [float(v.defence_away) for v in overlay.values() if v.defence_away and v.defence_away > 0]
    return (
        sum(atk_h) / len(atk_h) if atk_h else 0.0,
        sum(atk_a) / len(atk_a) if atk_a else 0.0,
        sum(def_h) / len(def_h) if def_h else 0.0,
        sum(def_a) / len(def_a) if def_a else 0.0,
    )


def expected_goals_adxg(
    home_id: int,
    away_id: int,
    overlay: dict | None,
    *,
    means: tuple[float, float, float, float] | None = None,
) -> tuple[float, float]:
    """E053-A: continuous relative ATK/DEF xG; no hand ATK/CONCEDE / overall."""
    ov = overlay or {}
    m_atk_h, m_atk_a, m_def_h, m_def_a = means if means is not None else adxg_intensity_means(ov)
    h = ov.get(home_id)
    a = ov.get(away_id)
    i_atk_h = _intensity(h.attack_home if h else None, m_atk_h)
    i_atk_a = _intensity(a.attack_away if a else None, m_atk_a)
    i_def_h = _intensity(h.defence_home if h else None, m_def_h)
    i_def_a = _intensity(a.defence_away if a else None, m_def_a)
    e_home = LEAGUE_AVG * (i_atk_h / i_def_a) * HOME_ADV
    e_away = LEAGUE_AVG * (i_atk_a / i_def_h) * AWAY_ADV
    return _clamp(e_home), _clamp(e_away)


def _clamp(x: float) -> float:
    return max(0.45, min(3.4, x))


def player_match_context(
    snapshot: Snapshot,
    team_id: int,
    fx: Fixture,
    fixtures_version: str = "v1",
    fixture_strengths: dict | None = None,
    adxg_strengths: dict | None = None,
) -> dict:
    home = snapshot.team(fx.team_h)
    away = snapshot.team(fx.team_a)
    if fixtures_version == "v2d":
        from engine.fixtures_v2d import expected_goals_v2d

        if fixture_strengths is None:
            raise ValueError("fixtures_version=v2d requires fixture_strengths")
        e_home, e_away = expected_goals_v2d(home, away, fixture_strengths)
    elif fixtures_version == "v1_sfix":
        e_home, e_away = expected_goals(home, away, bucket_fn=_str_sfix)
    elif fixtures_version == "v1_pw":
        e_home, e_away = expected_goals_pw(home, away)
    elif fixtures_version == "v1_sxg":
        m_h, m_a = intensity_means(snapshot.teams.values())
        e_home, e_away = expected_goals_sxg(home, away, m_h=m_h, m_a=m_a)
    elif fixtures_version == "v1_adxg":
        means = adxg_intensity_means(adxg_strengths) if adxg_strengths else (0.0, 0.0, 0.0, 0.0)
        e_home, e_away = expected_goals_adxg(
            fx.team_h, fx.team_a, adxg_strengths, means=means
        )
    else:
        # v1 and v1_fpls (hydrate happens upstream; still uses production _str)
        e_home, e_away = expected_goals(home, away, bucket_fn=_str)
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
