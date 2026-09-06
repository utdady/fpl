"""Unit tests for live availability-application monitor."""
from __future__ import annotations

import unittest

from engine.avail_monitor import availability_application_report
from engine.models import Player


def _p(**kwargs) -> Player:
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


class TestAvailMonitor(unittest.TestCase):
    def test_all_available_warns(self) -> None:
        players = [_p(id=i) for i in range(5)]
        r = availability_application_report(players)
        self.assertFalse(r["ok"])
        self.assertEqual(r["n_avail_lt1"], 0)
        self.assertIn("zero_availability_demotions", r["warnings"])

    def test_doubtful_counts(self) -> None:
        players = [
            _p(id=1, status="a"),
            _p(id=2, status="d", chance_next=50),
            _p(id=3, status="i", chance_next=0),
        ]
        r = availability_application_report(players)
        self.assertTrue(r["ok"])
        self.assertEqual(r["n_status_not_a"], 2)
        self.assertEqual(r["n_avail_lt1"], 2)
        self.assertEqual(r["status_counts"].get("d"), 1)
        self.assertEqual(r["status_counts"].get("i"), 1)


if __name__ == "__main__":
    unittest.main()
