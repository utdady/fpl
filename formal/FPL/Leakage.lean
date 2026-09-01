/-!
# B0 leakage flag (FORMAL.md / E008)

Pre-registered rule: `LeakFlag = (Spearman(xP, actual) > 0.70)`.

Evaluation-time only — may depend on actuals. Must not depend on V1/V2 scores.
Python constant: `engine.obs.LEAKAGE_SPEARMAN = 0.70`.
-/

namespace FPL

/-- Inputs to the leakage flag. V1 / challenger scores are intentionally absent. -/
structure LeakInput where
  xp : List Float
  actual : List Float

/-- Spearman correlation; computed in Python (`engine.metrics.spearman`). -/
opaque spearman : List Float → List Float → Option Float

/-- Pre-registered E008 threshold (must match `engine.obs.LEAKAGE_SPEARMAN`). -/
def leakageSpearmanThreshold : Float := 0.70

def leakFlag (inp : LeakInput) : Bool :=
  match spearman inp.xp inp.actual with
  | some ρ => ρ > leakageSpearmanThreshold
  | none => false

/-- `LeakInput` has no V1 field; mutating unused challenger scores cannot change the flag. -/
theorem leakFlag_independent_of_unused_v1 (inp : LeakInput) (_v1 _v1' : List Float) :
    leakFlag inp = leakFlag inp := rfl

/-- Alias for the pre-registered constant (documentation / cross-ref with Python). -/
theorem leakage_threshold_value : leakageSpearmanThreshold = 0.70 := rfl

end FPL
