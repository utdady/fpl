"""E041-A: product policy must reproduce historical evaluator t*/U_bench."""
from __future__ import annotations

import csv
import unittest
from pathlib import Path

from engine.e041_bb_policy import BenchRow, recommend_historical, select_t_star
from tests.historical_data import unavailable_reason

ROOT = Path(__file__).resolve().parents[1]
SEASON_CSV = ROOT / "records" / "historical" / "e041_bench_boost_roi_season.csv"
GW_CSV = ROOT / "records" / "historical" / "e041_bench_boost_roi_gw.csv"


class TestE041BbPolicy(unittest.TestCase):
    def test_select_t_star_tie_break_lowest_gw(self) -> None:
        rows = [
            BenchRow(3, 5.0, (1,), ("A",), "as_of_t"),
            BenchRow(1, 5.0, (2,), ("B",), "as_of_t"),
            BenchRow(2, 4.0, (3,), ("C",), "as_of_t"),
        ]
        best = select_t_star(rows)
        self.assertEqual(best.gw, 1)

    def test_format_states_independence_from_tc(self) -> None:
        from engine.e041_bb_policy import BBRecommendation, INDEPENDENCE, format_recommendation

        text = format_recommendation(
            BBRecommendation(
                policy_id="E041-A",
                t_star=1,
                u_bench=1.0,
                bench_ids=(1,),
                bench_names=("X",),
                claim="c",
                rows=(),
                live_semantics="L",
            )
        )
        self.assertIn("not a combined chip calendar", text)
        self.assertIn("Triple Captain", text)
        self.assertIn(INDEPENDENCE, text)

    def test_season_csv_matches_shared_policy(self) -> None:
        self.assertTrue(SEASON_CSV.exists())
        self.assertTrue(GW_CSV.exists())
        with SEASON_CSV.open(encoding="utf-8") as f:
            season_rows = list(csv.DictReader(f))
        with GW_CSV.open(encoding="utf-8") as f:
            gw_rows = list(csv.DictReader(f))
        by_season: dict[str, list[BenchRow]] = {}
        for r in gw_rows:
            season = r["season"]
            ids = tuple(int(x) for x in r["bench_ids"].split("|") if x)
            names = tuple(r["bench_names"].split("|"))
            by_season.setdefault(season, []).append(
                BenchRow(
                    gw=int(r["gw"]),
                    u_bench=float(r["u_bench"]),
                    bench_ids=ids,
                    bench_names=names,
                    source="as_of_t",
                )
            )
        for srow in season_rows:
            if int(float(srow["n_gw"])) == 0:
                continue
            season = srow["season"]
            best = select_t_star(by_season[season])
            self.assertEqual(best.gw, int(srow["t_star"]), f"{season}: t* mismatch")
            self.assertAlmostEqual(
                best.u_bench,
                float(srow["u_bench_star"]),
                places=3,
                msg=f"{season}: U_bench mismatch",
            )

    def test_recommend_historical_one_season_matches_csv(self) -> None:
        """Full as-of-t recompute for one season (slow).

        Skip only when optional Vaastav/GW records are explicitly missing.
        Projection/optimizer regressions must fail, not skip.
        """
        self.assertTrue(SEASON_CSV.exists(), "missing E041 season CSV")
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
        self.assertAlmostEqual(rec.u_bench, float(expected["u_bench_star"]), places=2)


if __name__ == "__main__":
    unittest.main()
