"""Historical snapshot builder from Vaastav data (as-of-T discipline).

Usage:
    from engine.harness import build_snapshot, ensure_vaastav
    snap = build_snapshot("2025-26", as_of_gw=1)
"""
from __future__ import annotations

import csv
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from engine.models import (
    POS_BY_ID,
    Event,
    Fixture,
    Player,
    ScoringRules,
    Snapshot,
    SquadRules,
    Team,
)
from engine.scoring import DC_THRESHOLD, GC_BUCKET, SAVES_BUCKET

VAASTAV_REPO = Path("data/vaastav")
VAASTAV_ROOT = VAASTAV_REPO / "data"
SUPPORTED_SEASONS = ("2022-23", "2023-24", "2024-25", "2025-26")
SEASON_LABEL = {"2022-23": "2022/23", "2023-24": "2023/24", "2024-25": "2024/25", "2025-26": "2025/26"}
PREV_SEASON = {"2025-26": "2024-25", "2024-25": "2023-24", "2023-24": "2022-23", "2022-23": "2021-22"}
POS_TO_ID = {v: k for k, v in POS_BY_ID.items()}


@dataclass
class PlayerAgg:
    minutes: int = 0
    starts: int = 0
    goals: int = 0
    assists: int = 0
    bonus: int = 0
    yellow: int = 0
    red: int = 0
    saves: int = 0
    total_points: int = 0
    xg: float = 0.0
    xa: float = 0.0
    xgc: float = 0.0
    dc: float = 0.0


def _f(val, default=0.0) -> float:
    if val is None or val == "":
        return float(default)
    try:
        return float(val)
    except (TypeError, ValueError):
        return float(default)


def _i(val, default=0) -> int:
    if val is None or val == "":
        return int(default)
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return int(default)


def _i_opt(val):
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def season_dir(season: str) -> Path:
    return VAASTAV_ROOT / season


def ensure_vaastav(seasons: tuple[str, ...] | None = None) -> Path:
    """Clone Vaastav data if missing; checkout requested season folders."""
    needed = set(seasons or SUPPORTED_SEASONS)
    for s in list(needed):
        prev = PREV_SEASON.get(s)
        if prev:
            needed.add(prev)
    if not VAASTAV_REPO.exists():
        VAASTAV_REPO.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", "https://github.com/vaastav/Fantasy-Premier-League.git", str(VAASTAV_REPO)],
            check=True,
        )
    for s in sorted(needed):
        path = season_dir(s)
        if not (path / "players_raw.csv").exists():
            subprocess.run(
                ["git", "-C", str(VAASTAV_REPO), "checkout", "HEAD", "--", f"data/{s}"],
                check=True,
            )
    return VAASTAV_ROOT


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _id_code_map(season: str) -> dict[int, int]:
    rows = _read_csv(season_dir(season) / "players_raw.csv")
    out: dict[int, int] = {}
    for row in rows:
        eid = _i(row.get("id"))
        code = _i(row.get("code"))
        if eid and code:
            out[eid] = code
    return out


def aggregate_gw_stats(season: str, through_gw: int | None = None) -> dict[int, PlayerAgg]:
    merged = season_dir(season) / "gws" / "merged_gw.csv"
    if not merged.exists():
        return {}
    rows = _read_csv(merged)
    # Pre-xG seasons (e.g. 2021/22) lack expected_* columns; use goals/assists as rates.
    has_xg = bool(rows) and "expected_goals" in rows[0]
    has_starts = bool(rows) and "starts" in rows[0]
    acc: dict[int, PlayerAgg] = defaultdict(PlayerAgg)
    for row in rows:
        gw = _i(row.get("GW") or row.get("round"), 0)
        if through_gw is not None and gw > through_gw:
            continue
        eid = _i(row.get("element"), 0)
        if not eid:
            continue
        a = acc[eid]
        mins = _i(row.get("minutes"))
        a.minutes += mins
        if has_starts:
            a.starts += _i(row.get("starts"))
        elif mins >= 60:
            a.starts += 1
        goals = _i(row.get("goals_scored"))
        assists = _i(row.get("assists"))
        a.goals += goals
        a.assists += assists
        a.bonus += _i(row.get("bonus"))
        a.yellow += _i(row.get("yellow_cards"))
        a.red += _i(row.get("red_cards"))
        a.saves += _i(row.get("saves"))
        a.total_points += _i(row.get("total_points"))
        if has_xg:
            a.xg += _f(row.get("expected_goals"))
            a.xa += _f(row.get("expected_assists"))
            a.xgc += _f(row.get("expected_goals_conceded"))
        else:
            a.xg += float(goals)
            a.xa += float(assists)
        if "defensive_contribution" in row:
            a.dc += _f(row.get("defensive_contribution"))
    return dict(acc)



