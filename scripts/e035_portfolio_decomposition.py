"""E035 diagnostic: portfolio-value decomposition (descriptive proxies).

Pre-registered in docs/DECISION_ARCHITECTURE.md and docs/LAB_LOG.md.

GW-level treatment arm (balanced; objective=next; seed=7; packaged rates_v2b).
Primary: AUROC(proxy, portfolio_bad) within FAIL-season treat GWs.
portfolio_bad = treat Cap < ctrl Cap.

Proxies (descriptive only; no new optimizer):
  budget_opp_cost      mean(entrant_price - leaver_price) over same-pos swap pairs
  replacement_value    mean(best_excluded_treat_mu - entrant_treat_mu) per entrant
  positional_scarcity  mean(leaver_ctrl_rank - entrant_ctrl_rank) / pool_size
  bench_mass_delta     sum(treat_mu bench) - sum(ctrl_mu bench)
  n_squad_changes      |entered| (= |left|)
  squad_overlap        |intersection| / 15
  g_treat              U_treat(S_treat) - U_treat(S_ctrl, xi on treat)
  near_tie_frac        fraction of swap pairs with |ctrl_mu gap| < 0.25
  mean_vs_leaver_pts   mean(entrant_pts - leaver_pts) over same-pos pairs (realized)

Usage:
    python scripts/e035_portfolio_decomposition.py
    python scripts/e035_portfolio_decomposition.py --season 2023-24
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.harness import (
    SUPPORTED_SEASONS,
    build_snapshot,
    ensure_vaastav,
    gw_actuals,
    recent_minutes_by_element,
)
from engine.metrics import record_path
from engine.minutes_struct import RECENT_WINDOW
from engine.models import Player
from engine.optimize import BENCH_WEIGHT, pick_captains, solve_squad, solve_xi
from engine.packaging import apply_packaged_next_utility
from engine.project import project_all

OUT = Path("records") / "historical" / "e035_portfolio_decomposition_gw.csv"
OUT_TXT = Path("records") / "historical" / "e035_portfolio_decomposition_summary.txt"
SEED = 7
OBJECTIVE = "next"
STRATEGY = "balanced"
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}
NEAR_TIE = 0.25

PROXIES = (
    "budget_opp_cost",
    "replacement_value",
    "positional_scarcity",
    "bench_mass_delta",
    "n_squad_changes",
    "squad_overlap",
    "g_treat",
    "near_tie_frac",
    "mean_vs_leaver_pts",
    "delta_u_pred",
)


def _pts(act: dict, pid: int) -> float:
    return float(act.get(pid, {}).get("actual_points", 0) or 0)


def cap_points(sol, act: dict) -> float:
    total = sum(_pts(act, p.id) for p in sol.xi)
    total += _pts(act, sol.captain.id)
    return total


def squad_weighted_utility(squad: list[Player], xi: list[Player], by_id: dict) -> float:
    xi_ids = {p.id for p in xi}
    total = 0.0
    for p in squad:
        u = by_id[p.id].next_utility
        w = (1.0 - BENCH_WEIGHT) if p.id in xi_ids else BENCH_WEIGHT
        total += w * u
    return total


def rank_map(by_id: dict, snap, position: str) -> dict[int, int]:
    """Rank 1 = highest ctrl next_mu within position."""
    pool = [
        p.id for p in snap.players
        if p.id in by_id and p.position == position and by_id[p.id].horizon_utility > -20
    ]
    pool.sort(key=lambda pid: by_id[pid].next_mu, reverse=True)
    return {pid: i + 1 for i, pid in enumerate(pool)}


def same_pos_pairs(
    entered: set[int],
    left: set[int],
    players_by_id: dict[int, Player],
) -> list[tuple[int, int]]:
    ent_by_pos: dict[str, list[int]] = defaultdict(list)
    lev_by_pos: dict[str, list[int]] = defaultdict(list)
    for eid in entered:
        ent_by_pos[players_by_id[eid].position].append(eid)
    for lid in left:
        lev_by_pos[players_by_id[lid].position].append(lid)
    pairs: list[tuple[int, int]] = []
    for pos in ent_by_pos:
        if pos not in lev_by_pos:
            continue
        for eid in ent_by_pos[pos]:
            for lid in lev_by_pos[pos]:
                pairs.append((eid, lid))
    return pairs


def best_excluded_mu(by_t: dict, snap, squad_ids: set[int], position: str) -> float:
    best = float("-inf")
    found = False
    for p in snap.players:
        if p.id not in by_t or p.position != position or p.id in squad_ids:
            continue
        if by_t[p.id].horizon_utility <= -20:
            continue
        found = True
        best = max(best, by_t[p.id].next_mu)
    return best if found else float("nan")


def mann_whitney_u(pos_scores: list[float], neg_scores: list[float]) -> float:
    """U statistic: higher scores expected for portfolio_bad (positive class)."""
    if not pos_scores or not neg_scores:
        return float("nan")
    tagged = [(s, 1) for s in pos_scores] + [(s, 0) for s in neg_scores]
    tagged.sort(key=lambda x: x[0])
    ranks = [0.0] * len(tagged)
    i = 0
    while i < len(tagged):
        j = i
        while j < len(tagged) and tagged[j][0] == tagged[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[k] = avg_rank
        i = j
    n1 = len(pos_scores)
    r1 = sum(r for r, (_, lbl) in zip(ranks, tagged) if lbl == 1)
    return r1 - n1 * (n1 + 1) / 2.0


def auroc(pos_scores: list[float], neg_scores: list[float]) -> float:
    """AUROC with positive class = portfolio_bad (higher proxy => more bad)."""
    u = mann_whitney_u(pos_scores, neg_scores)
    if u != u:
        return float("nan")
    n1, n2 = len(pos_scores), len(neg_scores)
    return u / (n1 * n2)


def analyze_season(season: str) -> list[dict]:
    ensure_vaastav((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E035 portfolio decomposition gate={gate} ===")
    rows: list[dict] = []

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue
        players_by_id = {p.id: p for p in snap.players}

        recent = recent_minutes_by_element(season, gw, window=RECENT_WINDOW)
        v1 = project_all(
            snap, horizon=1, strategy=STRATEGY, seed=SEED,
            minutes_version="v2am_s", rates_version="v1", fixtures_version="v1",
        )
        v2b = project_all(
            snap, horizon=1, strategy=STRATEGY, seed=SEED,
            minutes_version="v2am_s", rates_version="v2b", fixtures_version="v1",
        )
        packaged = apply_packaged_next_utility(
            v2b, v1, recent_minutes=recent, as_of_gw=gw, strategy=STRATEGY,
        )
        by_c = {p.player.id: p for p in v1}
        by_t = {p.player.id: p for p in packaged}

        try:
            sol_c = solve_squad(snap, v1, strategy=STRATEGY, objective=OBJECTIVE)
            sol_t = solve_squad(snap, packaged, strategy=STRATEGY, objective=OBJECTIVE)
        except RuntimeError:
            continue

        ctrl_cap = cap_points(sol_c, act)
        treat_cap = cap_points(sol_t, act)
        delta_cap = treat_cap - ctrl_cap
        portfolio_bad = int(delta_cap < 0)
        portfolio_good = int(delta_cap >= 0)

        c_squad = {p.id for p in sol_c.players}
        t_squad = {p.id for p in sol_t.players}
        entered = t_squad - c_squad
        left = c_squad - t_squad
        overlap = len(c_squad & t_squad) / 15.0
        n_changes = len(entered)

        pairs = same_pos_pairs(entered, left, players_by_id)

        budget_deltas: list[float] = []
        scarcity_deltas: list[float] = []
        near_tie_flags: list[int] = []
        vs_leaver: list[float] = []
        for eid, lid in pairs:
            budget_deltas.append(players_by_id[eid].now_cost - players_by_id[lid].now_cost)
            pos = players_by_id[eid].position
            ranks = rank_map(by_c, snap, pos)
            pool_n = max(len(ranks), 1)
            scarcity_deltas.append((ranks.get(lid, pool_n) - ranks.get(eid, pool_n)) / pool_n)
            gap = abs(by_c[eid].next_mu - by_c[lid].next_mu)
            near_tie_flags.append(int(gap < NEAR_TIE))
            vs_leaver.append(_pts(act, eid) - _pts(act, lid))

        repl_vals: list[float] = []
        for eid in entered:
            pos = players_by_id[eid].position
            best_mu = best_excluded_mu(by_t, snap, t_squad, pos)
            if best_mu == best_mu:
                repl_vals.append(best_mu - by_t[eid].next_mu)

        bench_c = {p.id for p in sol_c.bench}
        bench_t = {p.id for p in sol_t.bench}
        bench_mass_delta = (
            sum(by_t[p.id].next_mu for p in sol_t.players if p.id in bench_t)
            - sum(by_c[p.id].next_mu for p in sol_c.players if p.id in bench_c)
        )

        try:
            xi_ctrl_on_treat, _ = solve_xi(snap, sol_c.players, by_t)
            g_treat = squad_weighted_utility(sol_t.players, sol_t.xi, by_t) - squad_weighted_utility(
                sol_c.players, xi_ctrl_on_treat, by_t
            )
        except RuntimeError:
            g_treat = float("nan")

        delta_u_pred = sol_t.next_xi_utility - sol_c.next_xi_utility

        rows.append({
            "season": season,
            "e024_gate": gate,
            "gw": gw,
            "portfolio_bad": portfolio_bad,
            "portfolio_good": portfolio_good,
            "delta_cap": round(delta_cap, 4),
            "delta_u_pred": round(delta_u_pred, 4),
            "budget_opp_cost": round(statistics.mean(budget_deltas), 4) if budget_deltas else 0.0,
            "replacement_value": round(statistics.mean(repl_vals), 4) if repl_vals else 0.0,
            "positional_scarcity": round(statistics.mean(scarcity_deltas), 4) if scarcity_deltas else 0.0,
            "bench_mass_delta": round(bench_mass_delta, 4),
            "n_squad_changes": n_changes,
            "squad_overlap": round(overlap, 4),
            "g_treat": round(g_treat, 4) if g_treat == g_treat else "",
            "near_tie_frac": round(statistics.mean(near_tie_flags), 4) if near_tie_flags else 0.0,
            "mean_vs_leaver_pts": round(statistics.mean(vs_leaver), 4) if vs_leaver else "",
            "n_swap_pairs": len(pairs),
        })

    bad_n = sum(r["portfolio_bad"] for r in rows)
    print(f"  gw-rows={len(rows)} portfolio_bad={bad_n}")
    return rows


def proxy_discrimination(rows: list[dict], gate: str) -> list[tuple[str, float, float, int, int]]:
    """Return (proxy, auroc, mann_whitney_u, n_bad, n_good) for gate subset."""
    subset = [r for r in rows if r["e024_gate"] == gate]
    bad = [r for r in subset if r["portfolio_bad"]]
    good = [r for r in subset if r["portfolio_good"]]
    results: list[tuple[str, float, float, int, int]] = []
    for proxy in PROXIES:
        pos = [float(r[proxy]) for r in bad if r[proxy] != ""]
        neg = [float(r[proxy]) for r in good if r[proxy] != ""]
        if len(pos) < 3 or len(neg) < 3:
            results.append((proxy, float("nan"), float("nan"), len(pos), len(neg)))
            continue
        results.append((proxy, auroc(pos, neg), mann_whitney_u(pos, neg), len(pos), len(neg)))
    return results


def correlation_matrix(rows: list[dict], gate: str) -> dict[str, dict[str, float]]:
    import math

    subset = [r for r in rows if r["e024_gate"] == gate]
    vecs: dict[str, list[float]] = {}
    for proxy in PROXIES:
        vecs[proxy] = [float(r[proxy]) for r in subset if r[proxy] != ""]
    n = min(len(v) for v in vecs.values()) if vecs else 0
    if n < 5:
        return {}
    trimmed = {k: v[:n] for k, v in vecs.items()}
    out: dict[str, dict[str, float]] = {a: {} for a in PROXIES}
    for a in PROXIES:
        for b in PROXIES:
            xs, ys = trimmed[a], trimmed[b]
            mx, my = statistics.mean(xs), statistics.mean(ys)
            num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
            den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
            out[a][b] = round(num / den, 3) if den else float("nan")
    return out


def summarize(rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E035: portfolio-value decomposition (descriptive)")
    lines.append("primary: AUROC(proxy, portfolio_bad) within gate; higher = proxy predicts bad")
    lines.append("")

    for gate in ("FAIL", "PASS"):
        subset = [r for r in rows if r["e024_gate"] == gate]
        bad = sum(r["portfolio_bad"] for r in subset)
        lines.append(f"=== {gate} treat GWs n={len(subset)} portfolio_bad={bad} ===")
        disc = proxy_discrimination(rows, gate)
        disc.sort(key=lambda x: x[1] if x[1] == x[1] else -1, reverse=True)
        for proxy, auc, u, nb, ng in disc:
            auc_s = f"{auc:.3f}" if auc == auc else "nan"
            u_s = f"{u:.1f}" if u == u else "nan"
            lines.append(f"  {proxy:22s} AUROC={auc_s}  U={u_s}  (bad={nb} good={ng})")
        lines.append("")

    fail_disc = {p: a for p, a, *_ in proxy_discrimination(rows, "FAIL")}
    pass_disc = {p: a for p, a, *_ in proxy_discrimination(rows, "PASS")}
    lines.append("=== FAIL vs PASS AUROC delta (architecture-intrinsic check) ===")
    for proxy in PROXIES:
        f, p = fail_disc.get(proxy, float("nan")), pass_disc.get(proxy, float("nan"))
        if f == f and p == p:
            lines.append(f"  {proxy:22s} FAIL={f:.3f} PASS={p:.3f} delta={f - p:.3f}")
    lines.append("")

    corr = correlation_matrix(rows, "FAIL")
    if corr:
        lines.append("=== FAIL proxy correlation (selected pairs) ===")
        for a, b in (
            ("g_treat", "n_squad_changes"),
            ("g_treat", "replacement_value"),
            ("budget_opp_cost", "replacement_value"),
            ("near_tie_frac", "positional_scarcity"),
            ("delta_u_pred", "g_treat"),
        ):
            if a in corr and b in corr[a]:
                lines.append(f"  corr({a}, {b})={corr[a][b]}")
        lines.append("")

    text = "\n".join(lines) + "\n"
    print(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    args = parser.parse_args()
    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    print("[e035] portfolio decomposition; descriptive only; no new objective")
    all_rows: list[dict] = []
    for s in seasons:
        all_rows.extend(analyze_season(s))

    fields = [
        "season", "e024_gate", "gw", "portfolio_bad", "portfolio_good", "delta_cap",
        "delta_u_pred", "budget_opp_cost", "replacement_value", "positional_scarcity",
        "bench_mass_delta", "n_squad_changes", "squad_overlap", "g_treat",
        "near_tie_frac", "mean_vs_leaver_pts", "n_swap_pairs",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"Wrote {OUT} ({len(all_rows)} rows)")
    summary = summarize(all_rows)
    OUT_TXT.write_text(summary, encoding="utf-8")
    print(f"Wrote {OUT_TXT}")


if __name__ == "__main__":
    main()
