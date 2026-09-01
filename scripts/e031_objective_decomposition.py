"""E031 diagnostic: objective-alignment decomposition (XI vs captain vs squad).

Extends E030 GW rows with sign tables and channel attribution.
Frozen stack: control v2am_s+rates=v1 vs packaged rates_v2b; objective=next; seed=7.
Strategies: balanced, safe — existing objectives only.

Channels:
  delta_cap_bonus = delta_cap - delta_xi_pts   (captain double-count)
  delta_cap_oracle = oracle_cap(treat XI) - oracle_cap(ctrl XI)

Change flags: squad_changed, xi_changed, captain_changed, captain_only_changed

Sign tables per FAIL/PASS: sign(delta U) vs sign(delta XI), sign(delta Cap), joint buckets.

No new utility. No lambda. No optimizer rewrite. Diagnostic only.

Usage:
    python scripts/e031_objective_decomposition.py
    python scripts/e031_objective_decomposition.py --season 2023-24
    python scripts/e031_objective_decomposition.py --csv-only   # sign tables from E030 CSV
"""
from __future__ import annotations

import argparse
import csv
import math
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
from engine.models import Player, PlayerProjection
from engine.optimize import solve_squad
from engine.packaging import apply_packaged_next_utility
from engine.project import project_all

E030_CSV = Path("records") / "historical" / "e030_objective_alignment_gw.csv"
OUT_GW = Path("records") / "historical" / "e031_objective_decomposition_gw.csv"
OUT_TXT = Path("records") / "historical" / "e031_objective_decomposition_summary.txt"
SEED = 7
OBJECTIVE = "next"
STRATEGIES = ("balanced", "safe")
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}
SIGN_EPS = 1e-9


def _pts(act: dict, pid: int) -> float:
    return float(act.get(pid, {}).get("actual_points", 0) or 0)


def xi_points(xi_ids: set[int], act: dict) -> float:
    return sum(_pts(act, pid) for pid in xi_ids)


def xi_cap_points(xi: list[Player], captain: Player, act: dict) -> float:
    total = sum(_pts(act, p.id) for p in xi)
    total += _pts(act, captain.id)
    return total


def best_captain(xi: list[Player], act: dict) -> Player:
    return max(xi, key=lambda p: _pts(act, p.id))


def cap_points(sol, act: dict) -> float:
    return xi_cap_points(sol.xi, sol.captain, act)


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return float("nan")
    return num / (den_x * den_y)


def _sgn(x: float) -> int:
    if x > SIGN_EPS:
        return 1
    if x < -SIGN_EPS:
        return -1
    return 0


def enrich_row(row: dict) -> dict:
    du = float(row["delta_u_pred"])
    dxi = float(row["delta_xi_pts"])
    dcap = float(row["delta_cap"])
    dbonus = dcap - dxi
    out = dict(row)
    out["delta_cap_bonus"] = round(dbonus, 4)
    if "delta_cap_oracle" in row and row["delta_cap_oracle"] not in ("", None):
        out["delta_cap_oracle"] = round(float(row["delta_cap_oracle"]), 4)
    for k in ("xi_changed", "squad_changed", "captain_changed", "captain_only_changed"):
        if k in row and row[k] not in ("", None):
            out[k] = int(row[k])
    out["sign_u"] = _sgn(du)
    out["sign_xi"] = _sgn(dxi)
    out["sign_cap"] = _sgn(dcap)
    out["sign_bonus"] = _sgn(dbonus)
    out["u_pos_cap_neg"] = int(du > SIGN_EPS and dcap < -SIGN_EPS)
    out["u_pos_xi_neg"] = int(du > SIGN_EPS and dxi < -SIGN_EPS)
    out["u_pos_xi_pos_cap_neg"] = int(du > SIGN_EPS and dxi > SIGN_EPS and dcap < -SIGN_EPS)
    out["u_pos_xi_neg_cap_neg"] = int(du > SIGN_EPS and dxi < -SIGN_EPS and dcap < -SIGN_EPS)
    return out


