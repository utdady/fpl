"""Unit tests for E047-A strength hydrate (no network)."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from engine.fplcache_strength import StrengthFields, hydrate_snapshot_teams
from engine.models import Event, ScoringRules, Snapshot, SquadRules, Team


def _snap(teams: dict[int, Team]) -> Snapshot:
    return Snapshot(
        as_of=datetime.now(timezone.utc),
        season_label="2024/25",
        scoring=ScoringRules(
            long_play=2, short_play=1,
            goals_scored={"GKP": 6, "DEF": 6, "MID": 5, "FWD": 4},
            assists=3,
            clean_sheets={"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0},
            defensive_contribution={"GKP": 0, "DEF": 2, "MID": 2, "FWD": 2},
            goals_conceded={"GKP": -1, "DEF": -1, "MID": 0, "FWD": 0},
            saves=1, yellow_cards=-1, red_cards=-3, bonus=1,
            dc_threshold={"GKP": 99, "DEF": 10, "MID": 12, "FWD": 12},
        ),
        squad=SquadRules(
            squad_size=15, squad_play=11, budget=1000, team_limit=3,
            squad_select={"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3},
            min_play={"GKP": 1, "DEF": 3, "MID": 2, "FWD": 1},
            max_play={"GKP": 1, "DEF": 5, "MID": 5, "FWD": 3},
        ),
        teams=teams,
        events=[Event(1, "GW1", None, False, True, False)],
        fixtures=[],
        players=[],
    )


class TestV1Fpls(unittest.TestCase):
    def test_no_season_identity(self) -> None:
        t = Team(1, "A", "AAA", 4, 3)
        snap, diags = hydrate_snapshot_teams(_snap({1: t}), season=None, as_of_gw=1)
        self.assertEqual(snap.teams[1].strength_home, 4)
        self.assertEqual(diags[0].identity_reason, "no_season")
        self.assertFalse(diags[0].replaced)

    def test_replace_via_monkeypatch(self) -> None:
        from engine import fplcache_strength as mod

        t = Team(1, "A", "AAA", 3, 3)
        snap0 = _snap({1: t})

        def fake_load(season: str, gw: int):
            return {1: StrengthFields(5, 4)}

        old = mod.load_strengths
        mod.load_strengths = fake_load  # type: ignore
        try:
            snap1, diags = hydrate_snapshot_teams(snap0, season="2024-25", as_of_gw=10)
        finally:
            mod.load_strengths = old  # type: ignore
        self.assertEqual(snap1.teams[1].strength_home, 5)
        self.assertEqual(snap1.teams[1].strength_away, 4)
        self.assertTrue(diags[0].replaced)
        # Original snapshot object teams unchanged (new Snapshot)
        self.assertEqual(snap0.teams[1].strength_home, 3)


if __name__ == "__main__":
    unittest.main()
