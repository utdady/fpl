"""Transfer suggestions from an owned 15. Not V5/V7 — myopic next-GW search.

Product helper (not an E-card): Hamming-k ILP on the current squad (selling
Hamming-k ILP on the current squad (selling prices + bank), then score with
solve_xi + captain-by-xP (highest next_mu in the XI).

This is a next-GW FT-spending optimizer: it finds the highest projected
XI+C plan given available free transfers. It does not decide whether banking
FTs is wiser. Default allow_hit=False; hits are an explicit aggressive option.

Search and ranking use the same scalar: next_utility (strategy-aware).
Displayed next_xi_mu is informational (points-shaped μ), not the rank key.

Candidate enumeration is diversified (exclude prior ins), not global top-N.
"""
from __future__ import annotations

import pickle
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field, replace
from typing import Any

import pulp

from engine.api import CACHE_DIR
from engine.model_config import PRODUCTION
from engine.models import Player, PlayerProjection, Snapshot
from engine.optimize import BENCH_WEIGHT, solve_squad, solve_xi
from engine.project import project_all

SOURCE = (
    f"minutes={PRODUCTION['minutes_version']} rates={PRODUCTION['rates_version']} "
    "strategy={strategy} objective=next_utility"
)
PROJ_TTL_S = 1800

MODE_NORMAL = "NORMAL_TRANSFER"
MODE_WILDCARD = "WILDCARD"
MODE_FREE_HIT = "FREE_HIT"

OBJECTIVE_NEXT = "next-GW XI+C next_utility − hits"
SQUAD_OBJECTIVE_HORIZON = "horizon utility"


@dataclass
class SquadState:
    owned_ids: list[int]
    selling: dict[int, int]
    bank: int
    ft: int
    hit_cost: int
    value: int
    wc_active: bool
    chip_mode: str | None  # "wildcard" | "freehit" | None


@dataclass
class TransferMove:
    out_id: int
    out_name: str
    in_id: int
    in_name: str
    pos: str
    selling_price: int
    purchase_price: int


@dataclass
class MinutesFlag:
    id: int
    name: str
    pos: str
    p_start: float
    mu: float
    utility: float


@dataclass
class TransferPlan:
    k: int
    hit: int
    next_xi_mu: float
    next_xi_utility: float
    score: float
    delta: float
    bank: int
    captain: str
    vice: str
    captain_id: int
    vice_id: int
    captain_mu: float
    captain_utility: float
    captain_p_start: float
    captain_pos: str
    moves: list[TransferMove]
    xi_ids: list[int]
    incoming_ids: list[int]
    outgoing_ids: list[int]
    # XI players with low P(start) — premiums can look "uncaptainable" when suppressed.
    minutes_flags: list[MinutesFlag] = field(default_factory=list)


@dataclass
class SuggestResult:
    source: str
    strategy: str
    next_gw: int
    mode: str
    objective: str
    squad_objective: str | None
    displayed_payoff: str
    diversify_n: int
    roll_utility: float
    roll_mu: float
    plans: list[TransferPlan] = field(default_factory=list)


def parse_my_team(data: dict[str, Any]) -> SquadState:
    picks = data.get("picks") or []
    if len(picks) != 15:
        raise ValueError(f"squad JSON must have 15 picks; got {len(picks)}")
    tr = data.get("transfers") or {}
    chips = data.get("chips") or []
    chip_mode = None
    for c in chips:
        if not isinstance(c, dict):
            continue
        name = c.get("name")
        if name in {"wildcard", "freehit"} and c.get("status_for_entry") == "active":
            chip_mode = name
            break
    wc_active = chip_mode is not None
    limit = tr.get("limit")
    made = int(tr.get("made") or 0)
    cap = int(limit) if limit is not None else 1
    ft = 10**9 if wc_active else max(0, cap - made)
    return SquadState(
        owned_ids=[int(p["element"]) for p in picks],
        selling={int(p["element"]): int(p["selling_price"]) for p in picks},
        bank=int(tr.get("bank") or 0),
        ft=ft,
        hit_cost=int(tr.get("cost") or 4),
        value=int(tr.get("value") or 0),
        wc_active=wc_active,
        chip_mode=chip_mode,
    )


