"""Unit tests for E048-A _str_sfix remap (no network / Cap)."""
from __future__ import annotations

import unittest

from engine.fixtures import STR_HI, STR_LO, _str, _str_sfix, expected_goals
from engine.models import Team


class TestV1Sfix(unittest.TestCase):
    def test_frozen_endpoints(self) -> None:
        self.assertEqual(STR_LO, 1000)
        self.assertEqual(STR_HI, 1350)

    def test_sfix_examples(self) -> None:
        self.assertEqual(_str_sfix(1000), 2)
        self.assertEqual(_str_sfix(1117), 3)
        self.assertEqual(_str_sfix(1175), 4)
        self.assertEqual(_str_sfix(1350), 5)
        self.assertEqual(_str_sfix(975), 2)   # clamp to LO
        self.assertEqual(_str_sfix(1400), 5)  # clamp to HI

    def test_legacy_scale_identity(self) -> None:
        for b in (2, 3, 4, 5):
            self.assertEqual(_str_sfix(b), b)

    def test_production_str_still_clamps_modern(self) -> None:
        self.assertEqual(_str(1150), 5)
        self.assertEqual(_str(3), 3)

    def test_expected_goals_differs_under_sfix(self) -> None:
        strong = Team(1, "S", "STR", 1350, 1350)
        weak = Team(2, "W", "WEK", 1000, 1000)
        e_ctrl = expected_goals(strong, weak, bucket_fn=_str)
        e_fix = expected_goals(strong, weak, bucket_fn=_str_sfix)
        # Control: both buckets 5 → symmetric-ish; treat: 5 vs 2 → stronger home edge
        self.assertNotEqual(e_ctrl, e_fix)
        self.assertGreater(e_fix[0], e_ctrl[0])


if __name__ == "__main__":
    unittest.main()