def recent_minutes_by_element(
    season: str,
    as_of_gw: int,
    window: int = 4,
) -> dict[int, int]:
    """Minutes in GWs (as_of_gw-window) .. (as_of_gw-1), as-of-T only.

    Empty if as_of_gw <= 1. Used by E015 structural minutes.
    """
    if as_of_gw <= 1:
        return {}
    from_gw = max(1, as_of_gw - window)
    through_gw = as_of_gw - 1
    merged = season_dir(season) / "gws" / "merged_gw.csv"
    if not merged.exists():
        return {}
    acc: dict[int, int] = defaultdict(int)
    for row in _read_csv(merged):
        gw = _i(row.get("GW") or row.get("round"), 0)
        if gw < from_gw or gw > through_gw:
            continue
        eid = _i(row.get("element"), 0)
        if not eid:
            continue
        acc[eid] += _i(row.get("minutes"))
    return dict(acc)


def prior_stats_by_code(prev_season: str) -> dict[int, PlayerAgg]:
    id_code = _id_code_map(prev_season)
    agg = aggregate_gw_stats(prev_season)
    by_code: dict[int, PlayerAgg] = {}
    for eid, stats in agg.items():
        code = id_code.get(eid)
        if code:
            by_code[code] = stats
    return by_code


def gw_prices(season: str, gw: int) -> dict[int, int]:
    path = season_dir(season) / "gws" / f"gw{gw}.csv"
    if not path.exists():
        return {}
    return {_i(r["element"]): _i(r["value"]) for r in _read_csv(path) if r.get("element")}


def gw_actuals(season: str, gw: int) -> dict[int, dict]:
    """Per-player GW actuals. Multiple rows (DGW) are summed; identical dupes collapse."""
    path = season_dir(season) / "gws" / f"gw{gw}.csv"
    if not path.exists():
        return {}
    out: dict[int, dict] = {}
    seen_fx: dict[int, set] = {}
    for row in _read_csv(path):
        eid = _i(row.get("element"), 0)
        if not eid:
            continue
        fx = row.get("fixture") or ""
        seen_fx.setdefault(eid, set())
        if fx and fx in seen_fx[eid]:
            continue
        if fx:
            seen_fx[eid].add(fx)
        mins = _i(row.get("minutes"))
        pts = _i(row.get("total_points"))
        cur = out.get(eid)
        if cur is None:
            out[eid] = {
                "actual_points": pts,
                "actual_minutes": mins,
                "did_start": int(mins >= 45),
            }
        else:
            cur["actual_points"] += pts
            cur["actual_minutes"] += mins
            cur["did_start"] = int(cur["did_start"] or mins >= 45)
    return out




def gw_xp(season: str, gw: int) -> dict[int, float]:
    """Official xP from Vaastav GW file. Benchmark only; possible timing leakage."""
    path = season_dir(season) / "gws" / f"gw{gw}.csv"
    if not path.exists():
        return {}
    return {_i(r["element"]): _f(r.get("xP")) for r in _read_csv(path) if r.get("element")}


def prior_points_by_element(season: str) -> dict[int, int]:
    prev = PREV_SEASON.get(season)
    if not prev:
        return {}
    id_code = _id_code_map(season)
    by_code = prior_stats_by_code(prev)
    out: dict[int, int] = {}
    for eid, code in id_code.items():
        stats = by_code.get(code)
        if stats:
            out[eid] = stats.total_points
    return out


def prior_pp90_by_element(season: str, min_minutes: int = 900) -> dict[int, float]:
    prev = PREV_SEASON.get(season)
    if not prev:
        return {}
    id_code = _id_code_map(season)
    by_code = prior_stats_by_code(prev)
    out: dict[int, float] = {}
    for eid, code in id_code.items():
        stats = by_code.get(code)
        if stats and stats.minutes >= min_minutes:
            out[eid] = stats.total_points / (stats.minutes / 90.0)
    return out

def _per90(total: float, minutes: int) -> float:
    if minutes < 1:
        return 0.0
    return total / (minutes / 90.0)


