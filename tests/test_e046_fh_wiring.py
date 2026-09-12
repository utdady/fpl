"""E046-A: product policy must reproduce historical evaluator t*/U_FH."""
from __future__ import annotations

import csv
import unittest
from pathlib import Path

from engine.e046_fh_policy import (
    FhRecommendation,
    FhRow,
    INDEPENDENCE,
    format_recommendation,
    recommend_historical,
    select_t_star,
)
from tests.historical_data import unavailable_reason
from tests.slow import skip_unless_slow

ROOT = Path(__file__).resolve().parents[1]
SEASON_CSV = ROOT / "records" / "historical" / "e046_free_hit_roi_season.csv"
GW_CSV = ROOT / "records" / "historical" / "e046_free_hit_roi_gw.csv"


class TestE046FhWiring(unittest.TestCase):
    def test_select_t_star_tie_break_lowest_gw(self) -> None:
        rows = [
            FhRow(3, 10.0, 5.0, 5.0, False, ""),
            FhRow(1, 9.0, 4.0, 5.0, False, ""),
            FhRow(2, 8.0, 5.0, 3.0, False, ""),
        ]
        best = select_t_star(rows)
        self.assertEqual(best.gw, 1)

    def test_format_states_independence(self) -> None:
        text = format_recommendation(
            FhRecommendation(
                policy_id="E046-A",
                t_star=1,
                u_fh=1.0,
                u_blank=2.0,
                u_held=1.0,
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
        self.assertIn("Triple Captain", text)
        self.assertIn("Bench Boost", text)
        self.assertIn(INDEPENDENCE, text)

    def test_season_csv_matches_shared_policy(self) -> None:
        self.assertTrue(SEASON_CSV.exists())
        self.assertTrue(GW_CSV.exists())
        with SEASON_CSV.open(encoding="utf-8") as f:
            season_rows = {r["season"]: r for r in csv.DictReader(f)}
        with GW_CSV.open(encoding="utf-8") as f:
            gw_rows = list(csv.DictReader(f))
        by_season: dict[str, list[FhRow]] = {}
        for r in gw_rows:
            season = r["season"]
            excluded = int(r["excluded"]) == 1
            by_season.setdefault(season, []).append(
                FhRow(
                    gw=int(r["gw"]),
                    u_blank=float(r["u_blank"] or 0),
                    u_held=float(r["u_held"] or 0),
                    u_fh=float(r["u_fh"] or 0),
                    excluded=excluded,
                    exclude_reason=r.get("exclude_reason") or "",
                )
            )
        # GW artifact may be a single-season export; assert every season present.
        self.assertTrue(by_season, "E046 GW CSV empty")
        for season, rows in by_season.items():
            self.assertIn(season, season_rows)
            srow = season_rows[season]
            if int(float(srow["n_gw"])) == 0:
                continue
            best = select_t_star(rows)
            self.assertEqual(best.gw, int(srow["t_star"]), f"{season}: t* mismatch")
            self.assertAlmostEqual(
                best.u_fh,
                float(srow["u_fh_star"]),
                places=3,
                msg=f"{season}: U_FH mismatch",
            )

    @skip_unless_slow()
    def test_recommend_historical_one_season_matches_csv(self) -> None:
        """Full as-of-t recompute for one season (slow; FPL_RUN_SLOW=1).

        Skip only when optional Vaastav/GW records are explicitly missing.
        """
        self.assertTrue(SEASON_CSV.exists(), "missing E046 season CSV")
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
        self.assertAlmostEqual(rec.u_fh, float(expected["u_fh_star"]), places=2)


if __name__ == "__main__":
    unittest.main()
