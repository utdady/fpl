"""Unit tests for E044-A fplcache availability hydrate (no network)."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from engine.fplcache_avail import AvailFields, hydrate_players, snapshot_utc_to_relpath
from engine.minutes import availability
from engine.models import Player


def _player(**kwargs) -> Player:
    base = dict(
        id=1,
        web_name="X",
        first_name="A",
        second_name="B",
        element_type=3,
        position="MID",
        team_id=1,
        now_cost=70,
        status="a",
        can_select=True,
        news="",
        chance_this=None,
        chance_next=None,
        minutes=1000,
        starts=10,
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
        games_hint=10,
        pen_order=None,
        corners_order=None,
        selected_by=1.0,
        ep_next=None,
    )
    base.update(kwargs)
    return Player(**base)


class TestFplaHydrate(unittest.TestCase):
    def test_snapshot_path(self) -> None:
        dt = datetime(2022, 8, 5, 12, 49, tzinfo=timezone.utc)
        self.assertEqual(snapshot_utc_to_relpath(dt), "2022/8/5/1249.json.xz")

    def test_hydrate_doubtful_lowers_availability(self) -> None:
        p = _player()
        self.assertEqual(availability(p, 0), 1.0)
        overlay = {
            1: AvailFields(
                status="d",
                chance_this=None,
                chance_next=25,
                can_select=True,
                code=99,
            )
        }
        out, reasons = hydrate_players([p], overlay)
        self.assertEqual(reasons[0], "joined_id")
        self.assertEqual(out[0].status, "d")
        self.assertEqual(out[0].chance_next, 25)
        self.assertAlmostEqual(availability(out[0], 0), 0.25)

    def test_join_miss_identity(self) -> None:
        p = _player(id=7, status="a")
        overlay = {
            1: AvailFields("i", 0, 0, True, 1),
        }
        out, reasons = hydrate_players([p], overlay)
        self.assertEqual(reasons[0], "join_miss")
        self.assertIs(out[0], p)
        self.assertEqual(availability(out[0], 0), 1.0)

    def test_no_overlay_identity(self) -> None:
        p = _player()
        out, reasons = hydrate_players([p], None)
        self.assertEqual(reasons[0], "no_overlay")
        self.assertEqual(out[0].status, "a")

    def test_injured_zero_when_chance_missing(self) -> None:
        p = _player()
        overlay = {1: AvailFields("i", None, None, True, 1)}
        out, _ = hydrate_players([p], overlay)
        self.assertEqual(availability(out[0], 0), 0.0)


if __name__ == "__main__":
    unittest.main()
