/-!
# Squad legality predicates (FORMAL.md)

Matches `engine.models.SquadRules` / `engine.harness.default_squad` and the
structural checks in `engine.audit.sanity_checklist` / `engine.optimize.solve_squad`.

Used by `Certificate.lean`. Does not solve the ILP.
-/

namespace FPL

inductive Pos
  | GKP | DEF | MID | FWD
  deriving DecidableEq, Repr, Inhabited

/-- Declared FPL squad rules (tenths of £m for budget/cost). -/
structure SquadRules where
  squadSize : Nat
  squadPlay : Nat
  budget : Nat
  teamLimit : Nat
  gkpSelect : Nat
  defSelect : Nat
  midSelect : Nat
  fwdSelect : Nat
  gkpMin : Nat
  gkpMax : Nat
  defMin : Nat
  defMax : Nat
  midMin : Nat
  midMax : Nat
  fwdMin : Nat
  fwdMax : Nat
  deriving DecidableEq, Repr

/-- Default 2024/25–2026/27 FPL rules (`engine.harness.default_squad`). -/
def defaultSquadRules : SquadRules where
  squadSize := 15
  squadPlay := 11
  budget := 1000
  teamLimit := 3
  gkpSelect := 2
  defSelect := 5
  midSelect := 5
  fwdSelect := 3
  gkpMin := 1
  gkpMax := 1
  defMin := 3
  defMax := 5
  midMin := 2
  midMax := 5
  fwdMin := 1
  fwdMax := 3

structure PlayerSlot where
  id : Nat
  cost : Nat
  position : Pos
  teamId : Nat
  deriving DecidableEq, Repr

def countPos (players : List PlayerSlot) (p : Pos) : Nat :=
  (players.filter (·.position == p)).length

def totalCost (players : List PlayerSlot) : Nat :=
  players.foldl (fun acc x => acc + x.cost) 0

/-- Max count of any single `teamId` in the list. -/
def maxClubCount (players : List PlayerSlot) : Nat :=
  players.foldl
    (fun m x =>
      let c := (players.filter (·.teamId == x.teamId)).length
      max m c)
    0

def hasDuplicateIds : List Nat → Bool
  | [] => false
  | x :: xs => xs.contains x || hasDuplicateIds xs

def idsUnique (players : List PlayerSlot) : Bool :=
  !(hasDuplicateIds (players.map (·.id)))

/-- Legal 15-man squad under declared rules (size, budget, positions, clubs). -/
def isLegalSquad (rules : SquadRules) (players : List PlayerSlot) : Bool :=
  idsUnique players
    && players.length == rules.squadSize
    && totalCost players ≤ rules.budget
    && countPos players .GKP == rules.gkpSelect
    && countPos players .DEF == rules.defSelect
    && countPos players .MID == rules.midSelect
    && countPos players .FWD == rules.fwdSelect
    && maxClubCount players ≤ rules.teamLimit

/-- Concrete legal toy squad under default rules. -/
private def toyLegalSquad : List PlayerSlot :=
  [ ⟨1, 45, .GKP, 1⟩, ⟨2, 40, .GKP, 2⟩
  , ⟨3, 50, .DEF, 1⟩, ⟨4, 45, .DEF, 2⟩, ⟨5, 45, .DEF, 3⟩, ⟨6, 40, .DEF, 4⟩, ⟨7, 40, .DEF, 5⟩
  , ⟨8, 70, .MID, 1⟩, ⟨9, 65, .MID, 2⟩, ⟨10, 60, .MID, 3⟩, ⟨11, 55, .MID, 4⟩, ⟨12, 50, .MID, 5⟩
  , ⟨13, 80, .FWD, 6⟩, ⟨14, 70, .FWD, 7⟩, ⟨15, 55, .FWD, 8⟩ ]

example : isLegalSquad defaultSquadRules toyLegalSquad = true := by decide

example : isLegalSquad defaultSquadRules (toyLegalSquad.drop 1) = false := by decide

end FPL
