"""E055-A Phase-2: CF_PAIR / CF_HOLD under frozen cascade recipes.

Run ONLY after Phase-1 SURVIVE. Frozen recipes in LAB_LOG E055-A.
No new objective. No promote.

Usage:
    python scripts/e055_cascade_phase2.py
    python scripts/e055_cascade_phase2.py --season 2024-25
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.fplcache_avail import ensure_fplcache_avail
from engine.fplcache_strength_ad import ensure_fplcache_strength_ad
from engine.harness import SUPPORTED_SEASONS, build_snapshot, ensure_vaastav, gw_actuals
from engine.metrics import record_path
from engine.models import Player
from engine.optimize import pick_captains, solve_squad
from engine.project import project_all

OUT_DIR = ROOT / "records" / "historical"
SEED = 7
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}
CANDIDATE = "v1_adxg"
POS_ORDER = {"GKP": 0, "DEF": 1, "MID": 2, "FWD": 3}


def pair_max_du_cand(enters: list, exits: list) -> list[tuple]:
    used_e: set[int] = set()
    used_x: set[int] = set()
    pairs: list[tuple] = []
    candidates: list[tuple] = []
    for i, e in enumerate(enters):
        for j, x in enumerate(exits):
            if e["pos"] != x["pos"]:
                continue
            du = e["cand_u"] - x["cand_u"]
            candidates.append((-du, e["id"], x["id"], i, j))
    candidates.sort()
    for _, _, _, i, j in candidates:
        if i in used_e or j in used_x:
            continue
        used_e.add(i)
        used_x.add(j)
        pairs.append((enters[i], exits[j]))
    return pairs


def choose_primary(enters: list, pairs: list[tuple]) -> int:
    if pairs:
        best = None
        for e, x in pairs:
            du = e["cand_u"] - x["cand_u"]
            key = (-du, e["id"])
            if best is None or key < best[0]:
                best = (key, e["id"])
        assert best is not None
        return best[1]
    best_e = min(enters, key=lambda e: (-e["cand_u"], e["id"]))
    return best_e["id"]


def xi_formation_legal(snap, xi: list[Player]) -> bool:
    rules = snap.squad
    if len(xi) != rules.squad_play:
        return False
    counts = Counter(p.position for p in xi)
    for pos, mn in rules.min_play.items():
        if counts.get(pos, 0) < mn:
            return False
    for pos, mx in rules.max_play.items():
        if counts.get(pos, 0) > mx:
            return False
    return True


def zeros_and_cap(xi: list[Player], captain: Player, act: dict) -> tuple[int, float]:
    z = sum(1 for p in xi if float(act.get(p.id, {}).get("actual_minutes", 0) or 0) == 0)
    total = sum(float(act.get(p.id, {}).get("actual_points", 0) or 0) for p in xi)
    total += float(act.get(captain.id, {}).get("actual_points", 0) or 0)
    return z, total


def eval_season(season: str, strategy: str = "balanced") -> list[dict]:
    ensure_vaastav((season,))
    ensure_fplcache_avail((season,))
    ensure_fplcache_strength_ad((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E055-A Phase-2 CF ({CANDIDATE} vs v1) gate={gate} ===")
    rows: list[dict] = []

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        print(f"  [{season}] GW{gw}")
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue

        ctrl = project_all(
            snap, horizon=1, strategy=strategy, seed=SEED,
            minutes_version="v2am_fpla", rates_version="v1", fixtures_version="v1",
        )
        cand = project_all(
            snap, horizon=1, strategy=strategy, seed=SEED,
            minutes_version="v2am_fpla", rates_version="v1", fixtures_version=CANDIDATE,
        )
        by_t = {p.player.id: p for p in cand}

        try:
            sol_c = solve_squad(snap, ctrl, strategy=strategy, objective="next")
            sol_t = solve_squad(snap, cand, strategy=strategy, objective="next")
        except RuntimeError as e:
            print(f"    solver fail: {e}")
            continue

        xi_c_ids = {p.id for p in sol_c.xi}
        xi_t_ids = {p.id for p in sol_t.xi}
        if xi_c_ids == xi_t_ids:
            continue

        pid_to_player: dict[int, Player] = {}
        for p in list(sol_c.players) + list(sol_t.players):
            pid_to_player[p.id] = p

        enter_ids = sorted(xi_t_ids - xi_c_ids)
        exit_ids = sorted(xi_c_ids - xi_t_ids)

        def meta(pid: int) -> dict:
            pt = by_t[pid]
            return {
                "id": pid,
                "pos": pt.player.position,
                "cand_u": float(pt.next_utility),
            }

        enters = [meta(i) for i in enter_ids]
        exits = [meta(i) for i in exit_ids]
        pairs = pair_max_du_cand(enters, exits)
        exit_by_enter = {e["id"]: x["id"] for e, x in pairs}
        primary_id = choose_primary(enters, pairs)
        companion_ids = {i for i in enter_ids if i != primary_id}

        z_ctrl, cap_ctrl = zeros_and_cap(sol_c.xi, sol_c.captain, act)
        z_cand, cap_cand = zeros_and_cap(sol_t.xi, sol_t.captain, act)
        xi0_worse = int(z_cand > z_ctrl)

        # CF_PAIR
        pair_ok = 0
        pair_reason = ""
        z_pair = ""
        cap_pair = ""
        if primary_id not in exit_by_enter:
            pair_reason = "primary_unpaired"
        else:
            l_id = exit_by_enter[primary_id]
            xi_pair = [
                pid_to_player[i]
                for i in sorted((xi_c_ids - {l_id}) | {primary_id})
            ]
            if not xi_formation_legal(snap, xi_pair):
                pair_reason = "formation_illegal"
            else:
                capt_p, _ = pick_captains(xi_pair, by_t)
                zp, cp = zeros_and_cap(xi_pair, capt_p, act)
                pair_ok = 1
                z_pair = zp
                cap_pair = round(cp, 4)

        # CF_HOLD
        xi_hold_ids = set(xi_t_ids)
        n_hold_swaps = 0
        blank_comps = [
            pid_to_player[i]
            for i in companion_ids
            if float(act.get(i, {}).get("actual_minutes", 0) or 0) == 0
        ]
        blank_comps.sort(key=lambda p: (POS_ORDER[p.position], p.id))
        for c in blank_comps:
            candidates = [
                pid_to_player[i]
                for i in (xi_c_ids - xi_hold_ids)
                if pid_to_player[i].position == c.position
            ]
            if not candidates:
                continue
            p_star = min(
                candidates,
                key=lambda p: (-float(by_t[p.id].next_utility), p.id),
            )
            tentative_ids = (xi_hold_ids - {c.id}) | {p_star.id}
            tentative = [pid_to_player[i] for i in sorted(tentative_ids)]
            if xi_formation_legal(snap, tentative):
                xi_hold_ids = tentative_ids
                n_hold_swaps += 1

        xi_hold = [pid_to_player[i] for i in sorted(xi_hold_ids)]
        capt_h, _ = pick_captains(xi_hold, by_t)
        z_hold, cap_hold = zeros_and_cap(xi_hold, capt_h, act)
        hold_ok = 1  # always defined; may be identity if no blank companions

        pair_xi0_better = int(pair_ok == 1 and int(z_pair) < z_cand)
        hold_xi0_better = int(z_hold < z_cand)
        pair_cap_better = (
            int(pair_ok == 1 and float(cap_pair) > cap_cand) if pair_ok else ""
        )
        hold_cap_better = int(cap_hold > cap_cand)

        rows.append({
            "season": season,
            "e024_gate": gate,
            "candidate": CANDIDATE,
            "gw": gw,
            "primary_mover_id": primary_id,
            "n_enter": len(enter_ids),
            "n_companion": len(companion_ids),
            "n_blank_companion": len(blank_comps),
            "xi0_ctrl": z_ctrl,
            "xi0_cand": z_cand,
            "xi0_worse_gw": xi0_worse,
            "cap_ctrl": round(cap_ctrl, 4),
            "cap_cand": round(cap_cand, 4),
            "pair_feasible": pair_ok,
            "pair_reason": pair_reason if not pair_ok else "ok",
            "xi0_pair": z_pair,
            "cap_pair": cap_pair,
            "pair_xi0_better": pair_xi0_better if pair_ok else "",
            "pair_cap_better": pair_cap_better,
            "hold_feasible": hold_ok,
            "n_hold_swaps": n_hold_swaps,
            "xi0_hold": z_hold,
            "cap_hold": round(cap_hold, 4),
            "hold_xi0_better": hold_xi0_better,
            "hold_cap_better": hold_cap_better,
        })
    return rows


def write_rows(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def summarize(rows: list[dict]) -> tuple[str, str]:
    lines: list[str] = []
    lines.append(f"E055-A Phase-2 CF: {CANDIDATE} vs fixtures=v1")
    lines.append(
        "Frozen: CF_PAIR = primary E<->L on ctrl XI; "
        "CF_HOLD = replace blank companions from ctrl XI; "
        "BRANCH if either recovers XI0 vs full cand (AGG zeros on feasible xi0_worse)"
    )
    lines.append("")

    worse = [r for r in rows if int(r["xi0_worse_gw"]) == 1]
    lines.append(f"n_xi_diff_gw={len(rows)} n_xi0_worse_gw={len(worse)}")
    lines.append("")

    def block(title: str, subset: list[dict]) -> dict:
        lines.append(f"=== {title} n={len(subset)} ===")
        if not subset:
            lines.append("  (empty)")
            lines.append("")
            return {
                "pair_recovers": False,
                "hold_recovers": False,
                "pair_n": 0,
                "hold_n": 0,
            }

        pair_feas = [r for r in subset if int(r["pair_feasible"]) == 1]
        z_cand = sum(int(r["xi0_cand"]) for r in pair_feas)
        z_pair = sum(int(r["xi0_pair"]) for r in pair_feas)
        pair_better_n = sum(1 for r in pair_feas if int(r["pair_xi0_better"]) == 1)
        pair_recovers = bool(pair_feas) and z_pair < z_cand

        z_cand_h = sum(int(r["xi0_cand"]) for r in subset)
        z_hold = sum(int(r["xi0_hold"]) for r in subset)
        hold_better_n = sum(1 for r in subset if int(r["hold_xi0_better"]) == 1)
        hold_swaps = sum(int(r["n_hold_swaps"]) for r in subset)
        hold_recovers = z_hold < z_cand_h

        cap_cand = sum(float(r["cap_cand"]) for r in subset)
        cap_hold = sum(float(r["cap_hold"]) for r in subset)
        cap_pair = sum(float(r["cap_pair"]) for r in pair_feas) if pair_feas else float("nan")
        cap_cand_p = sum(float(r["cap_cand"]) for r in pair_feas) if pair_feas else float("nan")

        lines.append(
            f"  CF_PAIR feasible={len(pair_feas)}/{len(subset)} "
            f"sum_xi0 cand={z_cand} pair={z_pair} "
            f"gw_better={pair_better_n} recovers={pair_recovers}"
        )
        if pair_feas:
            lines.append(
                f"  CF_PAIR Cap sum cand={cap_cand_p:.1f} pair={cap_pair:.1f} "
                f"delta={cap_pair - cap_cand_p:+.1f}"
            )
        unpaired = sum(1 for r in subset if r["pair_reason"] == "primary_unpaired")
        illegal = sum(1 for r in subset if r["pair_reason"] == "formation_illegal")
        lines.append(f"  CF_PAIR skip: unpaired={unpaired} formation_illegal={illegal}")
        lines.append(
            f"  CF_HOLD sum_xi0 cand={z_cand_h} hold={z_hold} "
            f"gw_better={hold_better_n} n_swaps={hold_swaps} recovers={hold_recovers}"
        )
        lines.append(
            f"  CF_HOLD Cap sum cand={cap_cand:.1f} hold={cap_hold:.1f} "
            f"delta={cap_hold - cap_cand:+.1f}"
        )
        lines.append("")
        return {
            "pair_recovers": pair_recovers,
            "hold_recovers": hold_recovers,
            "pair_n": len(pair_feas),
            "hold_n": len(subset),
        }

    block("ALL XI-diff GWs (report)", rows)
    stats = block("PRIMARY: xi0_worse GWs (branch universe)", worse)

    # per-season worse
    lines.append("=== xi0_worse by season (CF_HOLD xi0 / CF_PAIR if feasible) ===")
    for season in SUPPORTED_SEASONS:
        sub = [r for r in worse if r["season"] == season]
        if not sub:
            lines.append(f"  {season}: n=0")
            continue
        zc = sum(int(r["xi0_cand"]) for r in sub)
        zh = sum(int(r["xi0_hold"]) for r in sub)
        pf = [r for r in sub if int(r["pair_feasible"]) == 1]
        zp = sum(int(r["xi0_pair"]) for r in pf) if pf else None
        zp_txt = f"pair={zp}" if zp is not None else "pair=n/a"
        lines.append(
            f"  {season} n={len(sub)} cand_xi0={zc} hold_xi0={zh} {zp_txt} "
            f"pair_feas={len(pf)}"
        )
    lines.append("")

    pair_ok = stats["pair_recovers"]
    hold_ok = stats["hold_recovers"]
    if pair_ok or hold_ok:
        which = []
        if pair_ok:
            which.append("CF_PAIR")
        if hold_ok:
            which.append("CF_HOLD")
        status = "BRANCH"
        verdict = (
            f"BRANCH -> valuation/opportunity-cost family "
            f"({' + '.join(which)} recovers XI0 vs cand on xi0_worse AGG)"
        )
        nxt = "NEXT: open new prereg for valuation/opportunity-cost (no promote here)."
    else:
        status = "PARK"
        verdict = (
            "PARK cascade for this stack "
            "(neither CF recovers AGG XI0 vs full cand on xi0_worse)"
        )
        nxt = "NEXT: park; do not invent objective / FLEX penalty from E055."

    lines.append("=== VERDICT (frozen Phase-2 rule) ===")
    lines.append(verdict)
    lines.append(nxt)
    lines.append("No promote / no new objective on this card.")
    return "\n".join(lines) + "\n", status


def main() -> None:
    parser = argparse.ArgumentParser(description="E055-A Phase-2 CF_PAIR / CF_HOLD.")
    parser.add_argument("--season", choices=SUPPORTED_SEASONS, default=None)
    parser.add_argument("--strategy", default="balanced")
    args = parser.parse_args()

    print("[e055-p2] CONTROL = v2am_fpla + rates=v1 + fixtures=v1")
    print(f"[e055-p2] CANDIDATE = fixtures={CANDIDATE}")
    print("[e055-p2] Phase-2 CF only — no new objective / no promote")

    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    rows: list[dict] = []
    for s in seasons:
        rows.extend(eval_season(s, args.strategy))

    if args.season:
        ev_path = OUT_DIR / f"e055_cascade_phase2_events_{args.season}.csv"
        sum_path = OUT_DIR / f"e055_cascade_phase2_summary_{args.season}.txt"
        verd_path = OUT_DIR / f"e055_cascade_phase2_verdict_{args.season}.txt"
    else:
        ev_path = OUT_DIR / "e055_cascade_phase2_events.csv"
        sum_path = OUT_DIR / "e055_cascade_phase2_summary.txt"
        verd_path = OUT_DIR / "e055_cascade_phase2_verdict.txt"

    write_rows(rows, ev_path)
    text, status = summarize(rows)
    sum_path.write_text(text, encoding="utf-8")
    verd_path.write_text(
        f"E055-A Phase-2 verdict ({CANDIDATE} vs v1)\n"
        f"STATUS={status}\n"
        f"See {sum_path.name}\n",
        encoding="utf-8",
    )
    # Avoid Windows console Unicode issues
    sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
    print(f"Wrote {ev_path}")
    print(f"Wrote {sum_path}")
    print(f"Wrote {verd_path}")


if __name__ == "__main__":
    main()
