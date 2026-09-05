"""Event-rate expected points with a minutes mixture and simulated uncertainty."""
from __future__ import annotations

import math

import numpy as np

from engine.fixtures import LEAGUE_AVG, player_match_context
from engine.minutes import build_role_start, minutes_probs
from engine.minutes_v2am import recalibrate_minutes
from engine.minutes_struct import RECENT_WINDOW, build_role_start_struct
from engine.models import GWProjection, Player, PlayerProjection, Snapshot
from engine.scoring import GC_BUCKET, SAVES_BUCKET

N_SIMS = 2500
DECAY = 0.90
STRATEGIES = ("safe", "balanced", "aggressive")


def poisson_cdf(k: int, lam: float) -> float:
    if k < 0:
        return 0.0
    if lam <= 1e-12:
        return 1.0
    term = math.exp(-lam)
    s = term
    for i in range(1, k + 1):
        term *= lam / i
        s += term
        if s >= 1.0:
            return 1.0
    return s


def p_poisson_ge(k: int, lam: float) -> float:
    if k <= 0:
        return 1.0
    return max(0.0, 1.0 - poisson_cdf(k - 1, lam))


def cost_prior_xg90(pos: str, cost: int) -> float:
    c = cost / 10.0
    gap = max(0.0, c - 4.5)
    if pos == "FWD":
        return 0.08 + 0.055 * gap
    if pos == "MID":
        return 0.03 + 0.045 * gap
    if pos == "DEF":
        return 0.015 + 0.012 * max(0.0, c - 4.0)
    return 0.0


def cost_prior_xa90(pos: str, cost: int) -> float:
    c = cost / 10.0
    gap = max(0.0, c - 4.5)
    if pos == "MID":
        return 0.05 + 0.030 * gap
    if pos == "FWD":
        return 0.04 + 0.014 * gap
    if pos == "DEF":
        return 0.025 + 0.010 * max(0.0, c - 4.0)
    return 0.015


def blend(observed: float, prior: float, minutes: int, n_full: int = 1800) -> float:
    w = min(1.0, minutes / n_full)
    return w * observed + (1.0 - w) * prior


def rates_for_v1(player: Player) -> dict[str, float]:
    """Production / E016 control rate path: blend observed xG/xA toward cost priors."""
    xg = blend(player.xg90, cost_prior_xg90(player.position, player.now_cost), player.minutes)
    xa = blend(player.xa90, cost_prior_xa90(player.position, player.now_cost), player.minutes)
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


def rates_for(player: Player) -> dict[str, float]:
    """Alias for rates_v1 (backward-compatible name)."""
    return rates_for_v1(player)


def resolve_rates(
    player: Player,
    rates_version: str,
    rates_priors: dict[int, tuple[float, float]] | None,
    *,
    as_of_gw: int = 1,
    recent_minutes: dict[int, int] | None = None,
) -> dict[str, float]:
    if rates_version == "v1":
        return rates_for_v1(player)
    if rates_version in {"v2b", "v2b_d", "v2b_e"}:
        from engine.rates_v2b import rates_for_v2b, rates_for_v2b_d, rates_for_v2b_e

        prior = (rates_priors or {}).get(player.id)
        px = prior[0] if prior else None
        pa = prior[1] if prior else None
        if rates_version == "v2b_d":
            return rates_for_v2b_d(player, px, pa)
        if rates_version == "v2b_e":
            return rates_for_v2b_e(
                player,
                px,
                pa,
                as_of_gw=as_of_gw,
                recent4=(recent_minutes or {}).get(player.id, 0),
            )
        return rates_for_v2b(player, px, pa)
    raise ValueError("rates_version must be 'v1', 'v2b', 'v2b_d', or 'v2b_e'")



def utility(mu: float, sigma: float, p10: float, strategy: str) -> float:
    if strategy == "safe":
        return mu - 0.40 * sigma
    if strategy == "aggressive":
        return mu + 3.0 * p10
    return mu


