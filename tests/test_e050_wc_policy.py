"""Unit tests for E050-A Wildcard policy helpers (no network / Cap)."""
from __future__ import annotations

import unittest

from engine.e050_wc_policy import (
    G_STAR,
    INDEPENDENCE,
    MINUTES_VERSION,
    N_WC,
    RATES_VERSION,
    WcRow,
    effective_g_star,
    season_cap_with_replace,
    select_t_star,
)


class TestE050WcPolicy(unittest.TestCase):
    def test_stack_is_current_production(self) -> None:
        self.assertEqual(MINUTES_VERSION, "v2am_fpla")
        self.assertEqual(RATES_VERSION, "v1")
        self.assertEqual(G_STAR, 20)
        self.assertEqual(N_WC, 1)

    def test_select_t_star_tie_break_lowest_gw(self) -> None:
        rows = [
            WcRow(3, 10.0, 5, (1,), False, ""),
            WcRow(1, 10.0, 5, (2,), False, ""),
            WcRow(2, 8.0, 5, (3,), False, ""),
            WcRow(4, 99.0, 1, (4,), True, "blank:x"),
        ]
        best = select_t_star(rows)
        self.assertEqual(best.gw, 1)
        self.assertEqual(best.u_wc, 10.0)

    def test_effective_g_star_fallback(self) -> None:
        self.assertEqual(effective_g_star([1, 2, 20, 21]), 20)
        self.assertEqual(effective_g_star([1, 2, 19, 21]), 19)

    def test_independence_mentions_fh(self) -> None:
        self.assertIn("Free Hit", INDEPENDENCE)
        self.assertIn("not a combined chip calendar", INDEPENDENCE)

    def test_season_cap_replace_semantics(self) -> None:
        included = [1, 2, 3, 4]
        cap_held0 = {1: 10.0, 2: 10.0, 3: 10.0, 4: 10.0}
        cap_blank = {1: 20.0, 2: 20.0, 3: 30.0, 4: 20.0}
        blank_ids = {3: [101, 102]}

        def post_cap(gw: int, ids: list[int]) -> float:
            self.assertEqual(ids, [101, 102])
            return 15.0  # replaced held Cap after chip

        # chip at 3: pre=10+10, chip=30, post=15 → 65
        r = season_cap_with_replace(
            included_gws=included,
            cap_held0=cap_held0,
            cap_blank=cap_blank,
            blank_ids_by_gw=blank_ids,
            chip_gw=3,
            snap_act_cap_fn=post_cap,
        )
        self.assertEqual(r, 65.0)

        # never WC
        r0 = season_cap_with_replace(
            included_gws=included,
            cap_held0=cap_held0,
            cap_blank=cap_blank,
            blank_ids_by_gw=blank_ids,
            chip_gw=None,
            snap_act_cap_fn=post_cap,
        )
        self.assertEqual(r0, 40.0)


if __name__ == "__main__":
    unittest.main()
