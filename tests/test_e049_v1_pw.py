"""Unit tests for E049-A fixtures=v1_pw piecewise map (no network / Cap)."""
from __future__ import annotations

import unittest

from engine.fixtures import (
    ATK,
    CONCEDE,
    STR_HI,
    STR_LO,
    _str,
    _str_sfix,
    atk_pw,
    concede_pw,
    expected_goals,
    expected_goals_pw,
    pw_lerp,
    raw_to_u,
)
from engine.models import Team


class TestV1Pw(unittest.TestCase):
    def test_frozen_endpoints(self) -> None:
        self.assertEqual(STR_LO, 1000)
        self.assertEqual(STR_HI, 1350)

    def test_raw_to_u_examples(self) -> None:
        self.assertAlmostEqual(raw_to_u(1000), 2.0)
        self.assertAlmostEqual(raw_to_u(1350), 5.0)
        self.assertAlmostEqual(raw_to_u(1175), 3.5)
        self.assertAlmostEqual(raw_to_u(975), 2.0)   # clamp LO
        self.assertAlmostEqual(raw_to_u(1400), 5.0)  # clamp HI
        self.assertAlmostEqual(raw_to_u(None), 3.0)

    def test_legacy_scale_identity(self) -> None:
        for b in (2, 3, 4, 5):
            self.assertAlmostEqual(raw_to_u(b), float(b))
            self.assertAlmostEqual(atk_pw(b), ATK[b])
            self.assertAlmostEqual(concede_pw(b), CONCEDE[b])

    def test_knots_exact(self) -> None:
        for u, y in ((2.0, ATK[2]), (3.0, ATK[3]), (4.0, ATK[4]), (5.0, ATK[5])):
            self.assertAlmostEqual(pw_lerp(u, ((2.0, ATK[2]), (3.0, ATK[3]), (4.0, ATK[4]), (5.0, ATK[5]))), y)
        for u, y in (
            (2.0, CONCEDE[2]),
            (3.0, CONCEDE[3]),
            (4.0, CONCEDE[4]),
            (5.0, CONCEDE[5]),
        ):
            self.assertAlmostEqual(concede_pw(int(u)), y)

    def test_mid_segment_lerp(self) -> None:
        # u=3.5 midway between ATK[3]=1.32 and ATK[4]=1.95
        mid = 0.5 * (ATK[3] + ATK[4])
        self.assertAlmostEqual(atk_pw(1175), mid)
        mid_c = 0.5 * (CONCEDE[3] + CONCEDE[4])
        self.assertAlmostEqual(concede_pw(1175), mid_c)

    def test_production_str_still_clamps_modern(self) -> None:
        self.assertEqual(_str(1150), 5)
        self.assertEqual(_str(3), 3)

    def test_differs_from_discrete_sfix_and_control(self) -> None:
        strong = Team(1, "S", "STR", 1350, 1350)
        mid = Team(2, "M", "MID", 1175, 1175)
        e_ctrl = expected_goals(strong, mid, bucket_fn=_str)
        e_sfix = expected_goals(strong, mid, bucket_fn=_str_sfix)
        e_pw = expected_goals_pw(strong, mid)
        self.assertNotEqual(e_ctrl, e_pw)
        self.assertNotEqual(e_sfix, e_pw)

    def test_legacy_expected_goals_pw_matches_discrete(self) -> None:
        home = Team(1, "H", "HOM", 4, 4)
        away = Team(2, "A", "AWY", 3, 3)
        e_d = expected_goals(home, away, bucket_fn=_str)
        e_pw = expected_goals_pw(home, away)
        self.assertAlmostEqual(e_d[0], e_pw[0])
        self.assertAlmostEqual(e_d[1], e_pw[1])


if __name__ == "__main__":
    unittest.main()
