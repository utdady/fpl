"""Synthetic tests for engine.suggest (roll, k=1 upgrade, optional hit)."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from engine.models import (
    Event,
    Player,
    PlayerProjection,
    ScoringRules,
    Snapshot,
    SquadRules,
    Team,
)
from engine.suggest import SquadState, suggest_transfers

POS = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}


def _player(pid: int, name: str, pos: str, team: int, cost: int) -> Player:
    return Player(
        id=pid,
        web_name=name,
        first_name=name,
        second_name="",
        element_type=POS[pos],
        position=pos,
        team_id=team,
        now_cost=cost,
        status="a",
        can_select=True,
        news="",
        chance_this=100,
        chance_next=100,
        minutes=90,
        starts=1,
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
        games_hint=1,
        pen_order=None,
        corners_order=None,
        selected_by=1.0,
        ep_next=0.0,
    )


def _proj(player: Player, mu: float) -> PlayerProjection:
    return PlayerProjection(
        player=player,
        by_gw={},
        horizon_mu=mu,
        horizon_sigma=0.0,
        horizon_utility=mu,
        next_mu=mu,
        next_sigma=0.0,
        next_p_start=1.0,
        next_p_60=1.0,
        next_p_10=0.0,
        next_utility=mu,
    )


def _snapshot(players: list[Player]) -> Snapshot:
    teams = {
        i: Team(id=i, name=f"T{i}", short_name=f"T{i}", strength_home=3, strength_away=3)
        for i in range(1, 12)
    }
    return Snapshot(
        as_of=datetime(2026, 8, 1, tzinfo=timezone.utc),
        season_label="2026-27",
        scoring=ScoringRules(
            long_play=2,
            short_play=1,
            goals_scored={"GKP": 6, "DEF": 6, "MID": 5, "FWD": 4},
            assists=3,
            clean_sheets={"GKP": 4, "DEF": 4, "MID": 1, "FWD": 0},
            defensive_contribution={"GKP": 0, "DEF": 2, "MID": 2, "FWD": 2},
            goals_conceded={"GKP": -1, "DEF": -1, "MID": 0, "FWD": 0},
            saves=1,
            yellow_cards=-1,
            red_cards=-3,
            bonus=1,
            dc_threshold={"GKP": 99, "DEF": 10, "MID": 12, "FWD": 12},
        ),
        squad=SquadRules(
            squad_size=15,
            squad_play=11,
            budget=1000,
            team_limit=3,
            squad_select={"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3},
            min_play={"GKP": 1, "DEF": 3, "MID": 2, "FWD": 1},
            max_play={"GKP": 1, "DEF": 5, "MID": 5, "FWD": 3},
        ),
        teams=teams,
        events=[
            Event(
                id=3,
                name="Gameweek 3",
                deadline=None,
                is_current=False,
                is_next=True,
                finished=False,
            )
        ],
        fixtures=[],
        players=players,
    )


def _owned_and_pool() -> tuple[list[Player], Player, list[PlayerProjection], SquadState]:
    """15-man squad plus one same-position FWD upgrade that fits the bank."""
    owned: list[Player] = []
    pid = 1
    # 2 GKP, teams 1–2
    for i in range(2):
        owned.append(_player(pid, f"GK{i}", "GKP", 1 + i, 40))
        pid += 1
    # 5 DEF, teams 1–5
    for i in range(5):
        owned.append(_player(pid, f"DF{i}", "DEF", 1 + i, 45))
        pid += 1
    # 5 MID, teams 6–10
    for i in range(5):
        owned.append(_player(pid, f"MF{i}", "MID", 6 + i, 50))
        pid += 1
    # 3 FWD: two decent, one weak (id 15)
    owned.append(_player(13, "FW0", "FWD", 3, 70))
    owned.append(_player(14, "FW1", "FWD", 4, 70))
    weak = _player(15, "Weak", "FWD", 5, 70)
    owned.append(weak)
    upgrade = _player(99, "Star", "FWD", 11, 75)
    players = owned + [upgrade]
    projs = []
    for p in owned:
        if p.id == 15:
            projs.append(_proj(p, 2.0))
        elif p.position in {"GKP"} and p.id == 2:
            projs.append(_proj(p, 1.0))  # bench keeper
        elif p.position == "DEF" and p.id == 7:
            projs.append(_proj(p, 1.0))  # bench def
        elif p.position == "MID" and p.id == 12:
            projs.append(_proj(p, 1.0))  # bench mid
        else:
            projs.append(_proj(p, 5.0))
    projs.append(_proj(upgrade, 10.0))
    state = SquadState(
        owned_ids=[p.id for p in owned],
        selling={p.id: p.now_cost for p in owned},
        bank=10,
        ft=1,
        hit_cost=4,
        value=1000,
        wc_active=False,
    )
    return owned, upgrade, projs, state


class TestSuggestTransfers(unittest.TestCase):
    def test_roll_is_k0_no_moves(self) -> None:
        _owned, _upgrade, projs, state = _owned_and_pool()
        snap = _snapshot([p.player for p in projs])
        result = suggest_transfers(snap, projs, state, allow_hit=False, top_n=1)
        roll = next(p for p in result.plans if p.k == 0)
        self.assertEqual(roll.moves, [])
        self.assertEqual(roll.hit, 0)
        self.assertEqual(roll.delta_mu, 0.0)
        self.assertAlmostEqual(result.roll_mu, roll.next_xi_mu)

    def test_k1_picks_obvious_upgrade(self) -> None:
        _owned, upgrade, projs, state = _owned_and_pool()
        snap = _snapshot([p.player for p in projs])
        result = suggest_transfers(snap, projs, state, allow_hit=False, top_n=1)
        k1 = [p for p in result.plans if p.k == 1]
        self.assertTrue(k1, "expected a 1-transfer plan")
        ins = {m.in_id for p in k1 for m in p.moves}
        self.assertIn(upgrade.id, ins)
        outs = {m.out_id for p in k1 for m in p.moves}
        self.assertIn(15, outs)
        self.assertEqual(k1[0].hit, 0)
        self.assertGreater(k1[0].delta_mu, 0)

    def test_hit_plan_deducts_four(self) -> None:
        _owned, upgrade, projs, state = _owned_and_pool()
        state.ft = 0
        snap = _snapshot([p.player for p in projs])
        result = suggest_transfers(snap, projs, state, allow_hit=True, top_n=1)
        k1 = [p for p in result.plans if p.k == 1]
        self.assertTrue(k1, "expected a hit plan")
        plan = k1[0]
        self.assertEqual(plan.hit, 4)
        self.assertAlmostEqual(plan.score, plan.next_xi_mu - 4)
        self.assertIn(upgrade.id, {m.in_id for m in plan.moves})

    def test_no_hit_when_not_allowed_and_ft_zero(self) -> None:
        _owned, _upgrade, projs, state = _owned_and_pool()
        state.ft = 0
        snap = _snapshot([p.player for p in projs])
        result = suggest_transfers(snap, projs, state, allow_hit=False, top_n=1)
        self.assertTrue(all(p.k == 0 for p in result.plans))


if __name__ == "__main__":
    unittest.main()
