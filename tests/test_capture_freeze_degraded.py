"""Ensure freeze CSV survives diagnostics/solver failures."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from engine import capture


class TestFreezeDegraded(unittest.TestCase):
    def test_solver_failure_still_writes_freeze_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = root / "records"
            records.mkdir()
            freeze_path = records / "gw99_v1.0.csv"

            with patch.object(capture, "RECORDS_DIR", records), patch.object(
                capture, "DEGRADED_MARKER", records / ".capture_degraded"
            ), patch.object(
                capture, "AUDIT_LOO_CSV", records / "audit_loo.csv"
            ), patch.object(
                capture, "AUDIT_CF_CSV", records / "audit_counterfactual.csv"
            ), patch.object(
                capture, "load_snapshot", return_value=MagicMock()
            ), patch.object(
                capture,
                "project_all",
                return_value=[self._fake_projection()],
            ), patch.object(
                capture,
                "_write_diagnostics",
                side_effect=RuntimeError("LpVariable.dicts missing"),
            ):
                with self.assertRaises(capture.CaptureDegradedError):
                    capture.freeze(99, refresh=False)

            self.assertTrue(freeze_path.exists(), "freeze CSV must be written")
            marker = records / ".capture_degraded"
            self.assertTrue(marker.exists(), "degraded marker must be set")

    @staticmethod
    def _fake_projection():
        player = MagicMock()
        player.id = 1
        player.web_name = "Test"
        player.team_id = 1
        player.position = "MID"
        player.now_cost = 50
        gw_proj = MagicMock()
        gw_proj.mu = 2.5
        gw_proj.sigma = 1.1
        gw_proj.p_start = 0.9
        gw_proj.p_sub = 0.05
        gw_proj.p_60 = 0.8
        gw_proj.p_10_plus = 0.1
        gw_proj.n_fixtures = 1
        proj = MagicMock()
        proj.player = player
        proj.by_gw = {99: gw_proj}
        return proj


if __name__ == "__main__":
    unittest.main()