def default_scoring() -> ScoringRules:
    return ScoringRules(
        long_play=2,
        short_play=1,
        goals_scored={"GKP": 6, "DEF": 6, "MID": 5, "FWD": 4},
        assists=3,
        clean_sheets={"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0},
        defensive_contribution={"GKP": 0, "DEF": 2, "MID": 2, "FWD": 2},
        goals_conceded={"GKP": -1, "DEF": -1, "MID": 0, "FWD": 0},
        saves=1,
        yellow_cards=-1,
        red_cards=-3,
        bonus=1,
        dc_threshold=dict(DC_THRESHOLD),
    )


def default_squad() -> SquadRules:
    return SquadRules(
        squad_size=15,
        squad_play=11,
        budget=1000,
        team_limit=3,
        squad_select={"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3},
        min_play={"GKP": 1, "DEF": 3, "MID": 2, "FWD": 1},
        max_play={"GKP": 1, "DEF": 5, "MID": 5, "FWD": 3},
    )


def _stats_for_player(
    code: int,
    current: PlayerAgg | None,
    prior: PlayerAgg | None,
    as_of_gw: int,
) -> PlayerAgg:
    if as_of_gw > 1 and current and current.minutes > 0:
        return current
    if prior and prior.minutes > 0:
        return prior
    return current or prior or PlayerAgg()


def build_snapshot(
    season: str,
    as_of_gw: int,
    as_of: datetime | None = None,
) -> Snapshot:
    """Build a snapshot for predicting GW `as_of_gw`.

    Information cutoff: all data strictly before GW `as_of_gw` kickoffs.
    - as_of_gw=1: prior-season rates + GW1 opening prices/fixtures
    - as_of_gw=N: cumulative stats through GW N-1 + GW N opening prices
    """
    if season not in SUPPORTED_SEASONS:
        raise ValueError(f"Unsupported season {season!r}. Use one of {SUPPORTED_SEASONS}.")
    if not 1 <= as_of_gw <= 38:
        raise ValueError("as_of_gw must be between 1 and 38")

    ensure_vaastav((season,))
    sdir = season_dir(season)
    prev = PREV_SEASON.get(season)
    if not prev or not season_dir(prev).exists():
        ensure_vaastav((prev,) if prev else ())

    target_gw = as_of_gw
    through_gw = as_of_gw - 1
    current_agg = aggregate_gw_stats(season, through_gw=through_gw if through_gw > 0 else 0)
    prior_by_code = prior_stats_by_code(prev) if prev else {}
    prices = gw_prices(season, target_gw)

    teams: dict[int, Team] = {}
    for row in _read_csv(sdir / "teams.csv"):
        tid = _i(row.get("id"))
        if not tid:
            continue
        teams[tid] = Team(
            id=tid,
            name=row.get("name") or "",
            short_name=row.get("short_name") or "",
            strength_home=_i(row.get("strength_overall_home"), 3),
            strength_away=_i(row.get("strength_overall_away"), 3),
        )

    events: list[Event] = []
    for gw in range(1, 39):
        events.append(
            Event(
                id=gw,
                name=f"Gameweek {gw}",
                deadline=None,
                is_current=(gw == target_gw),
                is_next=(gw == target_gw),
                finished=(gw < target_gw),
            )
        )

    fixtures: list[Fixture] = []
    for row in _read_csv(sdir / "fixtures.csv"):
        ev = _i_opt(row.get("event"))
        fixtures.append(
            Fixture(
                id=_i(row.get("id")),
                event=ev,
                team_h=_i(row.get("team_h")),
                team_a=_i(row.get("team_a")),
                kickoff=row.get("kickoff_time"),
                finished=(ev is not None and ev < target_gw),
                fdr_home=_i_opt(row.get("team_h_difficulty")),
                fdr_away=_i_opt(row.get("team_a_difficulty")),
            )
        )

    players: list[Player] = []
    for row in _read_csv(sdir / "players_raw.csv"):
        eid = _i(row.get("id"))
        if not eid:
            continue
        pos = POS_BY_ID.get(_i(row.get("element_type"), 3), "MID")
        code = _i(row.get("code"))
        cur = current_agg.get(eid)
        prior = prior_by_code.get(code) if code else None
        stats = _stats_for_player(code, cur, prior, as_of_gw)

        minutes = stats.minutes if as_of_gw > 1 else 0
        starts = stats.starts if as_of_gw > 1 else 0
        games_hint = max(starts, round(minutes / 90) if minutes else 0)

        price = prices.get(eid, _i(row.get("now_cost")))
        xg90 = _per90(stats.xg, stats.minutes)
        xa90 = _per90(stats.xa, stats.minutes)
        xgc90 = _per90(stats.xgc, stats.minutes)
        dc90 = _per90(stats.dc, stats.minutes)
        saves90 = _per90(float(stats.saves), stats.minutes)

        status = row.get("status") or "a"
        if as_of_gw == 1:
            status = "a"

        players.append(
            Player(
                id=eid,
                web_name=row.get("web_name") or "",
                first_name=row.get("first_name") or "",
                second_name=row.get("second_name") or "",
                element_type=_i(row.get("element_type"), POS_TO_ID.get(pos, 3)),
                position=pos,
                team_id=_i(row.get("team")),
                now_cost=price,
                status=status,
                can_select=status not in {"i", "u"},
                news="",
                chance_this=None,
                chance_next=None,
                minutes=minutes,
                starts=starts,
                xg90=xg90,
                xa90=xa90,
                xgc90=xgc90,
                dc90=dc90,
                saves90=saves90,
                yellow=stats.yellow if as_of_gw > 1 else 0,
                red=stats.red if as_of_gw > 1 else 0,
                bonus=stats.bonus if as_of_gw > 1 else 0,
                goals=stats.goals if as_of_gw > 1 else 0,
                assists_n=stats.assists if as_of_gw > 1 else 0,
                total_points=stats.total_points if as_of_gw > 1 else 0,
                games_hint=games_hint,
                pen_order=_i_opt(row.get("penalties_order")),
                corners_order=_i_opt(row.get("corners_and_indirect_freekicks_order")),
                selected_by=_f(row.get("selected_by_percent")),
                ep_next=None,
            )
        )

    return Snapshot(
        as_of=as_of or datetime.now(timezone.utc),
        season_label=SEASON_LABEL.get(season, season),
        scoring=default_scoring(),
        squad=default_squad(),
        teams=teams,
        events=events,
        fixtures=fixtures,
        players=players,
    )
