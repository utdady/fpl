"""Unit tests for E053-A expected_goals_adxg (no network / Cap / MAE peek)."""
from __future__ import annotations

import unittest

from engine.fixtures import (
    AWAY_ADV,
    HOME_ADV,
    LEAGUE_AVG,
    adxg_intensity_means,
    expected_goals_adxg,
)
from engine.fplcache_strength_ad import AdxgFields


class TestV1Adxg(unittest.TestCase):
    def test_equal_league_sanity(self) -> None:
        ov = {
            1: AdxgFields(1200, 1200, 1200, 1200),
            2: AdxgFields(1200, 1200, 1200, 1200),
        }
        e_h, e_a = expected_goals_adxg(1, 2, ov)
        self.assertAlmostEqual(e_h, LEAGUE_AVG * HOME_ADV, places=9)
        self.assertAlmostEqual(e_a, LEAGUE_AVG * AWAY_ADV, places=9)
        self.assertAlmostEqual(e_h, 1.485, places=9)
        self.assertAlmostEqual(e_a, 1.188, places=9)

    def test_strong_attack_raises_e_home(self) -> None:
        ov = {
            1: AdxgFields(1400, 1200, 1200, 1200),  # strong home attack
            2: AdxgFields(1200, 1200, 1200, 1000),  # weak away defence
        }
        e_h, _ = expected_goals_adxg(1, 2, ov)
        e0_h, _ = expected_goals_adxg(
            1, 2,
            {
                1: AdxgFields(1200, 1200, 1200, 1200),
                2: AdxgFields(1200, 1200, 1200, 1200),
            },
        )
        self.assertGreater(e_h, e0_h)

    def test_strong_defence_lowers_opp_xg(self) -> None:
        # Strong away defence should reduce e_home
        weak_def = {
            1: AdxgFields(1200, 1200, 1200, 1200),
            2: AdxgFields(1200, 1200, 1200, 1000),
        }
        strong_def = {
            1: AdxgFields(1200, 1200, 1200, 1200),
            2: AdxgFields(1200, 1200, 1200, 1400),
        }
        e_weak, _ = expected_goals_adxg(1, 2, weak_def)
        e_strong, _ = expected_goals_adxg(1, 2, strong_def)
        self.assertLess(e_strong, e_weak)

    def test_empty_overlay_is_equal_league(self) -> None:
        e_h, e_a = expected_goals_adxg(1, 2, None)
        self.assertAlmostEqual(e_h, 1.485, places=9)
        self.assertAlmostEqual(e_a, 1.188, places=9)

    def test_means_positive_only(self) -> None:
        ov = {
            1: AdxgFields(1000, 1100, 1200, 1300),
            2: AdxgFields(1400, 1300, 1000, 1100),
            3: AdxgFields(0, 0, 0, 0),
        }
        m = adxg_intensity_means(ov)
        self.assertAlmostEqual(m[0], 1200.0, places=9)
        self.assertAlmostEqual(m[1], 1200.0, places=9)
        self.assertAlmostEqual(m[2], 1100.0, places=9)
        self.assertAlmostEqual(m[3], 1200.0, places=9)


if __name__ == "__main__":
    unittest.main()
