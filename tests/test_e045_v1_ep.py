"""Unit tests for E045-A ep_next μ blend (no network)."""
from __future__ import annotations

import unittest

from engine.fplcache_ep import blend_mu, EP_LAMBDA
from engine.rates_v1_ep import apply_ep_blend
from engine.models import GWProjection, Player, PlayerProjection


def _player(pid: int = 1, ep_next: float | None = None) -> Player:
    return Player(
        id=pid,
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
        ep_next=ep_next,
    )


def _proj(pid: int, mu: float) -> PlayerProjection:
    p = _player(pid)
    g = GWProjection(pid, 1, 1, mu, 1.0, 0.8, 0.1, 0.7, 0.05, 2.0)
    return PlayerProjection(
        player=p,
        by_gw={1: g},
        horizon_mu=mu,
        horizon_sigma=1.0,
        horizon_utility=mu,
        next_mu=mu,
        next_sigma=1.0,
        next_p_start=0.8,
        next_p_60=0.7,
        next_p_10=0.05,
        next_utility=mu,
    )


class TestV1Ep(unittest.TestCase):
    def test_blend_formula(self) -> None:
        mu1, ok = blend_mu(4.0, 6.0, lam=0.35)
        self.assertTrue(ok)
        self.assertAlmostEqual(mu1, 0.65 * 4.0 + 0.35 * 6.0)
        self.assertEqual(EP_LAMBDA, 0.35)

    def test_identity_missing_ep(self) -> None:
        mu1, ok = blend_mu(4.0, None)
        self.assertFalse(ok)
        self.assertEqual(mu1, 4.0)

    def test_apply_live_ep(self) -> None:
        projs = [_proj(1, 4.0), _proj(2, 5.0)]
        out, diags = apply_ep_blend(
            projs,
            season=None,
            as_of_gw=1,
            strategy="balanced",
            live_ep={1: 8.0},
        )
        self.assertTrue(diags[0].blended)
        self.assertAlmostEqual(out[0].next_mu, 0.65 * 4.0 + 0.35 * 8.0)
        self.assertEqual(out[0].next_sigma, 1.0)  # sigma unchanged
        self.assertFalse(diags[1].blended)
        self.assertEqual(out[1].next_mu, 5.0)

    def test_no_season_no_live_identity(self) -> None:
        projs = [_proj(1, 3.0)]
        out, diags = apply_ep_blend(
            projs, season=None, as_of_gw=1, strategy="balanced", live_ep=None
        )
        self.assertEqual(diags[0].identity_reason, "no_season")
        self.assertEqual(out[0].next_mu, 3.0)


if __name__ == "__main__":
    unittest.main()
