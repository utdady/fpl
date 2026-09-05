"""E040-A: product policy must reproduce historical evaluator t*/captain."""
from __future__ import annotations

import csv
import unittest
from pathlib import Path

from engine.e040_tc_policy import CaptRow, recommend_historical, select_t_star
from tests.historical_data import unavailable_reason

ROOT = Path(__file__).resolve().parents[1]
SEASON_CSV = ROOT / "records" / "historical" / "e040_triple_captain_roi_season.csv"
GW_CSV = ROOT / "records" / "historical" / "e040_triple_captain_roi_gw.csv"


class TestE040TcPolicy(unittest.TestCase):
    def test_select_t_star_tie_break_lowest_gw(self) -> None:
        rows = [
            CaptRow(3, 1, "A", 5.0, "as_of_t"),
            CaptRow(1, 2, "B", 5.0, "as_of_t"),
            CaptRow(2, 3, "C", 4.0, "as_of_t"),
        ]
        best = select_t_star(rows)
        self.assertEqual(best.gw, 1)
        self.assertEqual(best.captain_name, "B")

    def test_format_states_independence_from_bb(self) -> None:
        from engine.e040_tc_policy import INDEPENDENCE, TCRecommendation, format_recommendation

        text = format_recommendation(
            TCRecommendation(
                policy_id="E040-A",
                t_star=1,
                captain_id=1,
                captain_name="X",
                u_capt=1.0,
                claim="c",
                rows=(),
                live_semantics="L",
            )
        )
        self.assertIn("not a combined chip calendar", text)
        self.assertIn("Bench Boost", text)
        self.assertEqual(INDEPENDENCE in text, True)

    def test_season_csv_matches_shared_policy(self) -> None:
        """Recompute C from frozen artifacts' GW U_capt rows via select_t_star."""
        self.assertTrue(SEASON_CSV.exists(), "missing E040 season CSV")
        self.assertTrue(GW_CSV.exists(), "missing E040 GW CSV")
        with SEASON_CSV.open(encoding="utf-8") as f:
            season_rows = list(csv.DictReader(f))
        with GW_CSV.open(encoding="utf-8") as f:
            gw_rows = list(csv.DictReader(f))
        by_season: dict[str, list[CaptRow]] = {}
        for r in gw_rows:
            season = r["season"]
            by_season.setdefault(season, []).append(
                CaptRow(
                    gw=int(r["gw"]),
                    captain_id=int(r["captain_id"]),
                    captain_name=r["captain_name"],
                    u_capt=float(r["u_capt"]),
                    source="as_of_t",
                )
            )
        for srow in season_rows:
            season = srow["season"]
            if int(float(srow["n_gw"])) == 0:
                continue
            best = select_t_star(by_season[season])
            self.assertEqual(
                best.gw,
                int(srow["t_star"]),
                f"{season}: t* mismatch",
            )
            self.assertEqual(
                best.captain_id,
                int(srow["captain_c_id"]),
                f"{season}: captain id mismatch",
            )
            self.assertAlmostEqual(
                best.u_capt,
                float(srow["u_capt_star"]),
                places=3,
                msg=f"{season}: U_capt mismatch",
            )

    def test_recommend_historical_one_season_matches_csv(self) -> None:
        """Full as-of-t recompute for one season (slow).

        Skip only when optional Vaastav/GW records are explicitly missing.
        Projection/optimizer regressions must fail, not skip.
        """
        self.assertTrue(SEASON_CSV.exists(), "missing E040 season CSV")
        with SEASON_CSV.open(encoding="utf-8") as f:
            season_rows = {
                r["season"]: r
                for r in csv.DictReader(f)
            }
        season = "2024-25"
        self.assertIn(season, season_rows, f"{season} missing from season CSV")
        reason = unavailable_reason(season)
        if reason:
            self.skipTest(reason)
        rec = recommend_historical(season)
        expected = season_rows[season]
        self.assertEqual(rec.t_star, int(expected["t_star"]))
        self.assertEqual(rec.captain_id, int(expected["captain_c_id"]))
        self.assertAlmostEqual(rec.u_capt, float(expected["u_capt_star"]), places=2)


if __name__ == "__main__":
    unittest.main()