def result_to_json(result: SuggestResult) -> dict[str, Any]:
    return {
        "source": result.source,
        "strategy": result.strategy,
        "next_gw": result.next_gw,
        "mode": result.mode,
        "objective": result.objective,
        "squad_objective": result.squad_objective,
        "displayed_payoff": result.displayed_payoff,
        "diversify_n": result.diversify_n,
        "roll_utility": round(result.roll_utility, 4),
        "roll_mu": round(result.roll_mu, 4),
        "plans": [
            {
                "k": p.k,
                "hit": p.hit,
                "next_xi_mu": round(p.next_xi_mu, 4),
                "next_xi_utility": round(p.next_xi_utility, 4),
                "score": round(p.score, 4),
                "delta": round(p.delta, 4),
                # Compat alias: same as delta (utility − hit vs roll).
                "delta_mu": round(p.delta, 4),
                "bank": p.bank,
                "captain": p.captain,
                "vice": p.vice,
                "captain_id": p.captain_id,
                "vice_id": p.vice_id,
                "captain_mu": round(p.captain_mu, 4),
                "captain_utility": round(p.captain_utility, 4),
                "captain_p_start": round(p.captain_p_start, 4),
                "captain_pos": p.captain_pos,
                "xi_ids": p.xi_ids,
                "incoming_ids": p.incoming_ids,
                "outgoing_ids": p.outgoing_ids,
                "minutes_flags": [
                    {
                        "id": f.id,
                        "name": f.name,
                        "pos": f.pos,
                        "p_start": round(f.p_start, 4),
                        "mu": round(f.mu, 4),
                        "utility": round(f.utility, 4),
                    }
                    for f in p.minutes_flags
                ],
                "moves": [asdict(m) for m in p.moves],
            }
            for p in result.plans
        ],
    }


def cached_project_all(
    snapshot: Snapshot,
    *,
    strategy: str,
    horizon: int,
    seed: int = 7,
    refresh: bool = False,
) -> list[PlayerProjection]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    minutes = PRODUCTION["minutes_version"]
    rates = PRODUCTION["rates_version"]
    path = CACHE_DIR / f"proj_{strategy}_h{horizon}_{minutes}_{rates}_s{seed}.pkl"
    as_of = snapshot.as_of.isoformat()
    if (
        not refresh
        and path.exists()
        and (time.time() - path.stat().st_mtime) < PROJ_TTL_S
    ):
        payload = pickle.loads(path.read_bytes())
        if payload.get("as_of") == as_of:
            return _rehydrate(snapshot, payload["rows"])
    projections = project_all(
        snapshot,
        horizon=horizon,
        strategy=strategy,
        seed=seed,
        minutes_version=minutes,
        rates_version=rates,
    )
    rows = {
        proj.player.id: {
            "next_mu": proj.next_mu,
            "next_sigma": proj.next_sigma,
            "next_p_start": proj.next_p_start,
            "next_p_60": proj.next_p_60,
            "next_p_10": proj.next_p_10,
            "next_utility": proj.next_utility,
            "horizon_mu": proj.horizon_mu,
            "horizon_sigma": proj.horizon_sigma,
            "horizon_utility": proj.horizon_utility,
        }
        for proj in projections
    }
    path.write_bytes(pickle.dumps({"as_of": as_of, "rows": rows}))
    return projections


def _rehydrate(snapshot: Snapshot, rows: dict[int, dict[str, float]]) -> list[PlayerProjection]:
    by_id = {p.id: p for p in snapshot.players}
    out: list[PlayerProjection] = []
    for pid, row in rows.items():
        player = by_id.get(int(pid))
        if player is None:
            continue
        out.append(
            PlayerProjection(
                player=player,
                by_gw={},
                horizon_mu=row["horizon_mu"],
                horizon_sigma=row["horizon_sigma"],
                horizon_utility=row["horizon_utility"],
                next_mu=row["next_mu"],
                next_sigma=row["next_sigma"],
                next_p_start=row["next_p_start"],
                next_p_60=row["next_p_60"],
                next_p_10=row["next_p_10"],
                next_utility=row["next_utility"],
            )
        )
    return out


