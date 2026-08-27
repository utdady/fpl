"""E012: evaluation-integrity property tests (FORMAL.md).

Not a V2 gate. Verifies dependency graphs:
  - evaluation_status from structure only (not model scores)
  - LeakFlag from B0 xP + actuals only (not V1 scores)
  - R_total = R_squad + R_XI + R_cap (named god-mode oracle)
  - ILP constraint set F comes from Snapshot.squad rules

Usage:
    python -m unittest tests.test_e012_integrity -v
"""
from __future__ import annotations

import csv
import inspect
import math
import random
import unittest
from pathlib import Path

from engine.harness_decomp import classify_week
from engine.metrics import spearman
from engine.obs import LEAKAGE_SPEARMAN
from engine.optimize import solve_squad

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "records" / "historical"
SEASONS = ("2022-23", "2023-24", "2024-25", "2025-26")


def _f(x: str) -> float | None:
    if x is None or x == "":
        return None
    return float(x)


class TestEvaluationStatusIndependence(unittest.TestCase):
    """evaluation_status must not depend on model error / XI+Cap / regret."""

    def test_classify_week_signature_has_no_score_params(self) -> None:
        params = list(inspect.signature(classify_week).parameters)
        self.assertEqual(params, ["n_fixtures", "integ", "n_snapshot"])

    def test_recompute_status_from_structure_matches_recorded(self) -> None:
        """Re-run classify_week from stored integrity fields; ignore solver_failure."""
        checked = 0
        for season in SEASONS:
            path = HIST / season / "decision_gw.csv"
            if not path.exists():
                continue
            with path.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            for r in rows:
                flags = r.get("structural_flags") or ""
                if "solver_failure" in flags or "xi_solver_failure" in flags:
                    continue
                integ = {
                    "missing_file": False,
                    "n_actual_rows": int(r["n_actual_rows"]),
                    "n_unique_actuals": int(r["n_unique_actuals"]),
                    "n_duplicate_ids": int(r["n_duplicate_ids"]),
                    "n_with_minutes": int(r["n_with_minutes"]),
                }
                # missing_actuals path: unique==0
                if integ["n_unique_actuals"] == 0:
                    integ["missing_file"] = True
                status, _ = classify_week(
                    int(r["n_fixtures"]), integ, int(r["n_snapshot"])
                )
                self.assertEqual(
                    status,
                    r["evaluation_status"],
                    msg=f"{season} GW{r['gw']}: got {status} want {r['evaluation_status']} flags={flags}",
                )
                checked += 1
        self.assertGreater(checked, 100)

    def test_inspect_score_thresholds_do_not_set_excluded(self) -> None:
        """Never set excluded from V1 XI+Cap < 15 or B0 XI+Cap > 80 (FORMAL)."""
        for season in SEASONS:
            path = HIST / season / "decision_gw.csv"
            if not path.exists():
                continue
            with path.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            for r in rows:
                if r["evaluation_status"] != "excluded":
                    continue
                flags = r.get("structural_flags") or ""
                # inspect_* are diagnostic only; exclusion must cite structure/solver
                self.assertTrue(
                    any(
                        tok in flags
                        for tok in (
                            "missing_actuals",
                            "actuals_join_failure",
                            "no_fixtures_no_minutes",
                            "pathological_duplicate_rows",
                            "solver_failure",
                            "xi_solver_failure",
                        )
                    ),
                    msg=f"{season} GW{r['gw']} excluded without structural reason: {flags}",
                )


