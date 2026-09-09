/-!
# B0 leakage dependency contract (FORMAL.md / E008)

This module is a **dependency contract**, not a full formalization of Spearman.

Pre-registered rule: `LeakFlag = (Spearman(xP, actual) > 0.70)`.

- Evaluation-time only — may depend on actuals.
- Must not depend on V1/V2 scores: those fields are absent from `LeakInput`.
- Spearman itself is `opaque`; Python (`engine.metrics.spearman`) remains the
  implementation authority. Lean only records the input boundary and threshold.

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

/-- Threshold cross-ref with Python (must stay 0.70). -/
theorem leakage_threshold_value : leakageSpearmanThreshold = 0.70 := rfl

end FPL
