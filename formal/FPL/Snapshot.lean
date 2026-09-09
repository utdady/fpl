/-!
# Snapshot cutoff types (FORMAL.md)

**Type-level cutoff, not provenance.**

A `Predictor gw` may only take `Snapshot gw` in its signature — it cannot take
`Actuals gw` as a parameter. That is a dependency-boundary contract.

This does **not** prove that the *contents* of a `Snapshot` were honestly
reconstructed from pre-deadline data. Contaminated fields can still inhabit the
type. Provenance stays in Python (`engine.harness_validate`, `docs/HARNESS_SPEC.md`).
-/

namespace FPL

/--
Fields permitted in a pre-deadline snapshot for gameweek `gw`.

`ratesCutoff_ok` only constrains the *label* `ratesThroughGw`; it does not
inspect rate payloads.
-/
structure Snapshot (gw : Nat) where
  playerIds : List Nat
  openingPrices : List (Nat × Nat)
  /-- Claimed cumulative-stats cutoff (GW `gw - 1` when `gw > 0`). -/
  ratesThroughGw : Nat
  ratesCutoff_ok : ratesThroughGw + 1 = gw ∨ gw = 0

/-- Actual points for a gameweek — separate type from `Snapshot`. -/
structure Actuals (gw : Nat) where
  points : List (Nat × Float)

/-- A model prediction from permitted pre-deadline information only. -/
structure Prediction where
  mus : List (Nat × Float)

/--
A predictor at `gw` cannot access `Actuals` through its type — those are not in
the function signature. This is not a provenance proof.
-/
structure Predictor (gw : Nat) where
  predict : Snapshot gw → Prediction

def predictAt (gw : Nat) (pred : Predictor gw) (snap : Snapshot gw) : Prediction :=
  pred.predict snap

end FPL
