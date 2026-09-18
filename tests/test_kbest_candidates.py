"""PRODUCT k-best: no-good cuts exclude the exact 15, same objective."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from engine.candidates import solve_k_best
from engine.harness import default_scoring, default_squad
from engine.models import Event, Player, PlayerProjection, Snapshot, Team
from engine.optimize import solve_squad


def _player(pid: int, pos: str, team_id: int, cost: int) -> Player:
    etype = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}[pos]
    return Player(
        id=pid,
        web_name=f"{pos}{pid}",
        first_name="",
        second_name="",
        element_type=etype,
        position=pos,
        team_id=team_id,
        now_cost=cost,
        status="a",
        can_select=True,
        news="",
        chance_this=None,
        chance_next=None,
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
        selected_by=0.0,
        ep_next=None,
    )


def _proj(player: Player, util: float) -> PlayerProjection:
    return PlayerProjection(
        player=player,
        by_gw={},
        horizon_mu=util,
        horizon_sigma=1.0,
        horizon_utility=util,
        next_mu=util,
        next_sigma=1.0,
        next_p_start=0.90,
        next_p_60=0.80,
        next_p_10=0.20,
        next_utility=util,
    )


def _toy() -> tuple[Snapshot, list[PlayerProjection]]:
    """Enough legal players that S1 is unique and S2 exists after a cut."""
    players: list[Player] = []
    projs: list[PlayerProjection] = []
    pid = 1
    # Distinct utilities so CBC has a unique optimum, then a clear second 15.
    util = 20.0
    for pos, n in (("GKP", 4), ("DEF", 8), ("MID", 8), ("FWD", 5)):
        for i in range(n):
            team_id = 1 + (pid % 8)
            p = _player(pid, pos, team_id, cost=50)
            players.append(p)
            projs.append(_proj(p, util))
            util -= 0.25
            pid += 1
    teams = {
        tid: Team(id=tid, name=f"T{tid}", short_name=f"T{tid}", strength_home=3, strength_away=3)
        for tid in range(1, 9)
    }
    events = [
        Event(id=1, name="GW1", deadline=None, is_current=False, is_next=True, finished=False)
    ]
    snap = Snapshot(
        as_of=datetime.now(timezone.utc),
        season_label="toy",
        scoring=default_scoring(),
        squad=default_squad(),
        teams=teams,
        events=events,
        fixtures=[],
        players=players,
    )
    return snap, projs


class TestKBestCuts(unittest.TestCase):
    def test_exclude_squads_yields_different_legal_15(self) -> None:
        snap, projs = _toy()
        s1 = solve_squad(snap, projs, strategy="balanced", objective="horizon")
        ids1 = {p.id for p in s1.players}
        self.assertEqual(len(ids1), 15)

        s2 = solve_squad(
            snap,
            projs,
            strategy="balanced",
            objective="horizon",
            exclude_squads=[ids1],
        )
        ids2 = {p.id for p in s2.players}
        self.assertEqual(len(ids2), 15)
        self.assertNotEqual(ids1, ids2)
        self.assertEqual(len(s2.xi), 11)

    def test_k_best_pool_unique_and_s1_does_not_reappear(self) -> None:
        snap, projs = _toy()
        pool = solve_k_best(snap, projs, strategy="balanced", k=3, objective="horizon")
        self.assertGreaterEqual(len(pool), 2)
        seen: list[frozenset[int]] = []
        for cand in pool:
            ids = cand.diagnostics.ids
            self.assertEqual(len(ids), 15)
            self.assertNotIn(ids, seen)
            seen.append(ids)
        self.assertEqual(pool[0].diagnostics.distance, 0)
        self.assertGreater(pool[1].diagnostics.distance, 0)


if __name__ == "__main__":
    unittest.main()