def suggest_from_payload(
    payload: dict[str, Any],
    *,
    snapshot: Snapshot,
    strategy: str = PRODUCTION["strategy"],
    horizon: int = PRODUCTION["horizon_resolv"],
    seed: int = 7,
    refresh: bool = False,
    allow_hit: bool = False,
    diversify_n: int = 3,
) -> SuggestResult:
    state = parse_my_team(payload)
    projections = cached_project_all(
        snapshot, strategy=strategy, horizon=horizon, seed=seed, refresh=refresh
    )
    return suggest_transfers(
        snapshot,
        projections,
        state,
        strategy=strategy,
        allow_hit=allow_hit,
        diversify_n=diversify_n,
    )


def suggest_transfers(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    state: SquadState,
    *,
    strategy: str = PRODUCTION["strategy"],
    allow_hit: bool = False,
    diversify_n: int = 3,
    top_n: int | None = None,
) -> SuggestResult:
    """Rank diversified Hamming-k transfer plans. `top_n` is a deprecated alias for diversify_n."""
    if top_n is not None:
        diversify_n = top_n
    by_id = {p.player.id: p for p in projections}
    players = {p.id: p for p in snapshot.players}
    missing_snap = [i for i in state.owned_ids if i not in players]
    if missing_snap:
        raise RuntimeError(f"owned ids not in snapshot: {missing_snap}")
    missing_proj = [i for i in state.owned_ids if i not in by_id]
    if missing_proj:
        raise RuntimeError(
            "owned players missing projections — refusing to invent transfer "
            f"incentives: {missing_proj}"
        )

    next_gw = snapshot.next_event().id
    source = SOURCE.format(strategy=strategy)
    owned = [players[i] for i in state.owned_ids]

    if state.wc_active:
        mode = MODE_FREE_HIT if state.chip_mode == "freehit" else MODE_WILDCARD
        plan, chosen = _wildcard_plan(snapshot, projections, by_id, state, strategy)
        roll_u, roll_mu, _, _, _, _ = _score_squad(snapshot, owned, by_id)
        plan.delta = plan.score - roll_u
        _assert_plan_invariants(snapshot, owned, plan, chosen=chosen)
        return SuggestResult(
            source=source,
            strategy=strategy,
            next_gw=next_gw,
            mode=mode,
            objective=OBJECTIVE_NEXT,
            squad_objective=SQUAD_OBJECTIVE_HORIZON,
            displayed_payoff=OBJECTIVE_NEXT,
            diversify_n=diversify_n,
            roll_utility=roll_u,
            roll_mu=roll_mu,
            plans=[plan],
        )

    roll = _plan_from_squad(snapshot, owned, by_id, state, k=0, hit=0)
    _assert_plan_invariants(snapshot, owned, roll, chosen=owned)
    plans = [roll]
    k_max = state.ft + (1 if allow_hit else 0)
    k_max = min(k_max, snapshot.squad.squad_size)
    for k in range(1, k_max + 1):
        excluded: set[int] = set()
        for _ in range(diversify_n):
            chosen = _solve_k(
                snapshot,
                by_id,
                players,
                state,
                k=k,
                must_exclude=excluded,
            )
            if chosen is None:
                break
            ins = {p.id for p in chosen} - set(state.owned_ids)
            if not ins:
                break
            extra = max(0, k - state.ft)
            hit = extra * state.hit_cost
            plan = _plan_from_squad(snapshot, chosen, by_id, state, k=k, hit=hit)
            _assert_plan_invariants(snapshot, owned, plan, chosen=chosen)
            plans.append(plan)
            excluded |= ins
    for p in plans:
        p.delta = p.score - roll.score
    plans.sort(key=lambda p: (-p.score, p.k, p.hit))
    return SuggestResult(
        source=source,
        strategy=strategy,
        next_gw=next_gw,
        mode=MODE_NORMAL,
        objective=OBJECTIVE_NEXT,
        squad_objective=None,
        displayed_payoff=OBJECTIVE_NEXT,
        diversify_n=diversify_n,
        roll_utility=roll.next_xi_utility,
        roll_mu=roll.next_xi_mu,
        plans=plans,
    )


