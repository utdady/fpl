"""Explicit checks for optional local historical datasets.

Vaastav under data/vaastav/ is gitignored. Historical parity tests may skip
only when this helper reports unavailability — never on bare Exception.
"""
from __future__ import annotations

from engine.harness import PREV_SEASON, season_dir
from engine.metrics import record_path


def unavailable_reason(season: str) -> str | None:
    """Return a skip reason if optional season data is missing; else None."""
    players = season_dir(season) / "players_raw.csv"
    if not players.exists():
        return f"vaastav season cache missing: {players}"
    prev = PREV_SEASON.get(season)
    if prev:
        prev_players = season_dir(prev) / "players_raw.csv"
        if not prev_players.exists():
            return f"vaastav prev-season cache missing: {prev_players}"
    if not any(record_path(gw, season=season).exists() for gw in range(1, 39)):
        return f"no historical GW records for {season}"
    return None
