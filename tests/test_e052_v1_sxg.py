"""Unit tests for E052-A expected_goals_sxg (no network / Cap / MAE peek)."""
from __future__ import annotations

import unittest

from engine.fixtures import (
    AWAY_ADV,
    HOME_ADV,
    LEAGUE_AVG,
    expected_goals,
    expected_goals_sxg,
    intensity_means,
    _str,
)
from engine.models import Team


class TestV1Sxg(unittest.TestCase):
    def test_equal_league_sanity(self) -> None:
        a = Team(1, "A", "AAA", 1200, 1200)
        b = Team(2, "B", "BBB", 1200, 1200)
        m_h, m_a = 1200.0, 1200.0
        e_h, e_a = expected_goals_sxg(a, b, m_h=m_h, m_a=m_a)
        self.assertAlmostEqual(e_h, LEAGUE_AVG * HOME_ADV, places=9)
        self.assertAlmostEqual(e_a, LEAGUE_AVG * AWAY_ADV, places=9)
        self.assertAlmostEqual(e_h, 1.485, places=9)
        self.assertAlmostEqual(e_a, 1.188, places=9)

    def test_strong_home_raises_e_home(self) -> None:
        strong = Team(1, "S", "STR", 1400, 1400)
        weak = Team(2, "W", "WEK", 1000, 1000)
        m_h, m_a = 1200.0, 1200.0
        e_h, e_a = expected_goals_sxg(strong, weak, m_h=m_h, m_a=m_a)
        e0_h, e0_a = expected_goals_sxg(
            Team(1, "S", "STR", 1200, 1200),
            Team(2, "W", "WEK", 1200, 1200),
            m_h=m_h, m_a=m_a,
        )
        self.assertGreater(e_h, e0_h)
        self.assertLess(e_a, e0_a)

    def test_missing_strength_is_league_mean(self) -> None:
        home = Team(1, "H", "HOM", 0, 0)
        away = Team(2, "A", "AWY", 1200, 1200)
        e_h, e_a = expected_goals_sxg(home, away, m_h=1200.0, m_a=1200.0)
        # I_h=1, I_a=1 → equal-league
        self.assertAlmostEqual(e_h, 1.485, places=9)
        self.assertAlmostEqual(e_a, 1.188, places=9)

    def test_intensity_means_positive_only(self) -> None:
        teams = [
            Team(1, "A", "AAA", 1000, 1100),
            Team(2, "B", "BBB", 1400, 1300),
            Team(3, "C", "CCC", 0, 0),
        ]
        m_h, m_a = intensity_means(teams)
        self.assertAlmostEqual(m_h, 1200.0, places=9)
        self.assertAlmostEqual(m_a, 1200.0, places=9)

    def test_differs_from_production_str_on_modern_overall(self) -> None:
        strong = Team(1, "S", "STR", 1350, 1350)
        weak = Team(2, "W", "WEK", 1000, 1000)
        e_ctrl = expected_goals(strong, weak, bucket_fn=_str)
        m_h, m_a = intensity_means([strong, weak])
        e_sxg = expected_goals_sxg(strong, weak, m_h=m_h, m_a=m_a)
        self.assertNotEqual(e_ctrl, e_sxg)


if __name__ == "__main__":
    unittest.main()
