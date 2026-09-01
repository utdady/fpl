/-!
# Evaluation status (FORMAL.md / E012)

Faithful port of `engine.harness_decomp.classify_week`.

`evaluation_status` depends only on fixture count, actuals integrity, and snapshot
size. Model scores (V1/B0 XI+Cap, regret) never enter this function.
-/

namespace FPL

inductive EvalStatus
  | clean
  | flagged
  | excluded
  deriving DecidableEq, Repr

/-- Structural inputs to `classifyWeek` — no model scores. -/
structure WeekIntegrity where
  missingFile : Bool
  nActualRows : Nat
  nUniqueActuals : Nat
  nDuplicateIds : Nat
  nWithMinutes : Nat
  deriving Repr, DecidableEq

/-- Join floor: `max(50, int(0.15 * n_snapshot))` from harness_decomp. -/
def joinFloor (nSnapshot : Nat) : Nat :=
  max 50 (nSnapshot * 15 / 100)

/-- Reasons that may force `excluded` (never `inspect_v1_lt_15` / `inspect_b0_gt_80`). -/
def structuralExclusionReason (s : String) : Bool :=
  s == "missing_actuals"
    || s == "actuals_join_failure"
    || s == "no_fixtures_no_minutes"
    || s == "pathological_duplicate_rows"

def allowedStatusFlags : List String :=
  [
    "missing_actuals",
    "actuals_join_failure",
    "no_fixtures_no_minutes",
    "pathological_duplicate_rows",
    "duplicate_gw_rows",
    "bgw_or_short",
    "dgw_or_long",
    "zero_fixtures"
  ]

private def noFlags : List String := []

/--
Port of `classify_week(n_fixtures, integ, n_snapshot)`.

Solver failures (`solver_failure`, `xi_solver_failure`) are added downstream in
`evaluate_gw`, not here.
-/
def classifyWeek (nFixtures : Nat) (integ : WeekIntegrity) (nSnapshot : Nat) :
    EvalStatus × List String :=
  let excluded₁ :=
    if integ.missingFile || integ.nUniqueActuals == 0 then
      ["missing_actuals"]
    else
      noFlags
  let jf := joinFloor nSnapshot
  let excluded₂ :=
    if integ.nUniqueActuals > 0 && integ.nUniqueActuals < jf then
      ["actuals_join_failure"]
    else
      noFlags
  let excluded₃ :=
    if nFixtures == 0 && integ.nWithMinutes == 0 then
      ["no_fixtures_no_minutes"]
    else
      noFlags
  let (excluded₄, flagDup) :=
    if integ.nDuplicateIds > max 20 integ.nUniqueActuals then
      (["pathological_duplicate_rows"], noFlags)
    else if integ.nDuplicateIds > 5 then
      (noFlags, ["duplicate_gw_rows"])
    else
      (noFlags, noFlags)
  let flags₁ := if nFixtures < 10 then ["bgw_or_short"] else noFlags
  let flags₂ := if nFixtures > 10 then ["dgw_or_long"] else noFlags
  let flags₃ := if nFixtures == 0 then ["zero_fixtures"] else noFlags
  let allFlags := flags₁ ++ flags₂ ++ flags₃ ++ flagDup
  let allExcluded := excluded₁ ++ excluded₂ ++ excluded₃ ++ excluded₄
  if allExcluded ≠ [] then
    (.excluded, allExcluded ++ allFlags)
  else if allFlags ≠ [] then
    (.flagged, allFlags)
  else
    (.clean, noFlags)

/-! ### Sanity checks (decidable instances on concrete weeks) -/

example : classifyWeek 10 ⟨false, 100, 80, 0, 50⟩ 800 = (.clean, noFlags) := by
  native_decide

example : classifyWeek 8 ⟨false, 100, 80, 0, 50⟩ 800 = (.flagged, ["bgw_or_short"]) := by
  native_decide

example :
    classifyWeek 10 ⟨false, 100, 10, 0, 50⟩ 800 =
      (.excluded, ["actuals_join_failure"]) := by
  native_decide

example :
    ¬ ("inspect_v1_lt_15" ∈ (classifyWeek 10 ⟨false, 100, 80, 0, 50⟩ 800).2) := by
  native_decide

example :
    ¬ ("inspect_b0_gt_80" ∈ (classifyWeek 10 ⟨false, 100, 80, 0, 50⟩ 800).2) := by
  native_decide

/-- Diagnostic inspect flags are not in the allowed output set of `classifyWeek`. -/
theorem inspect_flags_not_allowed :
    ("inspect_v1_lt_15" ∉ allowedStatusFlags)
      ∧ ("inspect_b0_gt_80" ∉ allowedStatusFlags) := by
  native_decide

end FPL
