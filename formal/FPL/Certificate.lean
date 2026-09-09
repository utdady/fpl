import FPL.Squad
import FPL.Lineup

/-!
# Squad decision certificate (FORMAL.md)

Verifies a **returned** decision against declared rules. Does **not** re-solve
the ILP or prove CBC optimality.

```text
Python / CBC → SquadCertificate → verifyCertificate → legal / reject
```

`rulesVersion` / `snapshotId` bind the check to a declared rule set and snapshot,
not "some" legal squad in the abstract.
-/

namespace FPL

/--
Boring certificate emitted by Python after `solve_squad`.

Costs are FPL tenths (£0.1m). `claimedObjectiveMilli` is horizon utility × 1000
(recorded; Lean does not re-derive float utilities from CBC).
-/
structure SquadCertificate where
  rulesVersion : String
  snapshotId : String
  rules : SquadRules
  players : List PlayerSlot
  xiIds : List Nat
  captainId : Nat
  viceId : Nat
  claimedCost : Nat
  claimedObjectiveMilli : Int
  deriving Repr

/-- Structural legality of a returned decision under the certificate's rules. -/
def verifyCertificate (c : SquadCertificate) : Bool :=
  isLegalSquad c.rules c.players
    && isLegalXI c.rules c.players c.xiIds
    && captainInXI c.xiIds c.captainId
    && viceInXI c.xiIds c.viceId
    && totalCost c.players == c.claimedCost
    && c.rulesVersion != ""
    && c.snapshotId != ""

/-- Known rules tag for default FPL constraints. -/
def rulesVersionDefault : String := "fpl-default-v1"

private def toyCert : SquadCertificate where
  rulesVersion := rulesVersionDefault
  snapshotId := "toy-snapshot"
  rules := defaultSquadRules
  players :=
    [ ⟨1, 45, .GKP, 1⟩, ⟨2, 40, .GKP, 2⟩
    , ⟨3, 50, .DEF, 1⟩, ⟨4, 45, .DEF, 2⟩, ⟨5, 45, .DEF, 3⟩, ⟨6, 40, .DEF, 4⟩, ⟨7, 40, .DEF, 5⟩
    , ⟨8, 70, .MID, 1⟩, ⟨9, 65, .MID, 2⟩, ⟨10, 60, .MID, 3⟩, ⟨11, 55, .MID, 4⟩, ⟨12, 50, .MID, 5⟩
    , ⟨13, 80, .FWD, 6⟩, ⟨14, 70, .FWD, 7⟩, ⟨15, 55, .FWD, 8⟩ ]
  xiIds := [1, 3, 4, 5, 8, 9, 10, 11, 13, 14, 15]
  captainId := 8
  viceId := 13
  claimedCost := 810
  claimedObjectiveMilli := 0

example : verifyCertificate toyCert = true := by decide

example : verifyCertificate { toyCert with captainId := 2 } = false := by decide

example : verifyCertificate { toyCert with claimedCost := 999 } = false := by decide

end FPL
