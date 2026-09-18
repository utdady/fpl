"""Product smoke: transfer helper vs roll vs naive one-swap (historical replay).

NOT an E-card. NOT a promote gate. Descriptive confidence only.

Frozen policy (documented, not pre-registered research):
  - Production projections: minutes=v2am_s, rates=v1, fixtures=v1, strategy=balanced
  - GW1: greenfield solve_squad (horizon), Cap on that XI+C; no transfers
  - GW2+: each arm maintains its own 15 / bank / FT
  - Selling prices approximated by as-of-T now_cost (no purchase history)
  - FT: start 1 after GW1; each GW gain +1 up to max_ft=2 before acting; spend k
  - Primary condition: allow_hit=False (k ≤ FT only)
  - Optional --allow-hit: separate condition (FT+1 with −4)

Arms:
  helper  — engine.suggest.suggest_transfers; take best plan (diversify_n=1)
  roll    — no transfers
  naive   — at most one same-position swap maximizing Δ next_mu if FT≥1 and affordable

Payoff: realized Cap (XI pts + captain) from gw_actuals; hits reported separately;
net = Cap − hits.

Usage:
    python scripts/product_transfer_replay.py --season 2022-23 --to-gw 8
    python scripts/product_transfer_replay.py --season 2022-23 --allow-hit --to-gw 8
    python scripts/product_transfer_replay.py --all-seasons --to-gw 38
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.harness import (
    SUPPORTED_SEASONS,
    build_snapshot,
    ensure_vaastav,
    gw_actuals,
)
from engine.model_config import PRODUCTION
from engine.models import Player, PlayerProjection, Snapshot
from engine.optimize import pick_captains, solve_squad, solve_xi
from engine.project import project_all
from engine.suggest import SquadState, suggest_transfers

OUT_GW = Path("records") / "historical" / "product_transfer_replay_gw.csv"
OUT_SEASON = Path("records") / "historical" / "product_transfer_replay_season.csv"
OUT_TXT = Path("records") / "historical" / "product_transfer_replay_summary.txt"

SEED = 7
STRATEGY = PRODUCTION["strategy"]
MINUTES = PRODUCTION["minutes_version"]
RATES = PRODUCTION["rates_version"]
HIT_COST = 4
MAX_FT = 2
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}
ARMS = ("helper", "roll", "naive")


@dataclass
class ArmState:
    ids: list[int]
    bank: int
    ft: int  # available before this GW's decision


def _pts(act: dict, pid: int) -> float:
    return float(act.get(pid, {}).get("actual_points", 0) or 0)


def cap_points(xi: list[Player], captain: Player, act: dict) -> float:
    return sum(_pts(act, p.id) for p in xi) + _pts(act, captain.id)


def project_gw(season: str, gw: int) -> tuple[Snapshot, dict, list[PlayerProjection], dict[int, PlayerProjection]] | None:
    snap = build_snapshot(season, as_of_gw=gw)
    act = gw_actuals(season, gw)
    if not act:
        return None
    projs = project_all(
        snap,
        horizon=1,
        strategy=STRATEGY,
        seed=SEED,
        minutes_version=MINUTES,
        rates_version=RATES,
        fixtures_version="v1",
    )
    by_id = {p.player.id: p for p in projs}
    return snap, act, projs, by_id


def resolve_squad(snap: Snapshot, ids: list[int]) -> list[Player] | None:
    by = {p.id: p for p in snap.players}
    if any(i not in by for i in ids):
        return None
    return [by[i] for i in ids]


def score_owned(
    snap: Snapshot,
    owned: list[Player],
    by_id: dict[int, PlayerProjection],
    act: dict,
) -> tuple[float, str] | None:
    try:
        missing = [p.id for p in owned if p.id not in by_id]
        if missing:
            return None
        xi, _ = solve_xi(snap, owned, by_id)
        captain, _ = pick_captains(xi, by_id)
    except RuntimeError:
        return None
    return cap_points(xi, captain, act), captain.web_name


def apply_ids(old_ids: list[int], outgoing: list[int], incoming: list[int]) -> list[int]:
    out_s = set(outgoing)
    kept = [i for i in old_ids if i not in out_s]
    return kept + list(incoming)


def club_ok_after_swap(
    owned: list[Player],
    out_p: Player,
    cand: Player,
    team_limit: int,
) -> bool:
    teams: dict[int, int] = defaultdict(int)
    for p in owned:
        tid = cand.team_id if p.id == out_p.id else p.team_id
        teams[tid] += 1
        if teams[tid] > team_limit:
            return False
    return True


def naive_one_swap(
    snap: Snapshot,
    owned: list[Player],
    by_id: dict[int, PlayerProjection],
    bank: int,
    ft: int,
) -> tuple[list[int], int, int, int]:
    """Return (new_ids, new_bank, k, hit). At most one same-pos swap by max Δ next_mu."""
    if ft < 1:
        return [p.id for p in owned], bank, 0, 0
    owned_ids = {p.id for p in owned}
    best: tuple[float, Player, Player] | None = None
    for out_p in owned:
        if out_p.id not in by_id:
            continue
        for cand in snap.players:
            if cand.id in owned_ids or cand.position != out_p.position:
                continue
            if not cand.can_select or cand.id not in by_id:
                continue
            if by_id[cand.id].next_utility <= -20:
                continue
            next_bank = bank + out_p.now_cost - cand.now_cost
            if next_bank < 0:
                continue
            if not club_ok_after_swap(owned, out_p, cand, snap.squad.team_limit):
                continue
            delta = by_id[cand.id].next_mu - by_id[out_p.id].next_mu
            if best is None or delta > best[0]:
                best = (delta, out_p, cand)
    if best is None or best[0] <= 0:
        return [p.id for p in owned], bank, 0, 0
    _delta, out_p, cand = best
    new_ids = apply_ids([p.id for p in owned], [out_p.id], [cand.id])
    new_bank = bank + out_p.now_cost - cand.now_cost
    return new_ids, new_bank, 1, 0


def helper_decision(
    snap: Snapshot,
    projs: list[PlayerProjection],
    owned: list[Player],
    bank: int,
    ft: int,
    allow_hit: bool,
) -> tuple[list[int], int, int, int]:
    """Return (new_ids, new_bank, k, hit)."""
    state = SquadState(
        owned_ids=[p.id for p in owned],
        selling={p.id: p.now_cost for p in owned},
        bank=bank,
        ft=ft,
        hit_cost=HIT_COST,
        value=sum(p.now_cost for p in owned),
        wc_active=False,
        chip_mode=None,
    )
    try:
        result = suggest_transfers(
            snap,
            projs,
            state,
            strategy=STRATEGY,
            allow_hit=allow_hit,
            diversify_n=1,
        )
    except RuntimeError as exc:
        print(f"  [helper] suggest failed: {exc}; rolling")
        return [p.id for p in owned], bank, 0, 0
    plans = result.plans
    if not allow_hit:
        plans = [p for p in plans if p.hit == 0]
    if not plans:
        return [p.id for p in owned], bank, 0, 0
    # Already sorted by score; take best
    plan = plans[0]
    if plan.k == 0:
        return [p.id for p in owned], bank, 0, 0
    new_ids = apply_ids(state.owned_ids, plan.outgoing_ids, plan.incoming_ids)
    return new_ids, plan.bank, plan.k, plan.hit


def advance_ft(ft_before: int, k: int) -> int:
    remaining = max(0, ft_before - k)
    return min(MAX_FT, remaining + 1)


def gate_of(season: str) -> str:
    if season in FAIL_SEASONS:
        return "FAIL"
    if season in PASS_SEASONS:
        return "PASS"
    return "?"


def replay_season(
    season: str,
    *,
    from_gw: int,
    to_gw: int,
    allow_hit: bool,
) -> list[dict]:
    ensure_vaastav((season,))
    gate = gate_of(season)
    hit_tag = "hit" if allow_hit else "no_hit"
    print(f"\n=== {season} product transfer replay gate={gate} condition={hit_tag} GW{from_gw}-{to_gw} ===")

    rows: list[dict] = []
    arms: dict[str, ArmState] | None = None

    for gw in range(from_gw, to_gw + 1):
        packed = project_gw(season, gw)
        if packed is None:
            print(f"  GW{gw}: no actuals — skip")
            continue
        snap, act, projs, by_id = packed

        if arms is None:
            # Seed all arms from the same greenfield squad at first available GW.
            try:
                sol = solve_squad(snap, projs, strategy=STRATEGY, objective="horizon")
            except RuntimeError as exc:
                print(f"  GW{gw}: greenfield solve failed ({exc}) — skip")
                continue
            seed_ids = [p.id for p in sol.players]
            seed_bank = sol.bank
            # After GW1 set-and-forget: 1 FT available for next decision week.
            # On the seed GW itself policies do not transfer.
            arms = {
                name: ArmState(ids=list(seed_ids), bank=seed_bank, ft=1)
                for name in ARMS
            }
            for name in ARMS:
                owned = resolve_squad(snap, arms[name].ids)
                if owned is None:
                    print(f"  GW{gw}: seed squad unresolved — abort season")
                    return rows
                scored = score_owned(snap, owned, by_id, act)
                if scored is None:
                    print(f"  GW{gw}: seed score failed — abort season")
                    return rows
                cap, captain = scored
                rows.append(
                    {
                        "season": season,
                        "e024_gate": gate,
                        "condition": hit_tag,
                        "gw": gw,
                        "arm": name,
                        "cap": round(cap, 4),
                        "hits": 0,
                        "net": round(cap, 4),
                        "transfers": 0,
                        "ft_before": 0,
                        "bank_after": arms[name].bank,
                        "captain": captain,
                        "seed_gw": 1,
                    }
                )
            print(f"  GW{gw}: seeded greenfield | Cap={rows[-1]['cap']:.1f} bank={seed_bank}")
            continue

        # Decision week for each arm
        for name in ARMS:
            st = arms[name]
            owned = resolve_squad(snap, st.ids)
            if owned is None:
                # Player left the pool — roll what we can by dropping missing and
                # aborting this arm's transfers this week.
                print(f"  GW{gw} {name}: owned id missing from snapshot — skip transfers")
                present = [i for i in st.ids if any(p.id == i for p in snap.players)]
                if len(present) != snap.squad.squad_size:
                    rows.append(
                        {
                            "season": season,
                            "e024_gate": gate,
                            "condition": hit_tag,
                            "gw": gw,
                            "arm": name,
                            "cap": "",
                            "hits": "",
                            "net": "",
                            "transfers": "",
                            "ft_before": st.ft,
                            "bank_after": st.bank,
                            "captain": "",
                            "seed_gw": 0,
                            "error": "squad_incomplete",
                        }
                    )
                    continue
                owned = resolve_squad(snap, present)
                assert owned is not None

            ft_before = st.ft
            if name == "roll":
                new_ids, new_bank, k, hit = [p.id for p in owned], st.bank, 0, 0
            elif name == "naive":
                new_ids, new_bank, k, hit = naive_one_swap(
                    snap, owned, by_id, st.bank, ft_before
                )
            else:
                new_ids, new_bank, k, hit = helper_decision(
                    snap, projs, owned, st.bank, ft_before, allow_hit=allow_hit
                )

            new_owned = resolve_squad(snap, new_ids)
            if new_owned is None:
                rows.append(
                    {
                        "season": season,
                        "e024_gate": gate,
                        "condition": hit_tag,
                        "gw": gw,
                        "arm": name,
                        "cap": "",
                        "hits": hit,
                        "net": "",
                        "transfers": k,
                        "ft_before": ft_before,
                        "bank_after": new_bank,
                        "captain": "",
                        "seed_gw": 0,
                        "error": "post_transfer_unresolved",
                    }
                )
                st.ft = advance_ft(ft_before, k)
                continue

            scored = score_owned(snap, new_owned, by_id, act)
            if scored is None:
                rows.append(
                    {
                        "season": season,
                        "e024_gate": gate,
                        "condition": hit_tag,
                        "gw": gw,
                        "arm": name,
                        "cap": "",
                        "hits": hit,
                        "net": "",
                        "transfers": k,
                        "ft_before": ft_before,
                        "bank_after": new_bank,
                        "captain": "",
                        "seed_gw": 0,
                        "error": "score_failed",
                    }
                )
                arms[name] = ArmState(ids=new_ids, bank=new_bank, ft=advance_ft(ft_before, k))
                continue

            cap, captain = scored
            net = cap - hit
            rows.append(
                {
                    "season": season,
                    "e024_gate": gate,
                    "condition": hit_tag,
                    "gw": gw,
                    "arm": name,
                    "cap": round(cap, 4),
                    "hits": hit,
                    "net": round(net, 4),
                    "transfers": k,
                    "ft_before": ft_before,
                    "bank_after": new_bank,
                    "captain": captain,
                    "seed_gw": 0,
                }
            )
            arms[name] = ArmState(ids=new_ids, bank=new_bank, ft=advance_ft(ft_before, k))

        # Progress line
        by_arm = {r["arm"]: r for r in rows if r["gw"] == gw and r["season"] == season}
        bits = []
        for name in ARMS:
            r = by_arm.get(name)
            if r and r.get("cap") != "":
                bits.append(f"{name}={r['cap']}(k={r['transfers']})")
        print(f"  GW{gw}: " + "  ".join(bits))

    return rows


def season_summary(rows: list[dict]) -> list[dict]:
    # group by season, condition, arm
    buckets: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("cap") == "" or r.get("cap") is None:
            continue
        buckets[(r["season"], r["condition"], r["arm"])].append(r)

    # also need helper vs roll/naive per season+condition
    out: list[dict] = []
    seasons_conds = {(s, c) for (s, c, _a) in buckets}
    for season, condition in sorted(seasons_conds):
        gate = gate_of(season)
        caps = {}
        hits = {}
        xfers = {}
        for arm in ARMS:
            rs = buckets.get((season, condition, arm), [])
            caps[arm] = sum(float(r["cap"]) for r in rs)
            hits[arm] = sum(int(r["hits"] or 0) for r in rs)
            xfers[arm] = sum(int(r["transfers"] or 0) for r in rs)
            out.append(
                {
                    "season": season,
                    "e024_gate": gate,
                    "condition": condition,
                    "arm": arm,
                    "n_gw": len(rs),
                    "sum_cap": round(caps[arm], 4),
                    "sum_hits": hits[arm],
                    "sum_net": round(caps[arm] - hits[arm], 4),
                    "sum_transfers": xfers[arm],
                    "delta_vs_roll": "",
                    "delta_vs_naive": "",
                }
            )
        # fill deltas on helper row
        for row in out:
            if row["season"] != season or row["condition"] != condition:
                continue
            if row["arm"] == "helper":
                row["delta_vs_roll"] = round(caps["helper"] - caps.get("roll", 0), 4)
                row["delta_vs_naive"] = round(caps["helper"] - caps.get("naive", 0), 4)
    return out


def write_outputs(gw_rows: list[dict], season_rows: list[dict]) -> None:
    OUT_GW.parent.mkdir(parents=True, exist_ok=True)
    if gw_rows:
        fields = list(gw_rows[0].keys())
        # ensure error column if present on some rows
        for r in gw_rows:
            for k in r:
                if k not in fields:
                    fields.append(k)
        with OUT_GW.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(gw_rows)
    if season_rows:
        with OUT_SEASON.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(season_rows[0].keys()))
            w.writeheader()
            w.writerows(season_rows)

    lines = [
        "Product transfer replay — confidence/smoke (NOT an E-card)",
        f"stack: minutes={MINUTES} rates={RATES} strategy={STRATEGY} seed={SEED}",
        "selling~=now_cost; FT max=2; GW1=greenfield seed; no significance / no promote",
        "",
    ]
    by_gate: dict[str, list[dict]] = defaultdict(list)
    for r in season_rows:
        if r["arm"] == "helper":
            by_gate[r["e024_gate"]].append(r)
    for gate in ("FAIL", "PASS", "?"):
        rs = by_gate.get(gate, [])
        if not rs:
            continue
        lines.append(f"--- {gate} (helper arm) ---")
        for r in rs:
            lines.append(
                f"  {r['season']} [{r['condition']}] n={r['n_gw']} "
                f"Cap={r['sum_cap']} hits={r['sum_hits']} xfers={r['sum_transfers']} "
                f"Δroll={r['delta_vs_roll']} Δnaive={r['delta_vs_naive']}"
            )
        lines.append("")
    lines.append(f"gw csv: {OUT_GW}")
    lines.append(f"season csv: {OUT_SEASON}")
    OUT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Product transfer helper historical smoke replay")
    parser.add_argument("--season", choices=SUPPORTED_SEASONS, help="single season")
    parser.add_argument("--all-seasons", action="store_true")
    parser.add_argument("--from-gw", type=int, default=1)
    parser.add_argument("--to-gw", type=int, default=8, help="inclusive (default 8 for smoke)")
    parser.add_argument(
        "--allow-hit",
        action="store_true",
        help="separate condition: allow FT+1 with hit cost",
    )
    parser.add_argument(
        "--both-conditions",
        action="store_true",
        help="run no-hit then allow-hit",
    )
    args = parser.parse_args()
    if not args.season and not args.all_seasons:
        parser.error("pass --season or --all-seasons")
    seasons = list(SUPPORTED_SEASONS) if args.all_seasons else [args.season]
    conditions = [False, True] if args.both_conditions else [args.allow_hit]

    all_gw: list[dict] = []
    for season in seasons:
        for allow_hit in conditions:
            all_gw.extend(
                replay_season(
                    season,
                    from_gw=args.from_gw,
                    to_gw=args.to_gw,
                    allow_hit=allow_hit,
                )
            )
    season_rows = season_summary(all_gw)
    write_outputs(all_gw, season_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
