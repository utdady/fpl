"""Squad decision certificates: emit JSON + verify legality (FORMAL.md).

Mirrors `formal/FPL/Certificate.lean`. Verifies the *returned* decision against
declared rules — does not re-solve CBC/PuLP.

Usage:
    from engine.certificate import build_certificate, verify_certificate, write_certificate
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.models import Player, Snapshot, SquadRules, SquadSolution

# Must match formal/FPL/Certificate.lean `rulesVersionDefault`.
RULES_VERSION_DEFAULT = "fpl-default-v1"


@dataclass(frozen=True)
class PlayerSlot:
    id: int
    cost: int
    position: str  # GKP|DEF|MID|FWD
    team_id: int


@dataclass
class SquadCertificate:
    rules_version: str
    snapshot_id: str
    rules: dict[str, int]
    players: list[dict[str, Any]]
    xi_ids: list[int]
    captain_id: int
    vice_id: int
    claimed_cost: int
    claimed_objective_milli: int

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def rules_to_dict(rules: SquadRules) -> dict[str, int]:
    return {
        "squad_size": rules.squad_size,
        "squad_play": rules.squad_play,
        "budget": rules.budget,
        "team_limit": rules.team_limit,
        "gkp_select": rules.squad_select["GKP"],
        "def_select": rules.squad_select["DEF"],
        "mid_select": rules.squad_select["MID"],
        "fwd_select": rules.squad_select["FWD"],
        "gkp_min": rules.min_play["GKP"],
        "gkp_max": rules.max_play["GKP"],
        "def_min": rules.min_play["DEF"],
        "def_max": rules.max_play["DEF"],
        "mid_min": rules.min_play["MID"],
        "mid_max": rules.max_play["MID"],
        "fwd_min": rules.min_play["FWD"],
        "fwd_max": rules.max_play["FWD"],
    }


def snapshot_id_for(snapshot: Snapshot) -> str:
    nxt = snapshot.next_event()
    return f"{snapshot.season_label}|gw{nxt.id}|{snapshot.as_of.isoformat()}"


def build_certificate(
    snapshot: Snapshot,
    solution: SquadSolution,
    *,
    rules_version: str = RULES_VERSION_DEFAULT,
    snapshot_id: str | None = None,
) -> SquadCertificate:
    """Emit a certificate from a solver return value (no re-solve)."""
    players = [
        {
            "id": p.id,
            "cost": p.now_cost,
            "position": p.position,
            "team_id": p.team_id,
        }
        for p in solution.players
    ]
    return SquadCertificate(
        rules_version=rules_version,
        snapshot_id=snapshot_id or snapshot_id_for(snapshot),
        rules=rules_to_dict(snapshot.squad),
        players=players,
        xi_ids=[p.id for p in solution.xi],
        captain_id=solution.captain.id,
        vice_id=solution.vice.id,
        claimed_cost=solution.cost,
        claimed_objective_milli=int(round(solution.horizon_utility * 1000)),
    )


def _count_pos(players: list[dict[str, Any]], pos: str) -> int:
    return sum(1 for p in players if p["position"] == pos)


def _max_club(players: list[dict[str, Any]]) -> int:
    if not players:
        return 0
    return max(Counter(p["team_id"] for p in players).values())


def verify_certificate(cert: SquadCertificate | dict[str, Any]) -> list[str]:
    """Return list of failure reasons; empty means legal under declared rules."""
    if isinstance(cert, SquadCertificate):
        c = cert.to_json()
    else:
        c = cert
    fails: list[str] = []
    rules = c["rules"]
    players = c["players"]
    xi_ids = list(c["xi_ids"])
    ids = [p["id"] for p in players]

    if not c.get("rules_version"):
        fails.append("empty rules_version")
    if not c.get("snapshot_id"):
        fails.append("empty snapshot_id")
    if len(ids) != len(set(ids)):
        fails.append("duplicate player ids")
    if len(players) != rules["squad_size"]:
        fails.append(f"squad size {len(players)} != {rules['squad_size']}")
    cost = sum(p["cost"] for p in players)
    if cost != c["claimed_cost"]:
        fails.append(f"cost sum {cost} != claimed_cost {c['claimed_cost']}")
    if cost > rules["budget"]:
        fails.append(f"cost {cost} > budget {rules['budget']}")
    for key, pos in (
        ("gkp_select", "GKP"),
        ("def_select", "DEF"),
        ("mid_select", "MID"),
        ("fwd_select", "FWD"),
    ):
        got = _count_pos(players, pos)
        if got != rules[key]:
            fails.append(f"{pos} count {got} != {rules[key]}")
    if _max_club(players) > rules["team_limit"]:
        fails.append(f"club count > team_limit {rules['team_limit']}")

    if len(xi_ids) != len(set(xi_ids)):
        fails.append("duplicate xi ids")
    if len(xi_ids) != rules["squad_play"]:
        fails.append(f"XI size {len(xi_ids)} != {rules['squad_play']}")
    squad_set = set(ids)
    if not set(xi_ids).issubset(squad_set):
        fails.append("XI not subset of squad")
    xi_players = [p for p in players if p["id"] in set(xi_ids)]
    for pos, lo, hi in (
        ("GKP", "gkp_min", "gkp_max"),
        ("DEF", "def_min", "def_max"),
        ("MID", "mid_min", "mid_max"),
        ("FWD", "fwd_min", "fwd_max"),
    ):
        n = _count_pos(xi_players, pos)
        if not (rules[lo] <= n <= rules[hi]):
            fails.append(f"XI {pos}={n} not in [{rules[lo]}, {rules[hi]}]")
    if c["captain_id"] not in xi_ids:
        fails.append("captain not in XI")
    if c["vice_id"] not in xi_ids:
        fails.append("vice not in XI")
    return fails


def write_certificate(cert: SquadCertificate, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = cert.to_json()
    payload["emitted_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_certificate(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def emit_lean_example(cert: SquadCertificate | dict[str, Any], path: Path) -> None:
    """Write a Lean snippet that `#eval`s verifyCertificate on this cert (CI optional)."""
    if isinstance(cert, SquadCertificate):
        c = cert.to_json()
    else:
        c = cert
    rules = c["rules"]
    pos_map = {"GKP": "Pos.GKP", "DEF": "Pos.DEF", "MID": "Pos.MID", "FWD": "Pos.FWD"}

    def slot(p: dict[str, Any]) -> str:
        return (
            f"⟨{p['id']}, {p['cost']}, {pos_map[p['position']]}, {p['team_id']}⟩"
        )

    players = ", ".join(slot(p) for p in c["players"])
    xi = ", ".join(str(i) for i in c["xi_ids"])
    lines = [
        "import FPL.Certificate",
        "open FPL",
        "",
        "def cert : SquadCertificate where",
        f'  rulesVersion := "{c["rules_version"]}"',
        f'  snapshotId := "{c["snapshot_id"]}"',
        "  rules := {",
        f"    squadSize := {rules['squad_size']}, squadPlay := {rules['squad_play']},",
        f"    budget := {rules['budget']}, teamLimit := {rules['team_limit']},",
        f"    gkpSelect := {rules['gkp_select']}, defSelect := {rules['def_select']},",
        f"    midSelect := {rules['mid_select']}, fwdSelect := {rules['fwd_select']},",
        f"    gkpMin := {rules['gkp_min']}, gkpMax := {rules['gkp_max']},",
        f"    defMin := {rules['def_min']}, defMax := {rules['def_max']},",
        f"    midMin := {rules['mid_min']}, midMax := {rules['mid_max']},",
        f"    fwdMin := {rules['fwd_min']}, fwdMax := {rules['fwd_max']}",
        "  }",
        f"  players := [{players}]",
        f"  xiIds := [{xi}]",
        f"  captainId := {c['captain_id']}",
        f"  viceId := {c['vice_id']}",
        f"  claimedCost := {c['claimed_cost']}",
        f"  claimedObjectiveMilli := {c['claimed_objective_milli']}",
        "",
        "example : verifyCertificate cert = true := by decide",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Verify a squad certificate JSON")
    p.add_argument("path", type=Path, help="certificate JSON path")
    args = p.parse_args()
    cert = load_certificate(args.path)
    fails = verify_certificate(cert)
    if fails:
        print("REJECT")
        for f in fails:
            print(f"  - {f}")
        raise SystemExit(1)
    print("VALID")
    print(f"  rules_version={cert.get('rules_version')}")
    print(f"  snapshot_id={cert.get('snapshot_id')}")
    print(f"  cost={cert.get('claimed_cost')}  xi={len(cert.get('xi_ids', []))}")


if __name__ == "__main__":
    main()
