"""Parse live FPL scoring and squad rules. Thresholds that the API omits are documented defaults."""
from __future__ import annotations

from engine.models import POS_BY_ID, ScoringRules, SquadRules

# FPL does not publish DC action thresholds on bootstrap-static.
# 2025/26–2026/27 published rules: DEF 10 CBIT, MID/FWD 12 CBIT+recoveries.
DC_THRESHOLD = {"GKP": 99, "DEF": 10, "MID": 12, "FWD": 12}

# Saves: API lists 1 point. In FPL that is 1 point per 3 saves.
SAVES_BUCKET = 3
# Goals conceded: -1 per 2 goals for GKP/DEF.
GC_BUCKET = 2


def parse_scoring(game_config: dict) -> ScoringRules:
    raw = game_config.get("scoring") or {}

    def pos_map(key: str, default: dict[str, int]) -> dict[str, int]:
        val = raw.get(key, default)
        if isinstance(val, dict):
            return {k: int(v) for k, v in val.items()}
        return {pos: int(val) for pos in ("GKP", "DEF", "MID", "FWD")}

    return ScoringRules(
        long_play=int(raw.get("long_play", 2)),
        short_play=int(raw.get("short_play", 1)),
        goals_scored=pos_map("goals_scored", {"GKP": 6, "DEF": 6, "MID": 5, "FWD": 4}),
        assists=int(raw.get("assists", 3)),
        clean_sheets=pos_map("clean_sheets", {"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0}),
        defensive_contribution=pos_map(
            "defensive_contribution", {"GKP": 0, "DEF": 2, "MID": 2, "FWD": 2}
        ),
        goals_conceded=pos_map("goals_conceded", {"GKP": -1, "DEF": -1, "MID": 0, "FWD": 0}),
        saves=int(raw.get("saves", 1)),
        yellow_cards=int(raw.get("yellow_cards", -1)),
        red_cards=int(raw.get("red_cards", -3)),
        bonus=int(raw.get("bonus", 1)),
        dc_threshold=dict(DC_THRESHOLD),
    )


def parse_squad(game_config: dict, element_types: list[dict]) -> SquadRules:
    rules = game_config.get("rules") or {}
    select = {}
    min_play = {}
    max_play = {}
    for et in element_types:
        pos = POS_BY_ID[et["id"]]
        select[pos] = int(et["squad_select"])
        min_play[pos] = int(et["squad_min_play"])
        max_play[pos] = int(et["squad_max_play"])
    return SquadRules(
        squad_size=int(rules.get("squad_squadsize", 15)),
        squad_play=int(rules.get("squad_squadplay", 11)),
        budget=int(rules.get("squad_total_spend", 1000)),
        team_limit=int(rules.get("squad_team_limit", 3)),
        squad_select=select,
        min_play=min_play,
        max_play=max_play,
    )
