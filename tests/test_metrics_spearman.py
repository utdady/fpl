"""Unit tests for engine.metrics.spearman tie handling."""
from __future__ import annotations

import unittest

from engine.metrics import spearman


class TestSpearmanTies(unittest.TestCase):
    def test_tied_values_receive_average_rank(self) -> None:
        xs = [1.0, 2.0, 2.0, 4.0]
        ys = [4.0, 1.0, 1.0, 2.0]
        # Tie-aware ranks: x -> 1, 2.5, 2.5, 4; y -> 4, 1.5, 1.5, 3
        got = spearman(xs, ys)
        self.assertAlmostEqual(got, -1.0 / 3.0, places=10)

    def test_all_tied_returns_zero(self) -> None:
        xs = [3.0, 3.0, 3.0]
        ys = [1.0, 2.0, 3.0]
        self.assertEqual(spearman(xs, ys), 0.0)


if __name__ == "__main__":
    unittest.main()