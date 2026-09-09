/-!
# Evaluation status (FORMAL.md / E012)

Faithful port of `engine.harness_decomp.classify_week`.

`evaluation_status` depends only on fixture count, actuals integrity, and snapshot
size. Model scores (V1/B0 XI+Cap, regret) never enter this function.

Flags are a closed inductive type so misspellings are compile-time errors.
-/

namespace FPL

inductive EvalStatus
  | clean
  | flagged
  | excluded
  deriving DecidableEq, Repr

/-- Structural reasons / flags emitted by `classifyWeek` (never inspect_*). -/
inductive EvalFlag
  | missingActuals
  | actualsJoinFailure
  | noFixturesNoMinutes
  | pathologicalDuplicateRows
  | duplicateGwRows
  | bgwOrShort
  | dgwOrLong
  | zeroFixtures
  deriving DecidableEq, Repr

/-- Reasons that force `excluded` (subset of `EvalFlag`). -/
def isExclusionFlag : EvalFlag → Bool
  | .missingActuals
  | .actualsJoinFailure
  | .noFixturesNoMinutes
  | .pathologicalDuplicateRows => true
  | _ => false

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

structure EvalResult where
  status : EvalStatus
  flags : List EvalFlag
  deriving DecidableEq, Repr

private def noFlags : List EvalFlag := []

/--
Port of `classify_week(n_fixtures, integ, n_snapshot)`.

Solver failures (`solver_failure`, `xi_solver_failure`) are added downstream in
`evaluate_gw`, not here.
-/
def classifyWeek (nFixtures : Nat) (integ : WeekIntegrity) (nSnapshot : Nat) :
    EvalResult :=
  let excluded₁ :=
    if integ.missingFile || integ.nUniqueActuals == 0 then
      [EvalFlag.missingActuals]
    else
      noFlags
  let jf := joinFloor nSnapshot
  let excluded₂ :=
    if integ.nUniqueActuals > 0 && integ.nUniqueActuals < jf then
      [EvalFlag.actualsJoinFailure]
    else
      noFlags
  let excluded₃ :=
    if nFixtures == 0 && integ.nWithMinutes == 0 then
      [EvalFlag.noFixturesNoMinutes]
    else
      noFlags
  let (excluded₄, flagDup) :=
    if integ.nDuplicateIds > max 20 integ.nUniqueActuals then
      ([EvalFlag.pathologicalDuplicateRows], noFlags)
    else if integ.nDuplicateIds > 5 then
      (noFlags, [EvalFlag.duplicateGwRows])
    else
      (noFlags, noFlags)
  let flags₁ := if nFixtures < 10 then [EvalFlag.bgwOrShort] else noFlags
  let flags₂ := if nFixtures > 10 then [EvalFlag.dgwOrLong] else noFlags
  let flags₃ := if nFixtures == 0 then [EvalFlag.zeroFixtures] else noFlags
  let allFlags := flags₁ ++ flags₂ ++ flags₃ ++ flagDup
  let allExcluded := excluded₁ ++ excluded₂ ++ excluded₃ ++ excluded₄
  if allExcluded ≠ [] then
    { status := .excluded, flags := allExcluded ++ allFlags }
  else if allFlags ≠ [] then
    { status := .flagged, flags := allFlags }
  else
    { status := .clean, flags := noFlags }

/-- Every excluded result cites at least one structural exclusion flag. -/
def excludedHasStructuralReason (r : EvalResult) : Bool :=
  r.status != .excluded || r.flags.any isExclusionFlag

/-! ### Sanity checks (decidable instances on concrete weeks) -/

/-- `joinFloor 500 = 75`; need `nUniqueActuals ≥ 75` to avoid join failure. -/
example : classifyWeek 10 ⟨false, 100, 80, 0, 50⟩ 500 =
    { status := .clean, flags := noFlags } := by
  decide

example : classifyWeek 8 ⟨false, 100, 80, 0, 50⟩ 500 =
    { status := .flagged, flags := [EvalFlag.bgwOrShort] } := by
  decide

example : classifyWeek 10 ⟨false, 100, 10, 0, 50⟩ 800 =
    { status := .excluded, flags := [EvalFlag.actualsJoinFailure] } := by
  decide

example : excludedHasStructuralReason
    (classifyWeek 10 ⟨false, 100, 10, 0, 50⟩ 800) = true := by
  decide

end FPL
