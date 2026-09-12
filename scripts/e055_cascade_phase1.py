"""E055-A Phase-1: constraint-induced portfolio cascade (descriptive).

Frozen inputs/constants: LAB_LOG E055-A — do not retune after peek.
Phase-1 only: companion vs primary blank share on xi0_worse_gw.
No Phase-2 CFs. No new objective. No promote.

Usage:
    python scripts/e055_cascade_phase1.py
    python scripts/e055_cascade_phase1.py --season 2024-25
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.fplcache_avail import ensure_fplcache_avail
from engine.fplcache_strength_ad import ensure_fplcache_strength_ad
from engine.harness import SUPPORTED_SEASONS, build_snapshot, ensure_vaastav, gw_actuals
from engine.metrics import record_path
from engine.optimize import BENCH_WEIGHT, solve_squad, solve_xi
from engine.project import project_all

OUT_DIR = ROOT / "records" / "historical"
SEED = 7
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}
# E055-A frozen
CONCENTRATION_MIN = 0.50
CANDIDATE = "v1_adxg"


def _squad_u(squad, xi, by_id) -> float:
    xi_ids = {p.id for p in xi}
    total = 0.0
    for p in squad:
        u = by_id[p.id].next_utility
        w = (1.0 - BENCH_WEIGHT) if p.id in xi_ids else BENCH_WEIGHT
        total += w * u
    return total


def pair_max_du_cand(enters: list, exits: list) -> list[tuple]:
    """Greedy same-pos pairs maximizing ΔU_cand; ties lowest enter_id, exit_id."""
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
    """Return primary mover enter_id under E055-A freeze."""
    if pairs:
        best = None  # ( -du, enter_id )
        for e, x in pairs:
            du = e["cand_u"] - x["cand_u"]
            key = (-du, e["id"])
            if best is None or key < best[0]:
                best = (key, e["id"])
        assert best is not None
        return best[1]
    # no same-pos pairs: max U_cand, tie lowest id
    best_e = min(enters, key=lambda e: (-e["cand_u"], e["id"]))
    return best_e["id"]


def eval_season(season: str, strategy: str = "balanced") -> list[dict]:
    ensure_vaastav((season,))
    ensure_fplcache_avail((season,))
    ensure_fplcache_strength_ad((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E055-A Phase-1 cascade ({CANDIDATE} vs v1) gate={gate} ===")
    events: list[dict] = []

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
        by_c = {p.player.id: p for p in ctrl}
        by_t = {p.player.id: p for p in cand}

        try:
            sol_c = solve_squad(snap, ctrl, strategy=strategy, objective="next")
            sol_t = solve_squad(snap, cand, strategy=strategy, objective="next")
        except RuntimeError as e:
            print(f"    solver fail: {e}")
            continue

        xi_c = {p.id for p in sol_c.xi}
        xi_t = {p.id for p in sol_t.xi}
        if xi_c == xi_t:
            continue

        squad_c = {p.id for p in sol_c.players}
        squad_t = {p.id for p in sol_t.players}
        n_squad_changes = len(squad_t - squad_c)

        def xicap(sol) -> float:
            total = sum(float(act.get(p.id, {}).get("actual_points", 0) or 0) for p in sol.xi)
            total += float(act.get(sol.captain.id, {}).get("actual_points", 0) or 0)
            return total

        cap_ctrl = xicap(sol_c)
        cap_cand = xicap(sol_t)
        cap_delta = cap_cand - cap_ctrl

        try:
            xi_ctrl_on_treat, _ = solve_xi(snap, sol_c.players, by_t)
            g_treat = (
                _squad_u(sol_t.players, sol_t.xi, by_t)
                - _squad_u(sol_c.players, xi_ctrl_on_treat, by_t)
            )
        except RuntimeError:
            g_treat = float("nan")

        enter_ids = sorted(xi_t - xi_c)
        exit_ids = sorted(xi_c - xi_t)

        def row(pid: int) -> dict:
            pc = by_c[pid]
            pt = by_t.get(pid)
            a = act.get(pid, {})
            # U and cost from candidate arm when available; ctrl for exits not in cand rare
            src = pt if pt is not None else pc
            return {
                "id": pid,
                "name": pc.player.web_name,
                "pos": pc.player.position,
                "cand_u": float(src.next_utility),
                "cand_mu": float(src.next_mu),
                "ctrl_mu": float(pc.next_mu),
                "cost": int(pc.player.now_cost),
                "mins": float(a.get("actual_minutes", 0) or 0),
                "pts": float(a.get("actual_points", 0) or 0),
            }

        enters = [row(i) for i in enter_ids]
        exits = [row(i) for i in exit_ids]
        pos_touched = {r["pos"] for r in enters} | {r["pos"] for r in exits}
        n_pos = len(pos_touched)
        n_enter = len(enters)
        n_exit = len(exits)
        flex_flag = int(n_enter > 1 or n_pos > 1)
        budget_delta = sum(e["cost"] for e in enters) - sum(x["cost"] for x in exits)

        zeros_c = sum(
            1 for pid in xi_c if float(act.get(pid, {}).get("actual_minutes", 0) or 0) == 0
        )
        zeros_t = sum(
            1 for pid in xi_t if float(act.get(pid, {}).get("actual_minutes", 0) or 0) == 0
        )
        xi0_worse = int(zeros_t > zeros_c)

        pairs = pair_max_du_cand(enters, exits)
        exit_by_enter = {e["id"]: x for e, x in pairs}
        paired_enter_ids = set(exit_by_enter)
        primary_id = choose_primary(enters, pairs)
        n_unpaired_enter = n_enter - len(paired_enter_ids)
        n_unpaired_exit = n_exit - len({x["id"] for _, x in pairs})

        for e in enters:
            x = exit_by_enter.get(e["id"])
            role = "primary" if e["id"] == primary_id else "companion"
            blank_enter = int(e["mins"] == 0)
            primary_harm = int(blank_enter == 1 and xi0_worse == 1)
            du = (e["cand_u"] - x["cand_u"]) if x is not None else None
            events.append({
                "season": season,
                "e024_gate": gate,
                "candidate": CANDIDATE,
                "gw": gw,
                "role": role,
                "n_enter": n_enter,
                "n_exit": n_exit,
                "n_pos_touched": n_pos,
                "n_unpaired_enter": n_unpaired_enter,
                "n_unpaired_exit": n_unpaired_exit,
                "flex_flag": flex_flag,
                "budget_delta": budget_delta,
                "n_squad_changes": n_squad_changes,
                "cap_ctrl": round(cap_ctrl, 4),
                "cap_cand": round(cap_cand, 4),
                "cap_delta": round(cap_delta, 4),
                "g_treat": round(g_treat, 4) if g_treat == g_treat else "",
                "xi0_ctrl": zeros_c,
                "xi0_cand": zeros_t,
                "xi0_worse_gw": xi0_worse,
                "enter_id": e["id"],
                "enter_name": e["name"],
                "enter_pos": e["pos"],
                "enter_cand_u": round(e["cand_u"], 4),
                "enter_cand_mu": round(e["cand_mu"], 4),
                "enter_ctrl_mu": round(e["ctrl_mu"], 4),
                "enter_cost": e["cost"],
                "enter_mins": e["mins"],
                "enter_pts": e["pts"],
                "exit_id": x["id"] if x else "",
                "exit_name": x["name"] if x else "",
                "exit_pos": x["pos"] if x else "",
                "exit_cand_u": round(x["cand_u"], 4) if x else "",
                "exit_mins": x["mins"] if x else "",
                "exit_pts": x["pts"] if x else "",
                "du_cand": round(du, 4) if du is not None else "",
                "paired": int(e["id"] in paired_enter_ids),
                "blank_enter": blank_enter,
                "primary_harm": primary_harm,
                "primary_mover_id": primary_id,
            })
    return events


def write_events(events: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not events:
        path.write_text("", encoding="utf-8")
        return
    cols = list(events[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(events)


def summarize(events: list[dict]) -> tuple[str, str, float]:
    lines: list[str] = []
    lines.append(f"E055-A Phase-1 cascade: {CANDIDATE} vs fixtures=v1")
    lines.append(
        f"Frozen: PRIMARY=max dU_cand same-pos pair (else max U_cand); "
        f"COMPANIONS=Enter minus PRIMARY; "
        f"M=blank_enter on xi0_worse_gw; SURVIVE iff companion_blank_share>={CONCENTRATION_MIN}"
    )
    lines.append("")

    mass = [e for e in events if int(e["primary_harm"]) == 1]
    blanks = [e for e in events if int(e["blank_enter"]) == 1]
    n_m = len(mass)
    n_comp = sum(1 for e in mass if e["role"] == "companion")
    n_prim = sum(1 for e in mass if e["role"] == "primary")
    share = (n_comp / n_m) if n_m else float("nan")

    lines.append(
        f"n_enter_events={len(events)} blank_enter={len(blanks)} "
        f"primary_mass M (blank_enter on xi0_worse_gw)={n_m}"
    )
    lines.append(
        f"M role: primary={n_prim} companion={n_comp} "
        f"companion_blank_share="
        + (f"{100.0 * share:.1f}%" if share == share else "nan")
    )
    if mass:
        flex_n = sum(1 for e in mass if int(e["flex_flag"]) == 1)
        lines.append(f"M FLEX_flag share={100.0 * flex_n / n_m:.1f}% ({flex_n}/{n_m})")
    lines.append("")

    lines.append("=== PRIMARY mass M by season ===")
    for season in SUPPORTED_SEASONS:
        sub = [e for e in mass if e["season"] == season]
        if not sub:
            lines.append(f"  {season}: n=0")
            continue
        nc = sum(1 for e in sub if e["role"] == "companion")
        sh = nc / len(sub)
        lines.append(
            f"  {season} n={len(sub)} companion={nc} "
            f"companion_blank_share={100.0 * sh:.1f}%"
        )
    lines.append("")

    # Report-only: GW-level blank_primary vs blank_companions on xi0_worse
    worse_gws = {
        (e["season"], e["gw"]) for e in events if int(e["xi0_worse_gw"]) == 1
    }
    n_gw_prim_blank = 0
    n_gw_comp_blank = 0
    for season, gw in sorted(worse_gws):
        rows = [e for e in events if e["season"] == season and e["gw"] == gw]
        if any(e["role"] == "primary" and int(e["blank_enter"]) == 1 for e in rows):
            n_gw_prim_blank += 1
        if any(e["role"] == "companion" and int(e["blank_enter"]) == 1 for e in rows):
            n_gw_comp_blank += 1
    lines.append("=== Report-only: xi0_worse GWs with blank by role ===")
    lines.append(f"  n_xi0_worse_gw={len(worse_gws)}")
    lines.append(f"  with blank_primary={n_gw_prim_blank}")
    lines.append(f"  with blank_companion={n_gw_comp_blank}")
    lines.append("")

    # Report-only aggregates on M
    if mass:
        caps = [float(e["cap_delta"]) for e in mass]
        gts = [float(e["g_treat"]) for e in mass if e["g_treat"] != ""]
        nsc = [int(e["n_squad_changes"]) for e in mass]
        lines.append("=== Report-only on M (not the gate) ===")
        lines.append(
            f"  mean cap_delta={sum(caps)/len(caps):.3f} "
            f"mean n_squad_changes={sum(nsc)/len(nsc):.2f}"
            + (
                f" mean g_treat={sum(gts)/len(gts):.3f}"
                if gts
                else " mean g_treat=nan"
            )
        )
        lines.append("")

    if n_m >= 1 and share == share and share >= CONCENTRATION_MIN:
        verdict = (
            f"SURVIVE Phase-1 (companion_blank_share={100.0 * share:.1f}% "
            f">= {100.0 * CONCENTRATION_MIN:.0f}%)"
        )
        status = "SURVIVE"
    elif n_m < 1:
        verdict = "PARK Phase-1 (empty primary mass M)"
        status = "PARK"
        share = float("nan")
    else:
        verdict = (
            f"PARK Phase-1 (companion_blank_share="
            + (f"{100.0 * share:.1f}%" if share == share else "nan")
            + f" < {100.0 * CONCENTRATION_MIN:.0f}%; primary-dominated or no majority)"
        )
        status = "PARK"

    lines.append("=== VERDICT (frozen rule) ===")
    lines.append(verdict)
    if status == "SURVIVE":
        lines.append("NEXT: Phase-2 CF_PAIR / CF_HOLD only (no promote).")
    else:
        lines.append("NEXT: park cascade hypothesis for this stack; no Phase-2.")
    lines.append("No new objective / no promote on this card.")
    text = "\n".join(lines) + "\n"
    return text, status, share


def main() -> None:
    parser = argparse.ArgumentParser(description="E055-A Phase-1 cascade diagnostic.")
    parser.add_argument("--season", choices=SUPPORTED_SEASONS, default=None)
    parser.add_argument("--strategy", default="balanced")
    args = parser.parse_args()

    print("[e055] CONTROL = v2am_fpla + rates=v1 + fixtures=v1")
    print(f"[e055] CANDIDATE = fixtures={CANDIDATE}")
    print("[e055] Phase-1 descriptive only — no CF / no promote")

    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    events: list[dict] = []
    for s in seasons:
        events.extend(eval_season(s, args.strategy))

    if args.season:
        ev_path = OUT_DIR / f"e055_cascade_phase1_events_{args.season}.csv"
        sum_path = OUT_DIR / f"e055_cascade_phase1_summary_{args.season}.txt"
        verd_path = OUT_DIR / f"e055_cascade_phase1_verdict_{args.season}.txt"
    else:
        ev_path = OUT_DIR / "e055_cascade_phase1_events.csv"
        sum_path = OUT_DIR / "e055_cascade_phase1_summary.txt"
        verd_path = OUT_DIR / "e055_cascade_phase1_verdict.txt"

    write_events(events, ev_path)
    text, status, share = summarize(events)
    sum_path.write_text(text, encoding="utf-8")
    share_txt = f"{100.0 * share:.1f}%" if share == share else "nan"
    verd_path.write_text(
        f"E055-A Phase-1 verdict ({CANDIDATE} vs v1)\n"
        f"STATUS={status}\n"
        f"companion_blank_share={share_txt}\n"
        f"See {sum_path.name}\n",
        encoding="utf-8",
    )
    print(text)
    print(f"Wrote {ev_path}")
    print(f"Wrote {sum_path}")
    print(f"Wrote {verd_path}")


if __name__ == "__main__":
    main()
