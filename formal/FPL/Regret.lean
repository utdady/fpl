/-!
# Nested hindsight regret (FORMAL.md / E007)

Matches `engine.harness_decomp.evaluate_gw` regret columns:

  R_squad = P(oracle) - P(oracle XI+cap | V1 15)
  R_XI    = P(oracle XI+cap | V1 15) - P(V1 XI + best captain)
  R_cap   = P(V1 XI + best captain) - P(V1 XI + V1 captain)
  R_total = R_squad + R_XI + R_cap = P(oracle) - P(V1 realized)

This identity names the god-mode nested oracle. It is **not** the B0 gap.
-/

namespace FPL

/-- Point totals at each layer of the nested hindsight decomposition. -/
structure NestedRegret (α : Type) [Sub α] [Add α] where
  /-- P(hindsight-optimal 15 + XI + captain) -/
  pOracle : α
  /-- P(oracle XI + captain | V1 squad) -/
  pV1SquadOracleXi : α
  /-- P(V1 XI + best captain) -/
  pV1XiOracleCap : α
  /-- P(V1 XI + V1 captain) realized -/
  pV1Realized : α

namespace NestedRegret

variable {α : Type} [Sub α] [Add α]

def rSquad (r : NestedRegret α) : α := r.pOracle - r.pV1SquadOracleXi

def rXi (r : NestedRegret α) : α := r.pV1SquadOracleXi - r.pV1XiOracleCap

def rCap (r : NestedRegret α) : α := r.pV1XiOracleCap - r.pV1Realized

def rTotal (r : NestedRegret α) : α := rSquad r + rXi r + rCap r

end NestedRegret

/-- Additive decomposition of nested hindsight regret (integer points). -/
theorem regret_identity_int (r : NestedRegret Int) :
    NestedRegret.rTotal r = r.pOracle - r.pV1Realized := by
  dsimp [NestedRegret.rTotal, NestedRegret.rSquad, NestedRegret.rXi, NestedRegret.rCap]
  omega

/-- B0 gap is a separate quantity; do not confuse with nested regret. -/
structure B0Gap (α : Type) [Sub α] where
  pB0XiCap : α
  pV1XiCap : α

namespace B0Gap

variable {α : Type} [Sub α]

def gap (g : B0Gap α) : α := g.pB0XiCap - g.pV1XiCap

end B0Gap

end FPL