def _role_points(
    rng: np.random.Generator,
    n: int,
    mins: float,
    play_pts: int,
    lam_g: float,
    lam_a: float,
    p_cs: float,
    p_dc: float,
    lam_saves: float,
    lam_gc: float,
    p_y: float,
    lam_bonus: float,
    pts_g: int,
    pts_a: int,
    pts_cs: int,
    pts_dc: int,
    pts_save: int,
    pts_gc: int,
    pts_y: int,
) -> np.ndarray:
    scale = mins / 90.0
    goals = rng.poisson(lam_g * scale, n)
    assists = rng.poisson(lam_a * scale, n)
    cs = (rng.random(n) < p_cs).astype(np.int32) if p_cs > 0 else np.zeros(n, dtype=np.int32)
    dc = (rng.random(n) < p_dc).astype(np.int32) if p_dc > 0 else np.zeros(n, dtype=np.int32)
    saves = rng.poisson(lam_saves * scale, n) if lam_saves > 0 else np.zeros(n, dtype=np.int32)
    gc = rng.poisson(lam_gc * scale, n) if lam_gc > 0 else np.zeros(n, dtype=np.int32)
    yc = (rng.random(n) < min(0.55, p_y * scale)).astype(np.int32)
    bonus = np.clip(rng.poisson(lam_bonus, n), 0, 3)
    return (
        play_pts
        + pts_g * goals
        + pts_a * assists
        + pts_cs * cs
        + pts_dc * dc
        + pts_save * (saves // SAVES_BUCKET)
        + pts_gc * (gc // GC_BUCKET)
        + pts_y * yc
        + bonus
    )


def project_player_gw(
    snapshot: Snapshot,
    player: Player,
    event_id: int,
    gw_offset: int,
    strategy: str,
    rng: np.random.Generator,
    role_start: dict[int, float] | None = None,
    p_start_map: dict[str, float] | None = None,
    rates_version: str = "v1",
    rates_priors: dict[int, tuple[float, float]] | None = None,
    as_of_gw: int = 1,
    recent_minutes: dict[int, int] | None = None,
    fixtures_version: str = "v1",
    fixture_strengths: dict | None = None,
) -> GWProjection:
    scoring = snapshot.scoring
    pos = player.position
    p_start, p_sub, p_60 = minutes_probs(player, gw_offset, role_start)
    if p_start_map is not None:
        p_start, p_sub, p_60 = recalibrate_minutes(p_start, p_sub, p_start_map)
    fixtures = [f for f in snapshot.fixtures_for(event_id) if player.team_id in (f.team_h, f.team_a)]
    n = N_SIMS
    if not fixtures or (p_start + p_sub) < 1e-4:
        return GWProjection(player.id, event_id, len(fixtures), 0, 0, p_start, p_sub, p_60, 0, 0)

    rates = resolve_rates(
        player,
        rates_version,
        rates_priors,
        as_of_gw=as_of_gw,
        recent_minutes=recent_minutes,
    )
    total = np.zeros(n, dtype=np.float64)
    p60_acc = 0.0
    pstart_acc = 0.0

    for fx in fixtures:
        ctx = player_match_context(
            snapshot,
            player.team_id,
            fx,
            fixtures_version=fixtures_version,
            fixture_strengths=fixture_strengths,
        )
        attack_mult = ctx["attack_mult"]
        lam_g = rates["xg90"] * attack_mult
        lam_a = rates["xa90"] * attack_mult
        p_cs_start = ctx["p_cs"] if scoring.clean_sheets[pos] else 0.0
        dc_thr = scoring.dc_threshold[pos]
        p_dc_start = p_poisson_ge(dc_thr, rates["dc90"] * (85 / 90)) if scoring.defensive_contribution[pos] else 0.0
        p_dc_sub = p_poisson_ge(dc_thr, rates["dc90"] * (20 / 90)) if scoring.defensive_contribution[pos] else 0.0
        lam_saves = rates["saves90"] if pos == "GKP" else 0.0
        lam_gc = ctx["opp_xg"] if scoring.goals_conceded[pos] else 0.0
        lam_bonus_start = max(0.05, rates["bonus90"] + 0.22 * (lam_g + lam_a) + 0.15 * p_cs_start)
        lam_bonus_sub = 0.05 * lam_bonus_start

        start_pts = _role_points(
            rng, n, 85.0, scoring.long_play,
            lam_g, lam_a, p_cs_start, p_dc_start, lam_saves, lam_gc, rates["y90"],
            min(1.1, lam_bonus_start),
            scoring.goals_scored[pos], scoring.assists, scoring.clean_sheets[pos],
            scoring.defensive_contribution[pos], scoring.saves, scoring.goals_conceded[pos],
            scoring.yellow_cards,
        )
        sub_pts = _role_points(
            rng, n, 20.0, scoring.short_play,
            lam_g, lam_a, 0.0, p_dc_sub, lam_saves, lam_gc, rates["y90"],
            lam_bonus_sub,
            scoring.goals_scored[pos], scoring.assists, scoring.clean_sheets[pos],
            scoring.defensive_contribution[pos], scoring.saves, scoring.goals_conceded[pos],
            scoring.yellow_cards,
        )
        u = rng.random(n)
        pts = np.zeros(n, dtype=np.float64)
        m_start = u < p_start
        m_sub = (u >= p_start) & (u < p_start + p_sub)
        pts[m_start] = start_pts[m_start]
        pts[m_sub] = sub_pts[m_sub]
        total += pts
        pstart_acc += p_start
        p60_acc += p_start * 0.93 + p_sub * 0.08

    mu = float(total.mean())
    sigma = float(total.std(ddof=1))
    p10 = float((total >= 10).mean())
    p90 = float(np.quantile(total, 0.90))
    nfx = len(fixtures)
    return GWProjection(
        player_id=player.id,
        event_id=event_id,
        n_fixtures=nfx,
        mu=mu,
        sigma=sigma,
        p_start=min(1.0, pstart_acc / nfx),
        p_sub=p_sub,
        p_60=min(1.0, p60_acc / nfx),
        p_10_plus=p10,
        p90=p90,
    )


def project_all(
    snapshot: Snapshot,
    horizon: int,
    strategy: str,
    seed: int = 7,
    minutes_version: str = "v2am_s",
    p_start_map: dict[str, float] | None = None,
    rates_version: str = "v1",
    fixtures_version: str = "v1",
    share_diags_out: list | None = None,
) -> list[PlayerProjection]:
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {STRATEGIES}")
    if minutes_version not in {"v1", "v2am", "v2am_s", "v2am_share", "v2c", "v2c_e"}:
        raise ValueError(
            "minutes_version must be 'v1', 'v2am', 'v2am_s', 'v2am_share', 'v2c', or 'v2c_e'"
        )
    if rates_version not in {"v1", "v2b", "v2b_d", "v2b_e"}:
        raise ValueError("rates_version must be 'v1', 'v2b', 'v2b_d', or 'v2b_e'")
    if fixtures_version not in {"v1", "v2d"}:
        raise ValueError("fixtures_version must be 'v1' or 'v2d'")
    if minutes_version == "v2am" and p_start_map is None:
        raise ValueError("v2am requires a leave-one-season-out p_start_map")
    if minutes_version != "v2am":
        p_start_map = None
    next_e = snapshot.next_event()
    gw_ids = []
    for e in snapshot.events:
        if e.id >= next_e.id and len(gw_ids) < horizon:
            gw_ids.append(e.id)

    rates_priors: dict[int, tuple[float, float]] | None = None
    fixture_strengths = None
    if rates_version in {"v2b", "v2b_d", "v2b_e"} or fixtures_version == "v2d":
        from engine.harness import SEASON_LABEL

        label_to_season = {v: k for k, v in SEASON_LABEL.items()}
        season_key = label_to_season.get(snapshot.season_label)
        if season_key and rates_version in {"v2b", "v2b_d", "v2b_e"}:
            from engine.rates_v2b import build_rates_priors_for_snapshot

            rates_priors = build_rates_priors_for_snapshot(season_key, snapshot)
        if season_key and fixtures_version == "v2d":
            from engine.fixtures_v2d import strengths_for_season

            fixture_strengths = strengths_for_season(season_key)

    rng = np.random.default_rng(seed)
    as_of_gw = next_e.id
    recent: dict[int, int] = {}
    apply_recent = False
    season_key: str | None = None
    if minutes_version in {"v2am_s", "v2am_share", "v2c", "v2c_e"} or rates_version == "v2b_e":
        from engine.harness import SEASON_LABEL, recent_minutes_by_element

        label_to_season = {v: k for k, v in SEASON_LABEL.items()}
        season_key = label_to_season.get(snapshot.season_label)
        if season_key and as_of_gw > RECENT_WINDOW:
            recent = recent_minutes_by_element(season_key, as_of_gw, window=RECENT_WINDOW)
            apply_recent = minutes_version in {"v2am_s", "v2am_share", "v2c", "v2c_e"}
    if minutes_version in {"v2c", "v2c_e"}:
        from engine.minutes_v2c import build_role_start_v2c, build_role_start_v2c_e

        if not season_key:
            from engine.harness import SEASON_LABEL

            label_to_season = {v: k for k, v in SEASON_LABEL.items()}
            season_key = label_to_season.get(snapshot.season_label)
        if not season_key:
            raise ValueError(f"{minutes_version} requires a historical season_label mapped to a season key")
        team_names = {tid: t.name for tid, t in snapshot.teams.items()}
        builder = build_role_start_v2c_e if minutes_version == "v2c_e" else build_role_start_v2c
        role_start = builder(
            snapshot.players,
            season=season_key,
            as_of_gw=as_of_gw,
            recent_minutes=recent,
            apply_recent=apply_recent,
            team_names=team_names,
        )
    elif minutes_version == "v2am_share":
        from engine.minutes_v2am_share import build_role_start_v2am_share

        if not season_key:
            from engine.harness import SEASON_LABEL

            label_to_season = {v: k for k, v in SEASON_LABEL.items()}
            season_key = label_to_season.get(snapshot.season_label)
        team_names = {tid: t.name for tid, t in snapshot.teams.items()}
        # Live without season_key → identity to v2am_s (E042-A)
        role_start, diags = build_role_start_v2am_share(
            snapshot.players,
            season=season_key,
            as_of_gw=as_of_gw,
            recent_minutes=recent,
            apply_recent=apply_recent,
            team_names=team_names,
        )
        if share_diags_out is not None:
            share_diags_out.extend(diags)
    elif minutes_version == "v2am_s":
        role_start = build_role_start_struct(
            snapshot.players, recent_minutes=recent, apply_recent=apply_recent
        )
    else:
        role_start = build_role_start(snapshot.players)
    out: list[PlayerProjection] = []
    for player in snapshot.players:
        by_gw = {}
        h_mu = 0.0
        h_var = 0.0
        h_u = 0.0
        for offset, gw in enumerate(gw_ids):
            gw_rng = np.random.default_rng(rng.integers(0, 2**32 - 1) ^ (player.id * 1009 + gw))
            pred = project_player_gw(
                snapshot,
                player,
                gw,
                offset,
                strategy,
                gw_rng,
                role_start,
                p_start_map=p_start_map,
                rates_version=rates_version,
                rates_priors=rates_priors,
                as_of_gw=as_of_gw,
                recent_minutes=recent,
                fixtures_version=fixtures_version,
                fixture_strengths=fixture_strengths,
            )
            by_gw[gw] = pred
            w = DECAY ** offset
            h_mu += w * pred.mu
            h_var += (w * pred.sigma) ** 2
            h_u += w * utility(pred.mu, pred.sigma, pred.p_10_plus, strategy)
        nxt = by_gw[gw_ids[0]]
        out.append(
            PlayerProjection(
                player=player,
                by_gw=by_gw,
                horizon_mu=h_mu,
                horizon_sigma=math.sqrt(h_var),
                horizon_utility=h_u,
                next_mu=nxt.mu,
                next_sigma=nxt.sigma,
                next_p_start=nxt.p_start,
                next_p_60=nxt.p_60,
                next_p_10=nxt.p_10_plus,
                next_utility=utility(nxt.mu, nxt.sigma, nxt.p_10_plus, strategy),
            )
        )
    return out
