"""Unit tests for E045-A ep_next blend (no network)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine.fplcache_ep import EP_LAMBDA
from engine.models import GWProjection, Player, PlayerProjection
from engine.rates_v1_ep import apply_ep_blend


def _player(**kwargs) -> Player:
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


def _proj(player: Player, mu: float, sigma: float = 2.0, p10: float = 0.1) -> PlayerProjection:
    gw = GWProjection(
        player_id=player.id,
        event_id=1,
        n_fixtures=1,
        mu=mu,
        sigma=sigma,
        p_start=0.8,
        p_sub=0.1,
        p_60=0.7,
        p_10_plus=p10,
        p90=0.5,
    )
    return PlayerProjection(
        player=player,
        by_gw={1: gw},
        horizon_mu=mu,
        horizon_sigma=sigma,
        horizon_utility=mu,
        next_mu=mu,
        next_sigma=sigma,
        next_p_start=0.8,
        next_p_60=0.7,
        next_p_10=p10,
        next_utility=mu,
    )


class TestRatesV1Ep(unittest.TestCase):
    def test_blend_formula(self) -> None:
        p = _player(id=10)
        mu0 = 4.0
        e = 6.0
        overlay = {10: e}
        with mock.patch("engine.rates_v1_ep.load_ep_next", return_value=overlay):
            out, diags = apply_ep_blend(
                [_proj(p, mu0)],
                season="2024-25",
                as_of_gw=5,
                strategy="balanced",
            )
        expected = (1.0 - EP_LAMBDA) * mu0 + EP_LAMBDA * e
        self.assertAlmostEqual(out[0].next_mu, expected)
        self.assertAlmostEqual(out[0].by_gw[1].mu, expected)
        self.assertAlmostEqual(out[0].next_sigma, 2.0)
        self.assertAlmostEqual(out[0].next_p_10, 0.1)
        self.assertTrue(diags[0].blended)
        self.assertEqual(diags[0].identity_reason, "")

    def test_missing_overlay_identity(self) -> None:
        p = _player()
        with mock.patch("engine.rates_v1_ep.load_ep_next", return_value=None):
            out, diags = apply_ep_blend(
                [_proj(p, 5.0)],
                season="2024-25",
                as_of_gw=1,
                strategy="balanced",
            )
        self.assertAlmostEqual(out[0].next_mu, 5.0)
        self.assertFalse(diags[0].blended)
        self.assertEqual(diags[0].identity_reason, "no_overlay")

    def test_join_miss_identity(self) -> None:
        p = _player(id=99)
        with mock.patch("engine.rates_v1_ep.load_ep_next", return_value={1: 3.0}):
            out, diags = apply_ep_blend(
                [_proj(p, 5.0)],
                season="2024-25",
                as_of_gw=1,
                strategy="balanced",
            )
        self.assertAlmostEqual(out[0].next_mu, 5.0)
        self.assertFalse(diags[0].blended)
        self.assertEqual(diags[0].identity_reason, "missing_ep")

    def test_live_ep_without_season(self) -> None:
        p = _player(id=3)
        out, diags = apply_ep_blend(
            [_proj(p, 2.0)],
            season=None,
            as_of_gw=1,
            strategy="balanced",
            live_ep={3: 5.0},
        )
        expected = (1.0 - EP_LAMBDA) * 2.0 + EP_LAMBDA * 5.0
        self.assertAlmostEqual(out[0].next_mu, expected)
        self.assertTrue(diags[0].blended)

    def test_player_ep_next_not_required(self) -> None:
        """Blend must use overlay, not Player.ep_next (minutes path stays clean)."""
        p = _player(id=1, ep_next=None)
        with mock.patch("engine.rates_v1_ep.load_ep_next", return_value={1: 4.5}):
            out, _ = apply_ep_blend(
                [_proj(p, 3.0)],
                season="2023-24",
                as_of_gw=10,
                strategy="balanced",
            )
        self.assertIsNone(out[0].player.ep_next)
        self.assertAlmostEqual(
            out[0].next_mu,
            (1.0 - EP_LAMBDA) * 3.0 + EP_LAMBDA * 4.5,
        )

    def test_slim_load_roundtrip(self) -> None:
        from engine import fplcache_ep as mod

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            slim = root / "2022-23"
            slim.mkdir()
            payload = {
                "season": "2022-23",
                "gw": 1,
                "by_id": {"42": 3.2, "7": None},
            }
            (slim / "gw01.json").write_text(json.dumps(payload), encoding="utf-8")
            with mock.patch.object(mod, "SLIM_DIR", root):
                loaded = mod.load_ep_next("2022-23", 1)
            self.assertEqual(loaded, {42: 3.2})
            self.assertIsNone(mod.load_ep_next("2022-23", 99))


if __name__ == "__main__":
    unittest.main()
