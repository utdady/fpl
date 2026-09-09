"""Certificate bridge: Python emit/verify mirrors formal/FPL/Certificate.lean."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from engine.certificate import (
    RULES_VERSION_DEFAULT,
    build_certificate,
    emit_lean_example,
    load_certificate,
    verify_certificate,
    write_certificate,
)
from engine.harness import default_scoring, default_squad
from engine.models import Event, Player, Snapshot, SquadSolution, Team


def _player(pid: int, cost: int, pos: str, team: int) -> Player:
    et = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}[pos]
    return Player(
        id=pid,
        web_name=f"P{pid}",
        first_name="",
        second_name="",
        element_type=et,
        position=pos,
        team_id=team,
        now_cost=cost,
        status="a",
        can_select=True,
        news="",
        chance_this=100,
        chance_next=100,
        minutes=0,
        starts=0,
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
        games_hint=0,
        pen_order=None,
        corners_order=None,
        selected_by=0.0,
        ep_next=None,
    )


def _toy_players() -> list[Player]:
    slots = [
        (1, 45, "GKP", 1),
        (2, 40, "GKP", 2),
        (3, 50, "DEF", 1),
        (4, 45, "DEF", 2),
        (5, 45, "DEF", 3),
        (6, 40, "DEF", 4),
        (7, 40, "DEF", 5),
        (8, 70, "MID", 1),
        (9, 65, "MID", 2),
        (10, 60, "MID", 3),
        (11, 55, "MID", 4),
        (12, 50, "MID", 5),
        (13, 80, "FWD", 6),
        (14, 70, "FWD", 7),
        (15, 55, "FWD", 8),
    ]
    return [_player(*s) for s in slots]


def _toy_snapshot() -> Snapshot:
    players = _toy_players()
    return Snapshot(
        as_of=datetime(2026, 8, 18, tzinfo=timezone.utc),
        season_label="2026-27",
        scoring=default_scoring(),
        squad=default_squad(),
        teams={i: Team(i, f"T{i}", f"T{i}", 3, 3) for i in range(1, 9)},
        events=[Event(1, "GW1", None, False, True, False)],
        fixtures=[],
        players=players,
    )


def _toy_solution() -> SquadSolution:
    players = _toy_players()
    by_id = {p.id: p for p in players}
    xi_ids = [1, 3, 4, 5, 8, 9, 10, 11, 13, 14, 15]
    xi = [by_id[i] for i in xi_ids]
    bench = [p for p in players if p.id not in set(xi_ids)]
    return SquadSolution(
        players=players,
        xi=xi,
        bench=bench,
        captain=by_id[8],
        vice=by_id[13],
        cost=810,
        bank=190,
        horizon_utility=12.345,
        next_xi_mu=0.0,
        next_xi_utility=0.0,
        alternatives=[],
        strategy="balanced",
        horizon_gws=[1],
    )


class TestCertificate(unittest.TestCase):
    def test_toy_legal(self) -> None:
        cert = build_certificate(_toy_snapshot(), _toy_solution())
        self.assertEqual(cert.rules_version, RULES_VERSION_DEFAULT)
        self.assertEqual(verify_certificate(cert), [])
        self.assertEqual(cert.claimed_cost, 810)
        self.assertEqual(cert.claimed_objective_milli, 12345)

    def test_captain_not_in_xi_fails(self) -> None:
        cert = build_certificate(_toy_snapshot(), _toy_solution())
        bad = cert.to_json()
        bad["captain_id"] = 2
        fails = verify_certificate(bad)
        self.assertTrue(any("captain" in f for f in fails))

    def test_budget_fail(self) -> None:
        cert = build_certificate(_toy_snapshot(), _toy_solution())
        bad = cert.to_json()
        bad["players"][0]["cost"] = 5000
        bad["claimed_cost"] = sum(p["cost"] for p in bad["players"])
        fails = verify_certificate(bad)
        self.assertTrue(any("budget" in f for f in fails))

    def test_roundtrip_json(self) -> None:
        cert = build_certificate(_toy_snapshot(), _toy_solution())
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cert.json"
            write_certificate(cert, path)
            loaded = load_certificate(path)
            self.assertEqual(verify_certificate(loaded), [])
            lean_path = Path(td) / "cert.lean"
            emit_lean_example(cert, lean_path)
            text = lean_path.read_text(encoding="utf-8")
            self.assertIn("verifyCertificate cert = true", text)
            self.assertIn(RULES_VERSION_DEFAULT, text)


if __name__ == "__main__":
    unittest.main()
