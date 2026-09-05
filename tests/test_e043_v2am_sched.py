"""Unit tests for E043-A lagged short-turnaround (no Vaastav required)."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from engine.minutes_v2am_sched import (
    GAP_TRIGGER_DAYS,
    INCUMBENT_MINUTES,
    SHORT_TURN_CAP,
    apply_sched_blend,
)


def _p(pid, team_id, pos="MID", minutes=900, name="X"):
    return SimpleNamespace(
        id=pid,
        team_id=team_id,
        position=pos,
        web_name=name,
        minutes=minutes,
        status="a",
        can_select=True,
        chance_this=None,
        chance_next=None,
    )


class TestV2amSched(unittest.TestCase):
    def test_trigger_caps_incumbent(self) -> None:
        players = [_p(1, 10, minutes=900)]
        b0 = {1: 0.82}
        gaps = {10: 4.0}
        b1, diags = apply_sched_blend(
            players, b0, gaps, clubs_in_t={10}, league_bgw=False, as_of_gw=10
        )
        self.assertEqual(b1[1], SHORT_TURN_CAP)
        self.assertTrue(diags[0].trigger)
        self.assertTrue(diags[0].eligible)
        self.assertLess(4.0, GAP_TRIGGER_DAYS)

    def test_no_trigger_keeps_b0(self) -> None:
        players = [_p(1, 10, minutes=900)]
        b0 = {1: 0.82}
        gaps = {10: 6.0}
        b1, diags = apply_sched_blend(
            players, b0, gaps, clubs_in_t={10}, league_bgw=False, as_of_gw=10
        )
        self.assertEqual(b1[1], 0.82)
        self.assertFalse(diags[0].trigger)

    def test_gkp_identity(self) -> None:
        players = [_p(1, 10, pos="GKP", minutes=2000)]
        b0 = {1: 0.85}
        b1, diags = apply_sched_blend(
            players, b0, {10: 3.0}, clubs_in_t={10}, league_bgw=False, as_of_gw=10
        )
        self.assertEqual(b1[1], 0.85)
        self.assertEqual(diags[0].identity_reason, "gkp")

    def test_not_incumbent(self) -> None:
        players = [_p(1, 10, minutes=INCUMBENT_MINUTES - 1)]
        b0 = {1: 0.50}
        b1, diags = apply_sched_blend(
            players, b0, {10: 3.0}, clubs_in_t={10}, league_bgw=False, as_of_gw=10
        )
        self.assertEqual(b1[1], 0.50)
        self.assertEqual(diags[0].identity_reason, "not_incumbent")

    def test_club_blank_identity(self) -> None:
        players = [_p(1, 10, minutes=900)]
        b0 = {1: 0.70}
        b1, diags = apply_sched_blend(
            players, b0, {10: 3.0}, clubs_in_t=set(), league_bgw=False, as_of_gw=10
        )
        self.assertEqual(diags[0].identity_reason, "club_blank")
        self.assertEqual(b1[1], 0.70)

    def test_insufficient_history(self) -> None:
        players = [_p(1, 10, minutes=900)]
        b0 = {1: 0.70}
        b1, diags = apply_sched_blend(
            players, b0, {10: None}, clubs_in_t={10}, league_bgw=False, as_of_gw=10
        )
        self.assertEqual(diags[0].identity_reason, "insufficient_history")
        self.assertEqual(b1[1], 0.70)


if __name__ == "__main__":
    unittest.main()