def squad_composition_legal(snapshot: Snapshot, squad: list[Player]) -> bool:
    """Position + club + size. Does not use greenfield £100m / now_cost budget."""
    rules = snapshot.squad
    if len(squad) != rules.squad_size:
        return False
    if len({p.id for p in squad}) != rules.squad_size:
        return False
    pos: dict[str, int] = defaultdict(int)
    team: dict[int, int] = defaultdict(int)
    for p in squad:
        pos[p.position] += 1
        team[p.team_id] += 1
    for pcode, n in rules.squad_select.items():
        if pos.get(pcode, 0) != n:
            return False
    for c in team.values():
        if c > rules.team_limit:
            return False
    return True


def _assert_plan_invariants(
    snapshot: Snapshot,
    owned: list[Player],
    plan: TransferPlan,
    *,
    chosen: list[Player],
) -> None:
    old = {p.id for p in owned}
    new = {p.id for p in chosen}

    incoming = sorted(new - old)
    outgoing = sorted(old - new)
    if set(incoming) != set(plan.incoming_ids):
        raise RuntimeError(
            f"incoming mismatch: set={incoming} plan={plan.incoming_ids}"
        )
    if set(outgoing) != set(plan.outgoing_ids):
        raise RuntimeError(
            f"outgoing mismatch: set={outgoing} plan={plan.outgoing_ids}"
        )
    if len(incoming) != plan.k or len(outgoing) != plan.k:
        raise RuntimeError(
            f"k invariant failed: k={plan.k} |in|={len(incoming)} |out|={len(outgoing)}"
        )
    if set(incoming) & set(outgoing):
        raise RuntimeError(f"player both in and out: {set(incoming) & set(outgoing)}")
    rebuilt = (old - set(outgoing)) | set(incoming)
    if rebuilt != new:
        raise RuntimeError("final squad != old - outgoing + incoming")
    if not squad_composition_legal(snapshot, chosen):
        raise RuntimeError("final squad fails composition/club legality")
    if plan.bank < 0:
        raise RuntimeError(f"negative bank after transfers: {plan.bank}")
    if len(plan.moves) != plan.k:
        raise RuntimeError(
            f"display moves length {len(plan.moves)} != k={plan.k} "
            "(pairing is cosmetic but must cover the transfer set)"
        )
    move_ins = {m.in_id for m in plan.moves}
    move_outs = {m.out_id for m in plan.moves}
    if move_ins != set(incoming) or move_outs != set(outgoing):
        raise RuntimeError("display moves do not match incoming/outgoing sets")


LOW_P_START = 0.50


def _pick_captains_by_xp(
    xi: list[Player],
    by_id: dict[int, PlayerProjection],
) -> tuple[Player, Player]:
    """Suggest captain by highest next_mu (xP) in the XI — product display/score for suggest."""
    ranked = sorted(xi, key=lambda p: by_id[p.id].next_mu, reverse=True)
    captain = ranked[0]
    rest = [p for p in ranked if p.id != captain.id]
    vice = max(rest, key=lambda p: by_id[p.id].next_p_start * by_id[p.id].next_mu)
    return captain, vice


def _minutes_flags(
    xi: list[Player],
    by_id: dict[int, PlayerProjection],
) -> list[MinutesFlag]:
    flags: list[MinutesFlag] = []
    for p in xi:
        proj = by_id[p.id]
        if proj.next_p_start >= LOW_P_START:
            continue
        flags.append(
            MinutesFlag(
                id=p.id,
                name=p.web_name,
                pos=p.position,
                p_start=proj.next_p_start,
                mu=proj.next_mu,
                utility=proj.next_utility,
            )
        )
    flags.sort(key=lambda f: (f.p_start, -f.mu))
    return flags


