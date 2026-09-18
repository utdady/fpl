"""v0 preference-conditioned Model A re-solve.

S1 = argmax U over F
S2 = argmax U over F_prefs   (same objective; feasible set only)

Green primitives only:
  LOCK / BAN by element_id
  BANK in {0.0, 0.5, 1.0, 1.5, 2.0}m
  CLUB team_id -> max in {0,1,2}

Diagnostics are descriptive. Never reweight U.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.candidates import diagnose
from engine.model_config import PRODUCTION
from engine.models import PlayerProjection, Snapshot, SquadSolution
from engine.optimize import SquadInfeasibleError, SquadSolverError, solve_squad
from engine.stability_selection import squad_objective_value

OBJECTIVE = "horizon"
BANK_MENU_M = (0.0, 0.5, 1.0, 1.5, 2.0)
# FPL costs are tenths of £m (£1.0m → 10).
BANK_MENU_TENTHS = (0, 5, 10, 15, 20)
CLUB_MAX_ALLOWED = (0, 1, 2)


@dataclass(frozen=True)
class Preferences:
    lock: frozenset[int] = field(default_factory=frozenset)
    ban: frozenset[int] = field(default_factory=frozenset)
    min_bank_m: float | None = None
    club_max: dict[int, int] = field(default_factory=dict)

    def empty(self) -> bool:
        return (
            not self.lock
            and not self.ban
            and self.min_bank_m is None
            and not self.club_max
        )

    def min_bank_tenths(self) -> int | None:
        if self.min_bank_m is None:
            return None
        return BANK_MENU_TENTHS[BANK_MENU_M.index(self.min_bank_m)]


@dataclass(frozen=True)
class SquadView:
    ids: list[int]
    names: list[str]
    xi: list[str]
    bench: list[str]
    captain: str
    vice: str
    cost: int
    bank: int
    u: float
    next_xi_mu: float
    minutes_risk: int
    club_max: int


@dataclass(frozen=True)
class PreferenceResult:
    feasible: bool
    message: str | None
    preferences: Preferences
    s1: SquadView
    s2: SquadView | None
    delta_u: float | None
    distance: int | None
    enters: list[str]
    exits: list[str]
    model: dict[str, Any]


def preferences_from_payload(data: dict[str, Any] | None) -> Preferences:
    raw = data or {}
    lock = frozenset(int(x) for x in (raw.get("lock") or []))
    ban = frozenset(int(x) for x in (raw.get("ban") or []))
    bank_raw = raw.get("min_bank_m", raw.get("bank_m"))
    min_bank_m = None if bank_raw is None or bank_raw == "" else float(bank_raw)
    club_raw = raw.get("club_max") or {}
    club_max = {int(k): int(v) for k, v in club_raw.items()}
    prefs = Preferences(lock=lock, ban=ban, min_bank_m=min_bank_m, club_max=club_max)
    validate_preferences(prefs)
    return prefs


def validate_preferences(prefs: Preferences) -> None:
    overlap = prefs.lock & prefs.ban
    if overlap:
        raise ValueError(f"LOCK and BAN overlap: {sorted(overlap)}")
    if prefs.min_bank_m is not None and prefs.min_bank_m not in BANK_MENU_M:
        raise ValueError(
            f"min_bank_m must be one of {BANK_MENU_M}, got {prefs.min_bank_m}"
        )
    for tid, lim in prefs.club_max.items():
        if lim not in CLUB_MAX_ALLOWED:
            raise ValueError(f"club_max[{tid}] must be in {CLUB_MAX_ALLOWED}, got {lim}")


def _view(sol: SquadSolution, by_id: dict[int, PlayerProjection]) -> SquadView:
    from collections import Counter

    u = squad_objective_value(sol.players, sol.xi, by_id, objective=OBJECTIVE)
    risk = sum(1 for p in sol.players if by_id[p.id].next_p_start < 0.75)
    counts = Counter(p.team_id for p in sol.players)
    return SquadView(
        ids=[p.id for p in sol.players],
        names=[p.web_name for p in sol.players],
        xi=[p.web_name for p in sol.xi],
        bench=[p.web_name for p in sol.bench],
        captain=sol.captain.web_name,
        vice=sol.vice.web_name,
        cost=sol.cost,
        bank=sol.bank,
        u=u,
        next_xi_mu=sol.next_xi_mu,
        minutes_risk=risk,
        club_max=max(counts.values()) if counts else 0,
    )


def _squad_dict(view: SquadView) -> dict[str, Any]:
    return {
        "ids": view.ids,
        "names": view.names,
        "xi": view.xi,
        "bench": view.bench,
        "captain": view.captain,
        "vice": view.vice,
        "cost": view.cost,
        "bank": view.bank,
        "bank_m": view.bank / 10.0,
        "u": round(view.u, 4),
        "next_xi_mu": round(view.next_xi_mu, 4),
        "minutes_risk": view.minutes_risk,
        "club_max": view.club_max,
    }


def result_to_json(result: PreferenceResult) -> dict[str, Any]:
    return {
        "source": "engine.preferences.solve_preference_pair",
        "copy": "Best squad given your constraints (same Model A objective).",
        "feasible": result.feasible,
        "message": result.message,
        "model": result.model,
        "preferences": {
            "lock": sorted(result.preferences.lock),
            "ban": sorted(result.preferences.ban),
            "min_bank_m": result.preferences.min_bank_m,
            "club_max": {str(k): v for k, v in sorted(result.preferences.club_max.items())},
        },
        "s1": _squad_dict(result.s1),
        "s2": _squad_dict(result.s2) if result.s2 else None,
        "delta_u": None if result.delta_u is None else round(result.delta_u, 4),
        "distance": result.distance,
        "enters": result.enters,
        "exits": result.exits,
        "bank_menu_m": list(BANK_MENU_M),
        "club_max_allowed": list(CLUB_MAX_ALLOWED),
    }


def solve_preference_pair(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    prefs: Preferences | None = None,
    *,
    strategy: str = PRODUCTION["strategy"],
) -> PreferenceResult:
    """Solve S1; if prefs non-empty, re-solve S2 under hard cuts only."""
    prefs = prefs or Preferences()
    validate_preferences(prefs)
    by_id = {p.player.id: p for p in projections}
    model = {
        "minutes_version": PRODUCTION["minutes_version"],
        "rates_version": PRODUCTION["rates_version"],
        "fixtures_version": "v1",
        "strategy": strategy,
        "objective": OBJECTIVE,
        "horizon": PRODUCTION["horizon_resolv"],
        "role": "model_a",
    }
    s1_sol = solve_squad(
        snapshot, projections, strategy=strategy, objective=OBJECTIVE
    )
    s1 = _view(s1_sol, by_id)

    if prefs.empty():
        return PreferenceResult(
            feasible=True,
            message=None,
            preferences=prefs,
            s1=s1,
            s2=None,
            delta_u=None,
            distance=None,
            enters=[],
            exits=[],
            model=model,
        )

    try:
        s2_sol = solve_squad(
            snapshot,
            projections,
            strategy=strategy,
            objective=OBJECTIVE,
            must_include=set(prefs.lock),
            must_exclude=set(prefs.ban),
            min_bank=prefs.min_bank_tenths(),
            club_limits=dict(prefs.club_max) or None,
        )
    except SquadInfeasibleError as exc:
        return PreferenceResult(
            feasible=False,
            message=f"No feasible squad under these constraints ({exc})",
            preferences=prefs,
            s1=s1,
            s2=None,
            delta_u=None,
            distance=None,
            enters=[],
            exits=[],
            model=model,
        )
    except ValueError as exc:
        return PreferenceResult(
            feasible=False,
            message=f"Invalid preferences ({exc})",
            preferences=prefs,
            s1=s1,
            s2=None,
            delta_u=None,
            distance=None,
            enters=[],
            exits=[],
            model=model,
        )
    except SquadSolverError as exc:
        return PreferenceResult(
            feasible=False,
            message=f"Squad solver error — not a preference infeasibility ({exc})",
            preferences=prefs,
            s1=s1,
            s2=None,
            delta_u=None,
            distance=None,
            enters=[],
            exits=[],
            model=model,
        )

    s2 = _view(s2_sol, by_id)
    diag = diagnose(s2_sol, rank=2, s1=s1_sol, by_id=by_id, objective=OBJECTIVE)
    return PreferenceResult(
        feasible=True,
        message=None,
        preferences=prefs,
        s1=s1,
        s2=s2,
        delta_u=diag.delta_u,
        distance=diag.distance,
        enters=list(diag.enters),
        exits=list(diag.exits),
        model=model,
    )
