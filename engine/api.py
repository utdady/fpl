"""Live FPL API ingest with a timestamped on-disk snapshot."""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from engine.models import (
    POS_BY_ID,
    Event,
    Fixture,
    Player,
    Snapshot,
    Team,
)
from engine.scoring import parse_scoring, parse_squad

API_BASE = "https://fantasy.premierleague.com/api"
USER_AGENT = "fpl-v1/0.1 (local research tool)"
CACHE_DIR = Path(".cache/fpl")


def _get(path: str):
    req = urllib.request.Request(
        f"{API_BASE}/{path.lstrip('/')}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def _f(val, default=0.0) -> float:
    if val is None or val == "":
        return float(default)
    try:
        return float(val)
    except (TypeError, ValueError):
        return float(default)


def _i(val, default=None):
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def load_snapshot(refresh: bool = False, ttl_s: int = 1800) -> Snapshot:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    boot_path = CACHE_DIR / "bootstrap.json"
    fix_path = CACHE_DIR / "fixtures.json"
    meta_path = CACHE_DIR / "meta.json"

    use_cache = (
        not refresh
        and boot_path.exists()
        and fix_path.exists()
        and meta_path.exists()
        and (time.time() - boot_path.stat().st_mtime) < ttl_s
    )
    if use_cache:
        bootstrap = json.loads(boot_path.read_text(encoding="utf-8"))
        fixtures = json.loads(fix_path.read_text(encoding="utf-8"))
        as_of = datetime.fromisoformat(json.loads(meta_path.read_text(encoding="utf-8"))["as_of"])
    else:
        bootstrap = _get("bootstrap-static/")
        fixtures = _get("fixtures/")
        as_of = datetime.now(timezone.utc)
        boot_path.write_text(json.dumps(bootstrap), encoding="utf-8")
        fix_path.write_text(json.dumps(fixtures), encoding="utf-8")
        meta_path.write_text(json.dumps({"as_of": as_of.isoformat()}), encoding="utf-8")

    return parse_snapshot(bootstrap, fixtures, as_of)


def parse_snapshot(bootstrap: dict, fixtures: list, as_of: datetime) -> Snapshot:
    game_config = bootstrap.get("game_config") or {}
    scoring = parse_scoring(game_config)
    squad = parse_squad(game_config, bootstrap.get("element_types") or [])

    teams = {}
    for t in bootstrap.get("teams") or []:
        sh = t.get("strength_overall_home") or 3
        sa = t.get("strength_overall_away") or 3
        teams[t["id"]] = Team(
            id=t["id"],
            name=t["name"],
            short_name=t["short_name"],
            strength_home=int(sh),
            strength_away=int(sa),
        )

    events = [
        Event(
            id=e["id"],
            name=e.get("name") or f"Gameweek {e['id']}",
            deadline=e.get("deadline_time"),
            is_current=bool(e.get("is_current")),
            is_next=bool(e.get("is_next")),
            finished=bool(e.get("finished")),
        )
        for e in bootstrap.get("events") or []
    ]

    fx = [
        Fixture(
            id=f["id"],
            event=f.get("event"),
            team_h=f["team_h"],
            team_a=f["team_a"],
            kickoff=f.get("kickoff_time"),
            finished=bool(f.get("finished")),
            fdr_home=f.get("team_h_difficulty"),
            fdr_away=f.get("team_a_difficulty"),
        )
        for f in fixtures
    ]

    players = []
    for e in bootstrap.get("elements") or []:
        pos = POS_BY_ID.get(e["element_type"], "MID")
        minutes = int(e.get("minutes") or 0)
        starts = int(e.get("starts") or 0)
        games_hint = max(starts, round(minutes / 90) if minutes else 0)
        players.append(
            Player(
                id=e["id"],
                web_name=e.get("web_name") or "",
                first_name=e.get("first_name") or "",
                second_name=e.get("second_name") or "",
                element_type=int(e["element_type"]),
                position=pos,
                team_id=int(e["team"]),
                now_cost=int(e["now_cost"]),
                status=e.get("status") or "u",
                can_select=bool(e.get("can_select", True)),
                news=e.get("news") or "",
                chance_this=_i(e.get("chance_of_playing_this_round")),
                chance_next=_i(e.get("chance_of_playing_next_round")),
                minutes=minutes,
                starts=starts,
                xg90=_f(e.get("expected_goals_per_90")),
                xa90=_f(e.get("expected_assists_per_90")),
                xgc90=_f(e.get("expected_goals_conceded_per_90")),
                dc90=_f(e.get("defensive_contribution_per_90")),
                saves90=_f(e.get("saves_per_90")),
                yellow=int(e.get("yellow_cards") or 0),
                red=int(e.get("red_cards") or 0),
                bonus=int(e.get("bonus") or 0),
                goals=int(e.get("goals_scored") or 0),
                assists_n=int(e.get("assists") or 0),
                games_hint=games_hint,
                pen_order=_i(e.get("penalties_order")),
                corners_order=_i(e.get("corners_and_indirect_freekicks_order")),
                selected_by=_f(e.get("selected_by_percent")),
                ep_next=_f(e.get("ep_next")) if e.get("ep_next") not in (None, "") else None,
            )
        )

    season = "2026/27"
    static_url = (game_config.get("settings") or {}).get("static_content_url", "")
    if "2026_27" in static_url:
        season = "2026/27"

    return Snapshot(
        as_of=as_of,
        season_label=season,
        scoring=scoring,
        squad=squad,
        teams=teams,
        events=events,
        fixtures=fx,
        players=players,
    )
