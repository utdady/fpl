"""Unit tests for E042-A share blend (no Vaastav required)."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from engine.minutes_struct import MAX_BASE
from engine.minutes_v2am_share import B1_FLOOR, LAMBDA, apply_share_blend


def _p(pid, team_id, pos="MID", name="X"):
    return SimpleNamespace(
        id=pid,
        team_id=team_id,
        position=pos,
        web_name=name,
        status="a",
        can_select=True,
        chance_this=None,
        chance_next=None,
    )


class TestV2amShare(unittest.TestCase):
    def test_blend_formula(self) -> None:
        players = [_p(1, 1, name="A"), _p(2, 1, name="B")]
        b0 = {1: 0.60, 2: 0.40}
        club = {1: 270, 2: 90}
        n_gws = {1: 4, 2: 4}
        b1, diags = apply_share_blend(players, b0, club, n_gws, as_of_gw=10)
        s1 = 270 / 360
        expected = (1 - LAMBDA) * 0.60 + LAMBDA * MAX_BASE * s1
        expected = min(MAX_BASE, max(B1_FLOOR, expected))
        self.assertAlmostEqual(b1[1], expected, places=6)
        self.assertTrue(diags[0].eligible or diags[1].eligible)
        by_id = {d.player_id: d for d in diags}
        self.assertTrue(by_id[1].eligible)
        self.assertAlmostEqual(by_id[1].share, s1, places=6)

    def test_identity_zero_denom(self) -> None:
        players = [_p(1, 1), _p(2, 1)]
        b0 = {1: 0.50, 2: 0.50}
        b1, diags = apply_share_blend(
            players, b0, {1: 0, 2: 0}, {1: 0, 2: 0}, as_of_gw=10
        )
        self.assertEqual(b1[1], 0.50)
        self.assertEqual(b1[2], 0.50)
        self.assertTrue(all(d.identity_reason == "zero_denom" for d in diags))

    def test_identity_no_club_gws(self) -> None:
        players = [_p(1, 1), _p(2, 1)]
        b0 = {1: 0.70, 2: 0.30}
        # Player 1 has group minutes via peer but 0 GWs on club → identity for p1
        club = {1: 0, 2: 200}
        n_gws = {1: 0, 2: 3}
        b1, diags = apply_share_blend(players, b0, club, n_gws, as_of_gw=10)
        by_id = {d.player_id: d for d in diags}
        self.assertEqual(b1[1], 0.70)
        self.assertEqual(by_id[1].identity_reason, "no_club_gws")
        self.assertTrue(by_id[2].eligible)

    def test_identity_gw1(self) -> None:
        players = [_p(1, 1), _p(2, 1)]
        b0 = {1: 0.80, 2: 0.20}
        b1, diags = apply_share_blend(
            players, b0, {1: 90, 2: 90}, {1: 1, 2: 1}, as_of_gw=1
        )
        self.assertEqual(b1[1], 0.80)
        self.assertTrue(all(d.identity_reason == "gw1" for d in diags))


if __name__ == "__main__":
    unittest.main()