def analyze_season(season: str) -> list[dict]:
    ensure_vaastav((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E031 decomposition gate={gate} ===")
    rows: list[dict] = []

    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        snap = build_snapshot(season, as_of_gw=gw)
        act = gw_actuals(season, gw)
        if not act:
            continue

        recent = recent_minutes_by_element(season, gw, window=RECENT_WINDOW)
        v1 = project_all(
            snap, horizon=1, strategy="balanced", seed=SEED,
            minutes_version="v2am_s", rates_version="v1", fixtures_version="v1",
        )
        v2b = project_all(
            snap, horizon=1, strategy="balanced", seed=SEED,
            minutes_version="v2am_s", rates_version="v2b", fixtures_version="v1",
        )

        for strategy in STRATEGIES:
            packaged = apply_packaged_next_utility(
                v2b, v1, recent_minutes=recent, as_of_gw=gw, strategy=strategy,
            )
            v1_s = project_all(
                snap, horizon=1, strategy=strategy, seed=SEED,
                minutes_version="v2am_s", rates_version="v1", fixtures_version="v1",
            )
            try:
                sol_c = solve_squad(snap, v1_s, strategy=strategy, objective=OBJECTIVE)
                sol_t = solve_squad(snap, packaged, strategy=strategy, objective=OBJECTIVE)
            except RuntimeError:
                continue

            c_squad = {p.id for p in sol_c.players}
            t_squad = {p.id for p in sol_t.players}
            c_xi = {p.id for p in sol_c.xi}
            t_xi = {p.id for p in sol_t.xi}

            delta_u = sol_t.next_xi_utility - sol_c.next_xi_utility
            delta_xi_pts = xi_points(t_xi, act) - xi_points(c_xi, act)
            delta_cap = cap_points(sol_t, act) - cap_points(sol_c, act)

            cap_c_oracle = xi_cap_points(sol_c.xi, best_captain(sol_c.xi, act), act)
            cap_t_oracle = xi_cap_points(sol_t.xi, best_captain(sol_t.xi, act), act)
            delta_cap_oracle = cap_t_oracle - cap_c_oracle

            squad_changed = int(c_squad != t_squad)
            xi_changed = int(c_xi != t_xi)
            captain_changed = int(sol_c.captain.id != sol_t.captain.id)
            captain_only = int(
                not squad_changed and not xi_changed and captain_changed
            )

            row = enrich_row({
                "season": season,
                "e024_gate": gate,
                "gw": gw,
                "strategy": strategy,
                "delta_u_pred": round(delta_u, 4),
                "delta_xi_pts": round(delta_xi_pts, 4),
                "delta_cap": round(delta_cap, 4),
                "delta_cap_oracle": round(delta_cap_oracle, 4),
                "squad_changed": squad_changed,
                "xi_changed": xi_changed,
                "captain_changed": captain_changed,
                "captain_only_changed": captain_only,
            })
            rows.append(row)

    print(f"  gw-rows={len(rows)}")
    return rows


def load_e030_rows() -> list[dict]:
    if not E030_CSV.exists():
        raise FileNotFoundError(f"E030 CSV not found: {E030_CSV}")
    with E030_CSV.open(encoding="utf-8", newline="") as f:
        return [enrich_row(r) for r in csv.DictReader(f)]


def _pct(num: int, den: int) -> str:
    if den == 0:
        return "n/a"
    return f"{100.0 * num / den:.1f}% ({num}/{den})"


def _sign_table_u_cap(rows: list[dict]) -> tuple[int, int, int, int]:
    """Return (u+ cap+, u+ cap-, u- cap+, u- cap-)."""
    buckets = [0, 0, 0, 0]
    for r in rows:
        su, sc = r["sign_u"], r["sign_cap"]
        if su == 0 or sc == 0:
            continue
        idx = (0 if su > 0 else 2) + (0 if sc > 0 else 1)
        buckets[idx] += 1
    return tuple(buckets)  # type: ignore[return-value]


def _sign_table_u_xi(rows: list[dict]) -> tuple[int, int, int, int]:
    buckets = [0, 0, 0, 0]
    for r in rows:
        su, sx = r["sign_u"], r["sign_xi"]
        if su == 0 or sx == 0:
            continue
        idx = (0 if su > 0 else 2) + (0 if sx > 0 else 1)
        buckets[idx] += 1
    return tuple(buckets)  # type: ignore[return-value]


def summarize(rows: list[dict]) -> str:
    lines: list[str] = []
    lines.append("E031: objective-alignment decomposition (ctrl vs packaged rates_v2b)")
    lines.append("delta_cap_bonus = delta_cap - delta_xi_pts (captain double-count channel)")
    lines.append("delta_cap_oracle = oracle captain on each XI (hindsight upper bound)")
    lines.append("")

    has_oracle = any("delta_cap_oracle" in r for r in rows)

    for strategy in STRATEGIES:
        lines.append(f"=== strategy={strategy} ===")
        sr = [r for r in rows if r["strategy"] == strategy]
        for gate in ("FAIL", "PASS"):
            g = [r for r in sr if r["e024_gate"] == gate]
            gx = [r for r in g if int(r.get("xi_changed", 0) or 0)]
            n = len(g)
            if n < 3:
                lines.append(f"  {gate}: n={n} (too few)")
                continue

            du = [float(r["delta_u_pred"]) for r in g]
            dxi = [float(r["delta_xi_pts"]) for r in g]
            dcap = [float(r["delta_cap"]) for r in g]
            dbonus = [float(r["delta_cap_bonus"]) for r in g]

            lines.append(f"  {gate}: n={n} xi_changed={len(gx)}")
            lines.append(
                f"    corr(dU,dXI)={_pearson(du, dxi):.3f} "
                f"corr(dU,dCap)={_pearson(du, dcap):.3f} "
                f"corr(dU,dBonus)={_pearson(du, dbonus):.3f}"
            )
            if has_oracle:
                dor = [float(r["delta_cap_oracle"]) for r in g if "delta_cap_oracle" in r]
                if len(dor) >= 3:
                    lines.append(
                        f"    corr(dU,dCap_oracle)={_pearson(du[:len(dor)], dor):.3f} "
                        f"mean_dCap_oracle={statistics.mean(dor):.3f}"
                    )

            up, un, vp, vn = _sign_table_u_cap(g)
            lines.append(
                f"    sign(dU) x sign(dCap): u+cap+={up} u+cap-={un} u-cap+={vp} u-cap-={vn}"
            )
            up_xi, un_xi, vp_xi, vn_xi = _sign_table_u_xi(g)
            lines.append(
                f"    sign(dU) x sign(dXI):  u+xi+={up_xi} u+xi-={un_xi} u-xi+={vp_xi} u-xi-={vn_xi}"
            )

            flip = [r for r in g if r["u_pos_cap_neg"]]
            if flip:
                xi_neg = sum(r["u_pos_xi_neg_cap_neg"] for r in flip)
                xi_pos = sum(r["u_pos_xi_pos_cap_neg"] for r in flip)
                lines.append(
                    f"    dU>0 dCap<0: n={len(flip)} "
                    f"xi_neg={_pct(xi_neg, len(flip))} "
                    f"xi_pos_cap_neg={_pct(xi_pos, len(flip))}"
                )

            if has_oracle and flip:
                recover = [
                    float(r["delta_cap_oracle"]) - float(r["delta_cap"])
                    for r in flip
                    if "delta_cap_oracle" in r
                ]
                if recover:
                    lines.append(
                        f"    oracle - picked dCap on flip GWs: "
                        f"mean={statistics.mean(recover):.2f} "
                        f"(positive => oracle would improve vs picked)"
                    )

            if gx:
                du_x = [float(r["delta_u_pred"]) for r in gx]
                dxi_x = [float(r["delta_xi_pts"]) for r in gx]
                dcap_x = [float(r["delta_cap"]) for r in gx]
                lines.append(
                    f"    xi_changed only: n={len(gx)} "
                    f"corr(dU,dXI)={_pearson(du_x, dxi_x):.3f} "
                    f"corr(dU,dCap)={_pearson(du_x, dcap_x):.3f}"
                )

            if has_oracle:
                cap_chg = sum(int(r.get("captain_changed", 0)) for r in g)
                sq_chg = sum(int(r.get("squad_changed", 0)) for r in g)
                cap_only = sum(int(r.get("captain_only_changed", 0)) for r in g)
                lines.append(
                    f"    changes: squad={sq_chg} xi={sum(int(r.get('xi_changed',0)) for r in g)} "
                    f"captain={cap_chg} captain_only={cap_only}"
                )

        lines.append("")

    text = "\n".join(lines) + "\n"
    print(text)
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", choices=SUPPORTED_SEASONS)
    parser.add_argument(
        "--csv-only",
        action="store_true",
        help="sign tables from E030 CSV only (no oracle / change flags)",
    )
    args = parser.parse_args()

    if args.csv_only:
        print("[e031] csv-only mode: enrich E030 rows (no oracle captain)")
        all_rows = load_e030_rows()
        if args.season:
            all_rows = [r for r in all_rows if r["season"] == args.season]
    else:
        print("[e031] objective decomposition; balanced vs safe; no new objective")
        seasons = (args.season,) if args.season else SUPPORTED_SEASONS
        all_rows = []
        for s in seasons:
            all_rows.extend(analyze_season(s))

    base_fields = [
        "season", "e024_gate", "gw", "strategy",
        "delta_u_pred", "delta_xi_pts", "delta_cap", "delta_cap_bonus",
        "delta_cap_oracle",
        "squad_changed", "xi_changed", "captain_changed", "captain_only_changed",
        "sign_u", "sign_xi", "sign_cap", "sign_bonus",
        "u_pos_cap_neg", "u_pos_xi_neg", "u_pos_xi_pos_cap_neg", "u_pos_xi_neg_cap_neg",
    ]
    present = {k for r in all_rows for k in r}
    fields = [f for f in base_fields if f in present]

    OUT_GW.parent.mkdir(parents=True, exist_ok=True)
    with OUT_GW.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)
    print(f"Wrote {OUT_GW} ({len(all_rows)} rows)")
    summary = summarize(all_rows)
    OUT_TXT.write_text(summary, encoding="utf-8")
    print(f"Wrote {OUT_TXT}")


if __name__ == "__main__":
    main()
