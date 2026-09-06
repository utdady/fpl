"""Transfer suggestions from an owned 15. Not V5/V7 — myopic next-GW search.

Hamming-k ILP on the current squad (selling prices + bank), then score with
solve_xi + pick_captains. Rank by next-GW XI+C μ minus hit.
"""
from __future__ import annotations

import json
import pickle
import time
from dataclasses import asdict, dataclass, field, replace
from typing import Any

import pulp

from engine.api import CACHE_DIR
from engine.model_config import PRODUCTION
from engine.models import Player, PlayerProjection, Snapshot
from engine.optimize import BENCH_WEIGHT, pick_captains, solve_squad, solve_xi
from engine.project import project_all

SOURCE = (
    f"minutes={PRODUCTION['minutes_version']} rates={PRODUCTION['rates_version']} "
    "strategy={strategy} objective=next"
)
PROJ_TTL_S = 1800


@dataclass
class SquadState:
    owned_ids: list[int]
    selling: dict[int, int]
    bank: int
    ft: int
    hit_cost: int
    value: int
    wc_active: bool


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
class TransferPlan:
    k: int
    hit: int
    next_xi_mu: float
    score: float
    delta_mu: float
    bank: int
    captain: str
    vice: str
    captain_id: int
    vice_id: int
    moves: list[TransferMove]
    xi_ids: list[int]


@dataclass
class SuggestResult:
    source: str
    strategy: str
    next_gw: int
    roll_mu: float
    plans: list[TransferPlan] = field(default_factory=list)


def parse_my_team(data: dict[str, Any]) -> SquadState:
    picks = data.get("picks") or []
    if len(picks) != 15:
        raise ValueError(f"squad JSON must have 15 picks; got {len(picks)}")
    tr = data.get("transfers") or {}
    chips = data.get("chips") or []
    wc_active = any(
        (c.get("name") in {"wildcard", "freehit"})
        and c.get("status_for_entry") == "active"
        for c in chips
        if isinstance(c, dict)
    )
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
    )


def result_to_json(result: SuggestResult) -> dict[str, Any]:
    return {
        "source": result.source,
        "strategy": result.strategy,
        "next_gw": result.next_gw,
        "roll_mu": round(result.roll_mu, 4),
        "plans": [
            {
                "k": p.k,
                "hit": p.hit,
                "next_xi_mu": round(p.next_xi_mu, 4),
                "score": round(p.score, 4),
                "delta_mu": round(p.delta_mu, 4),
                "bank": p.bank,
                "captain": p.captain,
                "vice": p.vice,
                "captain_id": p.captain_id,
                "vice_id": p.vice_id,
                "xi_ids": p.xi_ids,
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
    top_n: int = 3,
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
        top_n=top_n,
    )


def suggest_transfers(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    state: SquadState,
    *,
    strategy: str = PRODUCTION["strategy"],
    allow_hit: bool = False,
    top_n: int = 3,
) -> SuggestResult:
    by_id = {p.player.id: p for p in projections}
    players = {p.id: p for p in snapshot.players}
    missing = [i for i in state.owned_ids if i not in players]
    if missing:
        raise RuntimeError(f"owned ids not in snapshot: {missing}")
    for pid in state.owned_ids:
        if pid not in by_id:
            p = players[pid]
            by_id[pid] = PlayerProjection(
                player=p,
                by_gw={},
                horizon_mu=-50.0,
                horizon_sigma=0.0,
                horizon_utility=-50.0,
                next_mu=-50.0,
                next_sigma=0.0,
                next_p_start=0.0,
                next_p_60=0.0,
                next_p_10=0.0,
                next_utility=-50.0,
            )
    next_gw = snapshot.next_event().id
    source = SOURCE.format(strategy=strategy)
    owned = [players[i] for i in state.owned_ids]

    if state.wc_active:
        plan = _wildcard_plan(snapshot, projections, by_id, state, strategy)
        roll_mu = plan.next_xi_mu if plan.k == 0 else _score_squad(snapshot, owned, by_id)[0]
        if plan.k != 0:
            plan.delta_mu = plan.score - roll_mu
        return SuggestResult(
            source=source,
            strategy=strategy,
            next_gw=next_gw,
            roll_mu=roll_mu,
            plans=[plan],
        )

    roll = _plan_from_squad(snapshot, owned, by_id, state, k=0, hit=0)
    plans = [roll]
    k_max = state.ft + (1 if allow_hit else 0)
    k_max = min(k_max, snapshot.squad.squad_size)
    for k in range(1, k_max + 1):
        excluded: set[int] = set()
        for _ in range(top_n):
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
            plans.append(_plan_from_squad(snapshot, chosen, by_id, state, k=k, hit=hit))
            excluded |= ins
    for p in plans:
        p.delta_mu = p.score - roll.score
    plans.sort(key=lambda p: (-p.score, p.k, p.hit))
    return SuggestResult(
        source=source,
        strategy=strategy,
        next_gw=next_gw,
        roll_mu=roll.next_xi_mu,
        plans=plans,
    )


def _score_squad(
    snapshot: Snapshot,
    squad: list[Player],
    by_id: dict[int, PlayerProjection],
) -> tuple[float, Player, Player, list[int]]:
    xi, _bench = solve_xi(snapshot, squad, by_id)
    captain, vice = pick_captains(xi, by_id)
    mu = sum(by_id[p.id].next_mu for p in xi) + by_id[captain.id].next_mu
    return mu, captain, vice, [p.id for p in xi]


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
    old_ids = {p.id for p in owned}
    new_ids = {p.id for p in chosen}
    by_new = {p.id: p for p in chosen}
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
    mu, captain, vice, xi_ids = _score_squad(snapshot, chosen, by_id)
    return TransferPlan(
        k=k,
        hit=hit,
        next_xi_mu=mu,
        score=mu - hit,
        delta_mu=0.0,
        bank=_remaining_bank(state, chosen),
        captain=captain.web_name,
        vice=vice.web_name,
        captain_id=captain.id,
        vice_id=vice.id,
        moves=_pair_moves(owned, chosen, state),
        xi_ids=xi_ids,
    )


def _wildcard_plan(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    by_id: dict[int, PlayerProjection],
    state: SquadState,
    strategy: str,
) -> TransferPlan:
    budget = max(state.value + state.bank, 1)
    snap = replace(snapshot, squad=replace(snapshot.squad, budget=budget))
    sol = solve_squad(snap, projections, strategy=strategy, objective="horizon")
    k = len({p.id for p in sol.players} - set(state.owned_ids))
    return _plan_from_squad(snapshot, sol.players, by_id, state, k=k, hit=0)


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
    chosen_ids = [i for i in ids if x[i].value() and x[i].value() > 0.5]
    if len(chosen_ids) != rules.squad_size:
        return None
    if pulp.LpStatus[status] not in {"Optimal", "Not Solved"}:
        # CBC may return Not Solved with a feasible incumbent; still require size.
        if len(chosen_ids) != rules.squad_size:
            return None
    return [players[i] for i in chosen_ids]
