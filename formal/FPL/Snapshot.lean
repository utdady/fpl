/-!
# Snapshot cutoff types (FORMAL.md)

Type-level information boundary: a predictor at GW `n` may only read `Snapshot n`.
Provenance (whether allowed fields were honestly reconstructed) stays in Python
(`engine.harness_validate`, `docs/HARNESS_SPEC.md`).
-/

namespace FPL

/-- Fields permitted in a pre-deadline snapshot for gameweek `gw`. -/
structure Snapshot (gw : Nat) where
  playerIds : List Nat
  openingPrices : List (Nat × Nat)
  /-- Cumulative stats are only through GW `gw - 1`. -/
  ratesThroughGw : Nat
  ratesCutoff_ok : ratesThroughGw + 1 = gw ∨ gw = 0

/-- Actual points for a gameweek — separate type from `Snapshot`. -/
structure Actuals (gw : Nat) where
  points : List (Nat × Float)

/-- A model prediction from permitted pre-deadline information only. -/
structure Prediction where
  mus : List (Nat × Float)

/--
A predictor at `gw` cannot access `Actuals gw` or later — those types are not in
the function signature.
-/
structure Predictor (gw : Nat) where
  predict : Snapshot gw → Prediction

/-- Example: composing predict with actuals is ill-typed unless `gw` matches. -/
def predictAt (gw : Nat) (pred : Predictor gw) (snap : Snapshot gw) : Prediction :=
  pred.predict snap

end FPL
