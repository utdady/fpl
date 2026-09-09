/-!
# XI / lineup legality (FORMAL.md)

Formation windows from `SquadRules.min_play` / `max_play`.
Matches `engine.optimize.solve_xi` constraints.
-/

import FPL.Squad

namespace FPL

/-- XI slots must be a subset of the squad (by id), size `squadPlay`, legal formation. -/
def isLegalXI (rules : SquadRules) (squad : List PlayerSlot) (xiIds : List Nat) : Bool :=
  let squadIds := squad.map (·.id)
  !(hasDuplicateIds xiIds)
    && xiIds.length == rules.squadPlay
    && xiIds.all (fun i => squadIds.contains i)
    &&
      let xiPlayers := squad.filter (fun p => xiIds.contains p.id)
      let g := countPos xiPlayers .GKP
      let d := countPos xiPlayers .DEF
      let m := countPos xiPlayers .MID
      let f := countPos xiPlayers .FWD
      rules.gkpMin ≤ g && g ≤ rules.gkpMax
        && rules.defMin ≤ d && d ≤ rules.defMax
        && rules.midMin ≤ m && m ≤ rules.midMax
        && rules.fwdMin ≤ f && f ≤ rules.fwdMax

def captainInXI (xiIds : List Nat) (captainId : Nat) : Bool :=
  xiIds.contains captainId

def viceInXI (xiIds : List Nat) (viceId : Nat) : Bool :=
  xiIds.contains viceId

/-- Default formation: 1 GKP, 3–5 DEF, 2–5 MID, 1–3 FWD. -/
private def toySquad : List PlayerSlot :=
  [ ⟨1, 45, .GKP, 1⟩, ⟨2, 40, .GKP, 2⟩
  , ⟨3, 50, .DEF, 1⟩, ⟨4, 45, .DEF, 2⟩, ⟨5, 45, .DEF, 3⟩, ⟨6, 40, .DEF, 4⟩, ⟨7, 40, .DEF, 5⟩
  , ⟨8, 70, .MID, 1⟩, ⟨9, 65, .MID, 2⟩, ⟨10, 60, .MID, 3⟩, ⟨11, 55, .MID, 4⟩, ⟨12, 50, .MID, 5⟩
  , ⟨13, 80, .FWD, 6⟩, ⟨14, 70, .FWD, 7⟩, ⟨15, 55, .FWD, 8⟩ ]

private def toyXI : List Nat := [1, 3, 4, 5, 8, 9, 10, 11, 13, 14, 15]

example : isLegalXI defaultSquadRules toySquad toyXI = true := by decide

example : captainInXI toyXI 8 = true := by decide

example : isLegalXI defaultSquadRules toySquad (toyXI.drop 1) = false := by decide

end FPL
