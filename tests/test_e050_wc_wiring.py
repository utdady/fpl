"""E050-A: product policy must reproduce historical evaluator t*/U_WC."""
from __future__ import annotations

import csv
import unittest
from pathlib import Path

from engine.e050_wc_policy import (
    GATE_NOTE,
    INDEPENDENCE,
    WcRecommendation,
    WcRow,
    format_recommendation,
    recommend_historical,
    select_t_star,
)
from tests.historical_data import unavailable_reason

ROOT = Path(__file__).resolve().parents[1]
SEASON_CSV = ROOT / "records" / "historical" / "e050_wildcard_roi_season.csv"


class TestE050WcWiring(unittest.TestCase):
    def test_select_t_star_tie_break_lowest_gw(self) -> None:
        rows = [
            WcRow(3, 10.0, 5, (1,), False, ""),
            WcRow(1, 10.0, 5, (2,), False, ""),
            WcRow(2, 8.0, 5, (3,), False, ""),
        ]
        best = select_t_star(rows)
        self.assertEqual(best.gw, 1)

    def test_format_states_independence_and_asterisks(self) -> None:
        text = format_recommendation(
            WcRecommendation(
                policy_id="E050-A",
                t_star=1,
                u_wc=1.0,
                n_tau=2,
                blank_ids=(),
                blank_names=(),
                held_ids=(1, 2, 3),
                held_freeze_gw=1,
                claim="c",
                rows=(),
                live_semantics="L",
            )
        )
        self.assertIn("not a combined chip calendar", text)
        self.assertIn("Free Hit", text)
        self.assertIn("REPLACE", text)
        self.assertIn(INDEPENDENCE, text)
        self.assertIn(GATE_NOTE, text)
        self.assertIn("2022-23", text)
        self.assertIn("2024-25", text)

    def test_season_csv_t_star_present(self) -> None:
        self.assertTrue(SEASON_CSV.exists())
        with SEASON_CSV.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 4)
        for r in rows:
            self.assertTrue(int(r["t_star"]) >= 1)
            self.assertIn(r["e024_gate"], {"FAIL", "PASS"})

    def test_recommend_historical_one_season_matches_csv(self) -> None:
        """Full as-of-t recompute for one season (slow).

        Skip only when optional Vaastav/GW records are explicitly missing.
        """
        self.assertTrue(SEASON_CSV.exists(), "missing E050 season CSV")
        with SEASON_CSV.open(encoding="utf-8") as f:
            season_rows = {r["season"]: r for r in csv.DictReader(f)}
        season = "2024-25"
        self.assertIn(season, season_rows, f"{season} missing from season CSV")
        reason = unavailable_reason(season)
        if reason:
            self.skipTest(reason)
        rec = recommend_historical(season)
        expected = season_rows[season]
        self.assertEqual(rec.t_star, int(expected["t_star"]))
        self.assertAlmostEqual(rec.u_wc, float(expected["u_wc_star"]), places=1)


if __name__ == "__main__":
    unittest.main()