def _score_squad(
    snapshot: Snapshot,
    squad: list[Player],
    by_id: dict[int, PlayerProjection],
) -> tuple[float, float, Player, Player, list[int], list[MinutesFlag]]:
    """Return (next_xi_utility, next_xi_mu, captain, vice, xi_ids, minutes_flags).

    Captain is chosen by next_mu (xP), matching the product expectation that C = highest
    projected points in the XI. Score still doubles that captain's utility for ranking.
    """
    xi, _bench = solve_xi(snapshot, squad, by_id)
    captain, vice = _pick_captains_by_xp(xi, by_id)
    util = sum(by_id[p.id].next_utility for p in xi) + by_id[captain.id].next_utility
    mu = sum(by_id[p.id].next_mu for p in xi) + by_id[captain.id].next_mu
    return util, mu, captain, vice, [p.id for p in xi], _minutes_flags(xi, by_id)


def _remaining_bank(state: SquadState, chosen: list[Player]) -> int:
    new_ids = {p.id for p in chosen}
    sold = sum(state.selling[i] for i in state.owned_ids if i not in new_ids)
    bought = sum(p.now_cost for p in chosen if p.id not in set(state.owned_ids))
    return state.bank + sold - bought


def _pair_moves(
    owned: list[Player],
    chosen: list[Player],
    state: SquadState,
) -> list[TransferMove]:
    """Cosmetic display pairing of the transfer set — not an optimization step."""
    old_ids = {p.id for p in owned}
    new_ids = {p.id for p in chosen}
    outs = [p for p in owned if p.id not in new_ids]
    ins = [p for p in chosen if p.id not in old_ids]
    used_in: set[int] = set()
    used_out: set[int] = set()
    moves: list[TransferMove] = []

    def add(out_p: Player, in_p: Player) -> None:
        pos = out_p.position if out_p.position == in_p.position else f"{out_p.position}->{in_p.position}"
        moves.append(
            TransferMove(
                out_id=out_p.id,
                out_name=out_p.web_name,
                in_id=in_p.id,
                in_name=in_p.web_name,
                pos=pos,
                selling_price=state.selling[out_p.id],
                purchase_price=in_p.now_cost,
            )
        )
        used_out.add(out_p.id)
        used_in.add(in_p.id)

    for out_p in outs:
        match = next((i for i in ins if i.position == out_p.position and i.id not in used_in), None)
        if match is not None:
            add(out_p, match)
    leftover_outs = [p for p in outs if p.id not in used_out]
    leftover_ins = [p for p in ins if p.id not in used_in]
    for out_p, in_p in zip(leftover_outs, leftover_ins):
        add(out_p, in_p)
    return moves


def _plan_from_squad(
    snapshot: Snapshot,
    chosen: list[Player],
    by_id: dict[int, PlayerProjection],
    state: SquadState,
    *,
    k: int,
    hit: int,
) -> TransferPlan:
    owned = [next(p for p in snapshot.players if p.id == i) for i in state.owned_ids]
    util, mu, captain, vice, xi_ids, minutes_flags = _score_squad(snapshot, chosen, by_id)
    old = {p.id for p in owned}
    new = {p.id for p in chosen}
    incoming = sorted(new - old)
    outgoing = sorted(old - new)
    cap_proj = by_id[captain.id]
    return TransferPlan(
        k=k,
        hit=hit,
        next_xi_mu=mu,
        next_xi_utility=util,
        score=util - hit,
        delta=0.0,
        bank=_remaining_bank(state, chosen),
        captain=captain.web_name,
        vice=vice.web_name,
        captain_id=captain.id,
        vice_id=vice.id,
        captain_mu=cap_proj.next_mu,
        captain_utility=cap_proj.next_utility,
        captain_p_start=cap_proj.next_p_start,
        captain_pos=captain.position,
        moves=_pair_moves(owned, chosen, state),
        xi_ids=xi_ids,
        incoming_ids=incoming,
        outgoing_ids=outgoing,
        minutes_flags=minutes_flags,
    )


