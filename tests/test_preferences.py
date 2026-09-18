"""PRODUCT v0 preference-conditioned Model A re-solve."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from engine.harness import default_scoring, default_squad
from engine.models import Event, Player, PlayerProjection, Snapshot, Team
from engine.optimize import solve_squad
from engine.preferences import (
    Preferences,
    preferences_from_payload,
    solve_preference_pair,
    validate_preferences,
)


def _player(pid: int, pos: str, team_id: int, cost: int) -> Player:
    etype = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}[pos]
    return Player(
        id=pid,
        web_name=f"{pos}{pid}",
        first_name="",
        second_name="",
        element_type=etype,
        position=pos,
        team_id=team_id,
        now_cost=cost,
        status="a",
        can_select=True,
        news="",
        chance_this=None,
        chance_next=None,
        minutes=90,
        starts=1,
        xg90=0.0,
        xa90=0.0,
        xgc90=0.0,
        dc90=0.0,
        saves90=0.0,
        yellow=0,
        red=0,
        bonus=0,
        goals=0,
        assists_n=0,
        total_points=0,
        games_hint=1,
        pen_order=None,
        corners_order=None,
        selected_by=0.0,
        ep_next=None,
    )


def _proj(player: Player, util: float) -> PlayerProjection:
    return PlayerProjection(
        player=player,
        by_gw={},
        horizon_mu=util,
        horizon_sigma=1.0,
        horizon_utility=util,
        next_mu=util,
        next_sigma=1.0,
        next_p_start=0.90,
        next_p_60=0.80,
        next_p_10=0.20,
        next_utility=util,
    )


def _toy() -> tuple[Snapshot, list[PlayerProjection]]:
    players: list[Player] = []
    projs: list[PlayerProjection] = []
    pid = 1
    util = 20.0
    for pos, n in (("GKP", 4), ("DEF", 8), ("MID", 8), ("FWD", 5)):
        for _ in range(n):
            team_id = 1 + (pid % 8)
            p = _player(pid, pos, team_id, cost=50)
            players.append(p)
            projs.append(_proj(p, util))
            util -= 0.25
            pid += 1
    teams = {
        tid: Team(id=tid, name=f"T{tid}", short_name=f"T{tid}", strength_home=3, strength_away=3)
        for tid in range(1, 9)
    }
    events = [
        Event(id=1, name="GW1", deadline=None, is_current=False, is_next=True, finished=False)
    ]
    snap = Snapshot(
        as_of=datetime.now(timezone.utc),
        season_label="toy",
        scoring=default_scoring(),
        squad=default_squad(),
        teams=teams,
        events=events,
        fixtures=[],
        players=players,
    )
    return snap, projs


class TestPreferenceCuts(unittest.TestCase):
    def test_validate_rejects_overlap_and_bad_bank(self) -> None:
        with self.assertRaises(ValueError):
            validate_preferences(Preferences(lock=frozenset({1}), ban=frozenset({1})))
        with self.assertRaises(ValueError):
            preferences_from_payload({"min_bank_m": 0.7})
        with self.assertRaises(ValueError):
            preferences_from_payload({"club_max": {"1": 3}})

    def test_min_bank_reserves_itb(self) -> None:
        snap, projs = _toy()
        s1 = solve_squad(snap, projs, strategy="balanced", objective="horizon")
        s2 = solve_squad(
            snap, projs, strategy="balanced", objective="horizon", min_bank=10
        )
        self.assertGreaterEqual(s2.bank, 10)
        self.assertLessEqual(s2.cost, snap.squad.budget - 10)
        # Same objective; bank cut only changes feasible set.
        self.assertEqual(len(s1.players), 15)
        self.assertEqual(len(s2.players), 15)

    def test_club_limit_and_lock(self) -> None:
        snap, projs = _toy()
        s1 = solve_squad(snap, projs, strategy="balanced", objective="horizon")
        # Lock a mid from S1; ban another mid not needed.
        mid = next(p for p in s1.players if p.position == "MID")
        result = solve_preference_pair(
            snap,
            projs,
            Preferences(lock=frozenset({mid.id}), club_max={mid.team_id: 2}),
            strategy="balanced",
        )
        self.assertTrue(result.feasible)
        assert result.s2 is not None
        self.assertIn(mid.id, result.s2.ids)
        from collections import Counter

        # Rebuild counts from ids via snapshot players.
        by_id = {p.id: p for p in snap.players}
        counts = Counter(by_id[i].team_id for i in result.s2.ids)
        self.assertLessEqual(counts[mid.team_id], 2)

    def test_infeasible_message(self) -> None:
        snap, projs = _toy()
        keep = {p.id for p in snap.players[:10]}
        ban = frozenset(p.id for p in snap.players if p.id not in keep)
        result = solve_preference_pair(
            snap,
            projs,
            Preferences(ban=ban),
            strategy="balanced",
        )
        self.assertFalse(result.feasible)
        self.assertIsNone(result.s2)
        self.assertIn("No feasible squad", result.message or "")

    def test_empty_prefs_s1_only(self) -> None:
        snap, projs = _toy()
        result = solve_preference_pair(snap, projs, Preferences(), strategy="balanced")
        self.assertTrue(result.feasible)
        self.assertIsNone(result.s2)


if __name__ == "__main__":
    unittest.main()
