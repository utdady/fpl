"""Unit tests for E046-A Free Hit policy helpers (no network)."""
from __future__ import annotations

import unittest

from engine.e046_fh_policy import (
    FhRow,
    G_STAR,
    INDEPENDENCE,
    MINUTES_VERSION,
    RATES_VERSION,
    effective_g_star,
    select_t_star,
)


class TestE046FhPolicy(unittest.TestCase):
    def test_stack_is_current_production(self) -> None:
        self.assertEqual(MINUTES_VERSION, "v2am_fpla")
        self.assertEqual(RATES_VERSION, "v1")
        self.assertEqual(G_STAR, 20)

    def test_select_t_star_tie_break_lowest_gw(self) -> None:
        rows = [
            FhRow(3, 10.0, 5.0, 5.0, False, ""),
            FhRow(1, 9.0, 4.0, 5.0, False, ""),
            FhRow(2, 8.0, 5.0, 3.0, False, ""),
            FhRow(4, 99.0, 0.0, 99.0, True, "held_n=0"),
        ]
        best = select_t_star(rows)
        self.assertEqual(best.gw, 1)
        self.assertEqual(best.u_fh, 5.0)

    def test_effective_g_star_fallback(self) -> None:
        self.assertEqual(effective_g_star([1, 2, 20, 21]), 20)
        self.assertEqual(effective_g_star([1, 2, 19, 21]), 19)
        self.assertEqual(effective_g_star([21, 22]), 21)
        self.assertIsNone(effective_g_star([]))

    def test_independence_mentions_tc_bb(self) -> None:
        self.assertIn("Triple Captain", INDEPENDENCE)
        self.assertIn("Bench Boost", INDEPENDENCE)
        self.assertIn("not a combined chip calendar", INDEPENDENCE)


if __name__ == "__main__":
    unittest.main()