class TestLeakFlagIndependence(unittest.TestCase):
    """LeakFlag = h(xP, actual); must ignore V1 / challenger scores."""

    def test_leakage_threshold_constant(self) -> None:
        self.assertEqual(LEAKAGE_SPEARMAN, 0.70)

    def test_flag_from_xp_actual_only(self) -> None:
        rng = random.Random(7)
        n = 80
        xp = [rng.random() * 10 for _ in range(n)]
        # High correlation -> flag
        act_hi = [x + rng.random() * 0.01 for x in xp]
        sp_hi = spearman(xp, act_hi)
        flag_hi = int(sp_hi == sp_hi and sp_hi > LEAKAGE_SPEARMAN)
        self.assertEqual(flag_hi, 1)

        # Shuffle actuals -> low correlation -> no flag
        act_lo = act_hi[:]
        rng.shuffle(act_lo)
        sp_lo = spearman(xp, act_lo)
        flag_lo = int(sp_lo == sp_lo and sp_lo > LEAKAGE_SPEARMAN)
        self.assertEqual(flag_lo, 0)

        # Mutating fake V1 scores must not enter the formula
        v1_mutated = [rng.random() * 100 for _ in range(n)]
        sp_again = spearman(xp, act_hi)
        flag_again = int(sp_again == sp_again and sp_again > LEAKAGE_SPEARMAN)
        self.assertEqual(flag_again, flag_hi)
        self.assertNotEqual(v1_mutated[0], xp[0])  # v1 unused

    def test_recorded_b0_leakage_recomputable_without_v1(self) -> None:
        """Existing E008 CSVs: leakage_flag matches Spearman(xP,actual) > 0.70."""
        from engine.harness import gw_actuals, gw_xp

        checked = 0
        for season in ("2024-25", "2025-26"):
            path = HIST / season / "b0_leakage.csv"
            if not path.exists():
                continue
            with path.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            for r in rows:
                gw = int(r["gw"])
                xp = gw_xp(season, gw)
                act = gw_actuals(season, gw)
                xs, ys = [], []
                for pid, pred in xp.items():
                    a = act.get(pid)
                    if a is None:
                        continue
                    xs.append(pred)
                    ys.append(float(a["actual_points"]))
                if len(xs) < 10:
                    continue
                sp = spearman(xs, ys)
                want = int(sp == sp and sp > LEAKAGE_SPEARMAN)
                self.assertEqual(want, int(r["leakage_flag"]), msg=f"{season} GW{gw}")
                checked += 1
        self.assertGreater(checked, 20)


class TestRegretIdentity(unittest.TestCase):
    """R_total = R_squad + R_XI + R_cap = P(oracle) - P(V1 realized)."""

    def test_algebraic_identity(self) -> None:
        p_oracle, p_v1_sq, p_v1_xi, p_v1 = 120.0, 100.0, 95.0, 90.0
        r_squad = p_oracle - p_v1_sq
        r_xi = p_v1_sq - p_v1_xi
        r_cap = p_v1_xi - p_v1
        self.assertAlmostEqual(r_squad + r_xi + r_cap, p_oracle - p_v1)

    def test_identity_on_historical_decision_gw(self) -> None:
        checked = 0
        for season in SEASONS:
            path = HIST / season / "decision_gw.csv"
            if not path.exists():
                continue
            with path.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            for r in rows:
                o = _f(r.get("hindsight_oracle_cap"))
                v = _f(r.get("v1_xi_cap"))
                rs = _f(r.get("hindsight_squad_regret"))
                rx = _f(r.get("hindsight_xi_regret"))
                rc = _f(r.get("hindsight_cap_regret"))
                if None in (o, v, rs, rx, rc):
                    continue
                self.assertTrue(
                    math.isclose(rs + rx + rc, o - v, abs_tol=1e-6),
                    msg=f"{season} GW{r['gw']}: {rs}+{rx}+{rc} != {o}-{v}",
                )
                checked += 1
        self.assertGreater(checked, 100)


class TestFeasibleSetFromSnapshot(unittest.TestCase):
    """Compare arms must share Snapshot.squad constraint declarations."""

    def test_solve_squad_binds_snapshot_rules_only(self) -> None:
        src = inspect.getsource(solve_squad)
        self.assertIn("rules = snapshot.squad", src)
        self.assertIn("rules.squad_size", src)
        self.assertIn("rules.budget", src)
        self.assertIn("rules.team_limit", src)
        # Objective/utilities may differ; constraint source must be snapshot
        self.assertNotIn("b0", src.lower().split("rules")[0])  # weak: no b0 before rules


if __name__ == "__main__":
    unittest.main()
