"""Unit tests for live capture ops decision helpers (no network)."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from engine.live_ops import should_freeze, should_score


class TestLiveCaptureOps(unittest.TestCase):
    def test_freeze_only_inside_pre_deadline_window(self) -> None:
        now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        deadline = now + timedelta(hours=24)
        self.assertTrue(
            should_freeze(now=now, deadline=deadline, path_exists=False, window_hours=48)
        )
        self.assertFalse(
            should_freeze(now=now, deadline=deadline, path_exists=True, window_hours=48)
        )
        far = now + timedelta(hours=72)
        self.assertFalse(
            should_freeze(now=now, deadline=far, path_exists=False, window_hours=48)
        )
        self.assertFalse(
            should_freeze(
                now=deadline + timedelta(minutes=1),
                deadline=deadline,
                path_exists=False,
                window_hours=48,
            )
        )

    def test_score_requires_data_checked_and_unscored_freeze(self) -> None:
        self.assertTrue(
            should_score(path_exists=True, already_scored=False, data_checked=True)
        )
        self.assertFalse(
            should_score(path_exists=True, already_scored=False, data_checked=False)
        )
        self.assertFalse(
            should_score(path_exists=True, already_scored=True, data_checked=True)
        )
        self.assertFalse(
            should_score(path_exists=False, already_scored=False, data_checked=True)
        )


if __name__ == "__main__":
    unittest.main()
