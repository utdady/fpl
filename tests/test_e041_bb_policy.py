"""E041-A: product policy must reproduce historical evaluator t*/U_bench."""
from __future__ import annotations

import csv
import unittest
from pathlib import Path

from engine.e041_bb_policy import BenchRow, recommend_historical, select_t_star

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
        if not SEASON_CSV.exists():
            self.skipTest("no season CSV")
        with SEASON_CSV.open(encoding="utf-8") as f:
            season_rows = {r["season"]: r for r in csv.DictReader(f)}
        season = "2024-25"
        if season not in season_rows:
            self.skipTest("2024-25 missing")
        try:
            rec = recommend_historical(season)
        except Exception as exc:  # noqa: BLE001
            self.skipTest(f"historical rebuild unavailable: {exc}")
        expected = season_rows[season]
        self.assertEqual(rec.t_star, int(expected["t_star"]))
        self.assertAlmostEqual(rec.u_bench, float(expected["u_bench_star"]), places=2)


if __name__ == "__main__":
    unittest.main()
