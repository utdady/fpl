"""E056-A Phase-2: RULE_UMAX over frozen MENU.

Run ONLY after Phase-1 SURVIVE MATERIAL. Frozen in LAB_LOG E056-A.
SCORE / RULE use only U_cand (ex-ante). MENU XIs use E055-A recipes
(identity with Phase-1 OC; HOLD construction matches E055-A including
blank-companion definition for Cap comparability).
No new ILP objective. No promote.

Usage:
    python scripts/e056_opportunity_cost_phase2.py
    python scripts/e056_opportunity_cost_phase2.py --season 2024-25
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
# E056-A tie priority: HOLD > PAIR > ctrl > cand
TIE_RANK = {"hold": 0, "pair": 1, "ctrl": 2, "cand": 3}


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
    return min(enters, key=lambda e: (-e["cand_u"], e["id"]))["id"]


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


def score_xi(xi: list[Player], by_t: dict) -> tuple[float, Player]:
    """E056-A SCORE: sum U_cand(XI) + U_cand(captain); captain via pick_captains."""
    capt, _ = pick_captains(xi, by_t)
    s = sum(float(by_t[p.id].next_utility) for p in xi) + float(by_t[capt.id].next_utility)
    return s, capt


def rule_umax(menu: dict[str, tuple[list[Player], float, int, float]]) -> str:
    """menu name -> (xi, score, zeros, cap). Ties: HOLD > PAIR > ctrl > cand."""
    best_name = None
    best_key = None
    for name, (_xi, score, _z, _c) in menu.items():
        key = (-score, TIE_RANK[name])
        if best_key is None or key < best_key:
            best_key = key
            best_name = name
    assert best_name is not None
    return best_name


def eval_season(season: str, strategy: str = "balanced") -> list[dict]:
    ensure_vaastav((season,))
    ensure_fplcache_avail((season,))
    ensure_fplcache_strength_ad((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E056-A Phase-2 RULE_UMAX ({CANDIDATE} vs v1) gate={gate} ===")
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
            return {"id": pid, "pos": pt.player.position, "cand_u": float(pt.next_utility)}

        enters = [meta(i) for i in enter_ids]
        exits = [meta(i) for i in exit_ids]
        pairs = pair_max_du_cand(enters, exits)
        exit_by_enter = {e["id"]: x["id"] for e, x in pairs}
        primary_id = choose_primary(enters, pairs)
        companion_ids = {i for i in enter_ids if i != primary_id}

        # CTRL / CAND
        z_ctrl, cap_ctrl = zeros_and_cap(sol_c.xi, sol_c.captain, act)
        z_cand, cap_cand = zeros_and_cap(sol_t.xi, sol_t.captain, act)
        xi0_worse = int(z_cand > z_ctrl)
        score_ctrl, _ = score_xi(list(sol_c.xi), by_t)
        score_cand, _ = score_xi(list(sol_t.xi), by_t)

        menu: dict[str, tuple[list[Player], float, int, float]] = {
            "ctrl": (list(sol_c.xi), score_ctrl, z_ctrl, cap_ctrl),
            "cand": (list(sol_t.xi), score_cand, z_cand, cap_cand),
        }

        # PAIR
        pair_ok = 0
        pair_reason = ""
        z_pair = ""
        cap_pair = ""
        score_pair = ""
        if primary_id not in exit_by_enter:
            pair_reason = "primary_unpaired"
        else:
            l_id = exit_by_enter[primary_id]
            xi_pair = [
                pid_to_player[i] for i in sorted((xi_c_ids - {l_id}) | {primary_id})
            ]
            if not xi_formation_legal(snap, xi_pair):
                pair_reason = "formation_illegal"
            else:
                sp, capt_p = score_xi(xi_pair, by_t)
                zp, cp = zeros_and_cap(xi_pair, capt_p, act)
                pair_ok = 1
                z_pair = zp
                cap_pair = round(cp, 4)
                score_pair = round(sp, 6)
                menu["pair"] = (xi_pair, sp, zp, cp)

        # HOLD (E055-A recipe identity)
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
        score_hold, capt_h = score_xi(xi_hold, by_t)
        z_hold, cap_hold = zeros_and_cap(xi_hold, capt_h, act)
        menu["hold"] = (xi_hold, score_hold, z_hold, cap_hold)

        chosen = rule_umax(menu)
        _xi_r, score_r, z_rule, cap_rule = menu[chosen]

        rows.append({
            "season": season,
            "e024_gate": gate,
            "candidate": CANDIDATE,
            "gw": gw,
            "xi0_worse_gw": xi0_worse,
            "rule_choice": chosen,
            "score_rule": round(score_r, 6),
            "xi0_rule": z_rule,
            "cap_rule": round(cap_rule, 4),
            "xi0_ctrl": z_ctrl,
            "xi0_cand": z_cand,
            "xi0_hold": z_hold,
            "cap_ctrl": round(cap_ctrl, 4),
            "cap_cand": round(cap_cand, 4),
            "cap_hold": round(cap_hold, 4),
            "score_ctrl": round(score_ctrl, 6),
            "score_cand": round(score_cand, 6),
            "score_hold": round(score_hold, 6),
            "pair_feasible": pair_ok,
            "pair_reason": pair_reason if not pair_ok else "ok",
            "xi0_pair": z_pair,
            "cap_pair": cap_pair,
            "score_pair": score_pair,
            "n_hold_swaps": n_hold_swaps,
            "n_menu": len(menu),
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
    lines.append(f"E056-A Phase-2 RULE_UMAX: {CANDIDATE} vs fixtures=v1")
    lines.append(
        "Frozen: SCORE=sum U_cand(XI)+U_cand(capt); "
        "RULE=argmax SCORE; ties HOLD>PAIR>ctrl>cand; "
        "SURVIVE iff Cap(RULE)>Cap(cand) AND zeros(RULE)<=zeros(cand) "
        "AND not identity-to-ctrl on all xi0_worse"
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
                "cap_ok": False,
                "xi0_ok": False,
                "not_all_ctrl": False,
            }
        ctr = Counter(r["rule_choice"] for r in subset)
        lines.append(
            "  rule_choice: "
            + ", ".join(f"{k}={ctr[k]}" for k in ("hold", "pair", "ctrl", "cand") if ctr[k])
        )
        z_rule = sum(int(r["xi0_rule"]) for r in subset)
        z_cand = sum(int(r["xi0_cand"]) for r in subset)
        z_ctrl = sum(int(r["xi0_ctrl"]) for r in subset)
        cap_rule = sum(float(r["cap_rule"]) for r in subset)
        cap_cand = sum(float(r["cap_cand"]) for r in subset)
        cap_ctrl = sum(float(r["cap_ctrl"]) for r in subset)
        n_ctrl = sum(1 for r in subset if r["rule_choice"] == "ctrl")
        lines.append(
            f"  sum_xi0 rule={z_rule} cand={z_cand} ctrl={z_ctrl} "
            f"(rule<=cand: {z_rule <= z_cand})"
        )
        lines.append(
            f"  sum_Cap rule={cap_rule:.1f} cand={cap_cand:.1f} ctrl={cap_ctrl:.1f} "
            f"delta_vs_cand={cap_rule - cap_cand:+.1f}"
        )
        lines.append(f"  n_rule_eq_ctrl={n_ctrl}/{len(subset)}")
        lines.append("")
        return {
            "cap_ok": cap_rule > cap_cand,
            "xi0_ok": z_rule <= z_cand,
            "not_all_ctrl": n_ctrl < len(subset),
            "z_rule": z_rule,
            "z_cand": z_cand,
            "cap_rule": cap_rule,
            "cap_cand": cap_cand,
        }

    block("ALL XI-diff GWs (report)", rows)
    stats = block("PRIMARY: xi0_worse GWs (SURVIVE universe)", worse)

    lines.append("=== RULE choice by season (xi0_worse) ===")
    for season in SUPPORTED_SEASONS:
        sub = [r for r in worse if r["season"] == season]
        if not sub:
            lines.append(f"  {season}: n=0")
            continue
        ctr = Counter(r["rule_choice"] for r in sub)
        z_r = sum(int(r["xi0_rule"]) for r in sub)
        z_c = sum(int(r["xi0_cand"]) for r in sub)
        c_r = sum(float(r["cap_rule"]) for r in sub)
        c_c = sum(float(r["cap_cand"]) for r in sub)
        lines.append(
            f"  {season} n={len(sub)} "
            + " ".join(f"{k}={ctr[k]}" for k in ("hold", "pair", "ctrl", "cand") if ctr[k])
            + f" xi0 {z_c}->{z_r} Cap {c_c:.0f}->{c_r:.0f}"
        )
    lines.append("")

    survive = bool(worse) and stats["cap_ok"] and stats["xi0_ok"] and stats["not_all_ctrl"]
    if survive:
        status = "BRANCH"
        verdict = (
            "BRANCH -> decision-rule / product-surface family "
            f"(Cap RULE {stats['cap_rule']:.1f} > cand {stats['cap_cand']:.1f}; "
            f"XI0 RULE {stats['z_rule']} <= cand {stats['z_cand']}; "
            "not identity-to-ctrl)"
        )
        nxt = "NEXT: new prereg for decision-rule / product-surface (no ILP rewrite / no promote here)."
    else:
        status = "PARK"
        reasons = []
        if not worse:
            reasons.append("empty xi0_worse")
        else:
            if not stats["cap_ok"]:
                reasons.append("Cap(RULE)<=Cap(cand)")
            if not stats["xi0_ok"]:
                reasons.append("XI0(RULE)>XI0(cand)")
            if not stats["not_all_ctrl"]:
                reasons.append("RULE identical to always-ctrl on all worse GWs")
        verdict = (
            "PARK valuation for this stack "
            f"({'; '.join(reasons) if reasons else 'SURVIVE failed'}; "
            "OC is ex-post only under this MENU/RULE)"
        )
        nxt = "NEXT: park; do not invent new ILP objective / FLEX penalty from E056."

    lines.append("=== VERDICT (frozen Phase-2 RULE_UMAX) ===")
    lines.append(verdict)
    lines.append(nxt)
    lines.append("No promote / no new ILP objective / production untouched.")
    return "\n".join(lines) + "\n", status


def main() -> None:
    parser = argparse.ArgumentParser(description="E056-A Phase-2 RULE_UMAX.")
    parser.add_argument("--season", choices=SUPPORTED_SEASONS, default=None)
    parser.add_argument("--strategy", default="balanced")
    args = parser.parse_args()

    print("[e056-p2] CONTROL = v2am_fpla + rates=v1 + fixtures=v1")
    print(f"[e056-p2] CANDIDATE = fixtures={CANDIDATE} (E053 KILL diagnostic)")
    print("[e056-p2] Phase-2 RULE_UMAX — no promote / no new ILP objective")

    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    rows: list[dict] = []
    for s in seasons:
        rows.extend(eval_season(s, args.strategy))

    if args.season:
        ev_path = OUT_DIR / f"e056_oc_phase2_events_{args.season}.csv"
        sum_path = OUT_DIR / f"e056_oc_phase2_summary_{args.season}.txt"
        verd_path = OUT_DIR / f"e056_oc_phase2_verdict_{args.season}.txt"
    else:
        ev_path = OUT_DIR / "e056_oc_phase2_events.csv"
        sum_path = OUT_DIR / "e056_oc_phase2_summary.txt"
        verd_path = OUT_DIR / "e056_oc_phase2_verdict.txt"

    write_rows(rows, ev_path)
    text, status = summarize(rows)
    sum_path.write_text(text, encoding="utf-8")
    verd_path.write_text(
        f"E056-A Phase-2 verdict ({CANDIDATE} vs v1)\n"
        f"STATUS={status}\n"
        f"See {sum_path.name}\n",
        encoding="utf-8",
    )
    sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
    print(f"Wrote {ev_path}")
    print(f"Wrote {sum_path}")
    print(f"Wrote {verd_path}")


if __name__ == "__main__":
    main()