def _wildcard_plan(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    by_id: dict[int, PlayerProjection],
    state: SquadState,
    strategy: str,
) -> tuple[TransferPlan, list[Player]]:
    budget = max(state.value + state.bank, 1)
    snap = replace(snapshot, squad=replace(snapshot.squad, budget=budget))
    sol = solve_squad(snap, projections, strategy=strategy, objective="horizon")
    k = len({p.id for p in sol.players} - set(state.owned_ids))
    plan = _plan_from_squad(snapshot, sol.players, by_id, state, k=k, hit=0)
    return plan, sol.players


def _eligible(
    snapshot: Snapshot,
    by_id: dict[int, PlayerProjection],
    owned_ids: set[int],
    must_exclude: set[int],
) -> list[Player]:
    out: list[Player] = []
    for p in snapshot.players:
        if p.id not in by_id:
            continue
        if p.id in must_exclude and p.id not in owned_ids:
            continue
        if p.id in owned_ids:
            out.append(p)
            continue
        if not p.can_select:
            continue
        if by_id[p.id].next_utility <= -20:
            continue
        out.append(p)
    return out


def _solve_k(
    snapshot: Snapshot,
    by_id: dict[int, PlayerProjection],
    players: dict[int, Player],
    state: SquadState,
    *,
    k: int,
    must_exclude: set[int],
) -> list[Player] | None:
    rules = snapshot.squad
    owned_ids = set(state.owned_ids)
    eligible = _eligible(snapshot, by_id, owned_ids, must_exclude)
    ids = [p.id for p in eligible]
    owned_in = [i for i in state.owned_ids if i in ids]
    if len(owned_in) != len(state.owned_ids):
        return None
    if k > len(ids) - len(owned_in):
        return None

    cost = {p.id: p.now_cost for p in eligible}
    pos = {p.id: p.position for p in eligible}
    team = {p.id: p.team_id for p in eligible}
    util = {p.id: by_id[p.id].next_utility for p in eligible}
    sell = state.selling

    prob = pulp.LpProblem(f"fpl_xfer_{k}", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("x", ids, 0, 1, pulp.LpInteger)
    s = pulp.LpVariable.dicts("s", ids, 0, 1, pulp.LpInteger)
    # Same scalar as ranking: next_utility (strategy-aware).
    prob += pulp.lpSum(
        util[i] * (BENCH_WEIGHT * x[i] + (1.0 - BENCH_WEIGHT) * s[i]) for i in ids
    )
    for i in ids:
        prob += s[i] <= x[i]
    prob += pulp.lpSum(x[i] for i in ids) == rules.squad_size
    prob += pulp.lpSum(s[i] for i in ids) == rules.squad_play
    prob += pulp.lpSum(x[i] for i in owned_in) == len(owned_in) - k
    prob += pulp.lpSum(x[i] for i in ids if i not in owned_ids) == k
    buy = pulp.lpSum(cost[i] * x[i] for i in ids if i not in owned_ids)
    gain = pulp.lpSum(sell[i] * (1 - x[i]) for i in owned_in)
    prob += buy <= state.bank + gain
    for pcode, n in rules.squad_select.items():
        prob += pulp.lpSum(x[i] for i in ids if pos[i] == pcode) == n, f"squad_{pcode}"
    for pcode in rules.min_play:
        n_start = pulp.lpSum(s[i] for i in ids if pos[i] == pcode)
        prob += n_start >= rules.min_play[pcode], f"min_{pcode}"
        prob += n_start <= rules.max_play[pcode], f"max_{pcode}"
    for tid in {team[i] for i in ids}:
        prob += pulp.lpSum(x[i] for i in ids if team[i] == tid) <= rules.team_limit, f"club_{tid}"
    for i in must_exclude:
        if i in ids and i not in owned_ids:
            prob += x[i] == 0, f"excl_{i}"

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=15))
    status_name = pulp.LpStatus[status]
    chosen_ids = [i for i in ids if x[i].value() and x[i].value() > 0.5]
    # Proven optimum only — do not treat timed-out incumbents as "highest".
    if status_name != "Optimal" or len(chosen_ids) != rules.squad_size:
        return None
    return [players[i] for i in chosen_ids]
