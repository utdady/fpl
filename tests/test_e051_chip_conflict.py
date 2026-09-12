"""Unit tests for E051 conflict helpers (no network)."""
from __future__ import annotations

import unittest

from scripts.e051_chip_conflict_diagnostic import (
    analyze,
    multi_collision,
    priority_kept,
    same_gw_pairs,
)


class TestE051Conflict(unittest.TestCase):
    def test_same_gw_pairs(self) -> None:
        t = {"TC": 10, "BB": 10, "FH": 20, "WC": 7}
        pairs = same_gw_pairs(t)
        self.assertEqual(pairs, [("TC", "BB")])

    def test_no_pairs(self) -> None:
        t = {"TC": 1, "BB": 2, "FH": 3, "WC": 4}
        self.assertEqual(same_gw_pairs(t), [])

    def test_multi(self) -> None:
        self.assertTrue(multi_collision({"TC": 5, "BB": 5, "FH": 5, "WC": 1}))
        self.assertFalse(multi_collision({"TC": 5, "BB": 5, "FH": 6, "WC": 1}))

    def test_priority_drops_lower_on_collision(self) -> None:
        # TC and BB both want GW10; WC>FH>TC>BB keeps TC, drops BB
        kept, dropped = priority_kept({"TC": 10, "BB": 10, "FH": 20, "WC": 7})
        self.assertIn("TC", kept)
        self.assertIn("BB", dropped)
        self.assertIn("WC", kept)
        self.assertIn("FH", kept)

    def test_priority_hard_fh_wc(self) -> None:
        kept, dropped = priority_kept({"TC": 1, "BB": 2, "FH": 8, "WC": 8})
        self.assertIn("WC", kept)
        self.assertIn("FH", dropped)

    def test_analyze_negligible(self) -> None:
        t_stars = {
            "2022-23": {"TC": 1, "BB": 2, "FH": 3, "WC": 4},
            "2023-24": {"TC": 5, "BB": 6, "FH": 7, "WC": 8},
            "2024-25": {"TC": 9, "BB": 10, "FH": 11, "WC": 12},
            "2025-26": {"TC": 13, "BB": 14, "FH": 15, "WC": 16},
        }
        r = analyze(t_stars)
        self.assertEqual(r["verdict"], "NEGLIGIBLE")
        self.assertEqual(r["branch"], "DO_NOT_OPEN_E051A")

    def test_analyze_conflicts(self) -> None:
        t_stars = {
            "2022-23": {"TC": 10, "BB": 10, "FH": 3, "WC": 4},
            "2023-24": {"TC": 5, "BB": 6, "FH": 7, "WC": 8},
            "2024-25": {"TC": 9, "BB": 10, "FH": 11, "WC": 12},
            "2025-26": {"TC": 13, "BB": 14, "FH": 15, "WC": 16},
        }
        r = analyze(t_stars)
        self.assertEqual(r["verdict"], "CONFLICTS_PRESENT")
        self.assertEqual(r["seasons_with_collision"], 1)


if __name__ == "__main__":
    unittest.main()
