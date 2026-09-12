"""E052-A Phase-1: fixtures=v1_sxg vs fixtures=v1 (projection-only).

Usage:
    python -m engine.harness_v1_sxg
    python -m engine.harness_v1_sxg --season 2024-25
    python -m engine.harness_v1_sxg --smoke-gw 20 --season 2024-25

Both arms: minutes=v2am_fpla, rates=v1, seed=7.
Control fixtures=v1 (no hydrate). Treatment fixtures=v1_sxg + dated hydrate.
Phase-1 only: MAE/Spearman/RMSE/bias/n_mu_delta — NO Cap / XI0 / ILP.
Production stays fixtures=v1 until Phase-2 SURVIVE + promote.
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
from pathlib import Path

from engine.fplcache_avail import ensure_fplcache_avail
from engine.fplcache_strength import ensure_fplcache_strength
from engine.harness import SUPPORTED_SEASONS, build_snapshot, ensure_vaastav, gw_actuals
from engine.metrics import record_path, spearman
from engine.project import project_all

OUT_DIR = Path("records") / "historical"
SEED = 7
FAIL_SEASONS = {"2022-23", "2025-26"}
PASS_SEASONS = {"2023-24", "2024-25"}


def _mae(preds, acts):
    if not preds:
        return float("nan")
    return statistics.mean(abs(a - p) for p, a in zip(preds, acts))


def _rmse(preds, acts):
    if not preds:
        return float("nan")
    return math.sqrt(statistics.mean((a - p) ** 2 for p, a in zip(preds, acts)))


def _bias(preds, acts):
    if not preds:
        return float("nan")
    return statistics.mean(p - a for p, a in zip(preds, acts))


def count_mu_delta(ctrl, treat, eps: float = 1e-9) -> int:
    by_t = {p.player.id: p for p in treat}
    n = 0
    for p in ctrl:
        q = by_t.get(p.player.id)
        if q is None:
            continue
        if abs(float(p.next_mu) - float(q.next_mu)) > eps:
            n += 1
    return n


def eval_season(
    season: str,
    strategy: str = "balanced",
    *,
    smoke_gw: int | None = None,
) -> dict:
    ensure_vaastav((season,))
    ensure_fplcache_avail((season,))
    ensure_fplcache_strength((season,))
    gate = "FAIL" if season in FAIL_SEASONS else ("PASS" if season in PASS_SEASONS else "?")
    print(f"\n=== {season} E052-A Phase-1 v1_sxg (control=fixtures=v1) gate={gate} ===")

    ctrl_mae_p, ctrl_mae_a = [], []
    treat_mae_p, treat_mae_a = [], []
    n_mu_delta = 0
    n_proj = 0
    gws = [smoke_gw] if smoke_gw is not None else list(range(1, 39))

    for gw in gws:
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
        treat = project_all(
            snap, horizon=1, strategy=strategy, seed=SEED,
            minutes_version="v2am_fpla", rates_version="v1", fixtures_version="v1_sxg",
        )
        n_mu_delta += count_mu_delta(ctrl, treat)
        n_proj += len(ctrl)

        for proj in ctrl:
            a = act.get(proj.player.id)
            if not a:
                continue
            if float(a.get("actual_minutes", 0) or 0) >= 60:
                ctrl_mae_p.append(proj.next_mu)
                ctrl_mae_a.append(float(a.get("actual_points", 0) or 0))
        for proj in treat:
            a = act.get(proj.player.id)
            if not a:
                continue
            if float(a.get("actual_minutes", 0) or 0) >= 60:
                treat_mae_p.append(proj.next_mu)
                treat_mae_a.append(float(a.get("actual_points", 0) or 0))

    c_mae = _mae(ctrl_mae_p, ctrl_mae_a)
    t_mae = _mae(treat_mae_p, treat_mae_a)
    c_rmse = _rmse(ctrl_mae_p, ctrl_mae_a)
    t_rmse = _rmse(treat_mae_p, treat_mae_a)
    c_bias = _bias(ctrl_mae_p, ctrl_mae_a)
    t_bias = _bias(treat_mae_p, treat_mae_a)
    c_sp = spearman(ctrl_mae_p, ctrl_mae_a)
    t_sp = spearman(treat_mae_p, treat_mae_a)
    n60 = len(ctrl_mae_p)

    mae_ok = (not math.isnan(t_mae)) and (not math.isnan(c_mae)) and t_mae <= c_mae + 1e-9
    identity_null = n_mu_delta == 0
    phase1_ok = mae_ok and not identity_null

    r = {
        "season": season,
        "e024_gate": gate,
        "ctrl_mae60": c_mae,
        "treat_mae60": t_mae,
        "ctrl_rmse60": c_rmse,
        "treat_rmse60": t_rmse,
        "ctrl_bias60": c_bias,
        "treat_bias60": t_bias,
        "ctrl_spearman60": c_sp,
        "treat_spearman60": t_sp,
        "n60": n60,
        "n_mu_delta": n_mu_delta,
        "n_proj": n_proj,
        "mae60_ok": mae_ok,
        "identity_null": identity_null,
        "phase1_ok": phase1_ok,
    }
    print(
        f"  MAE60 {c_mae:.4f}->{t_mae:.4f} ok={mae_ok}  "
        f"Sp {c_sp:.3f}->{t_sp:.3f}  "
        f"RMSE {c_rmse:.4f}->{t_rmse:.4f}  "
        f"bias {c_bias:.4f}->{t_bias:.4f}  "
        f"n_mu_delta={n_mu_delta}/{n_proj} identity_null={identity_null}  "
        f"phase1_ok={phase1_ok}"
    )
    return r


def write_summary(results: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "season", "e024_gate",
        "ctrl_mae60", "treat_mae60", "mae60_ok",
        "ctrl_rmse60", "treat_rmse60",
        "ctrl_bias60", "treat_bias60",
        "ctrl_spearman60", "treat_spearman60",
        "n60", "n_mu_delta", "n_proj", "identity_null", "phase1_ok",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k) for k in cols})


def write_verdict(results: list[dict], path: Path) -> None:
    mae_all = all(r["mae60_ok"] for r in results) if results else False
    any_null = any(r["identity_null"] for r in results) if results else True
    total_delta = sum(int(r["n_mu_delta"]) for r in results)
    sp_c = [r["ctrl_spearman60"] for r in results if not math.isnan(r["ctrl_spearman60"])]
    sp_t = [r["treat_spearman60"] for r in results if not math.isnan(r["treat_spearman60"])]
    sp_agg_c = statistics.mean(sp_c) if sp_c else float("nan")
    sp_agg_t = statistics.mean(sp_t) if sp_t else float("nan")
    sp_agg_ok = (
        (not math.isnan(sp_agg_t)) and (not math.isnan(sp_agg_c))
        and sp_agg_t + 1e-12 >= sp_agg_c
    )
    # Survive Phase-1 only if MAE hard on all seasons AND not identity-null overall
    survive = mae_all and total_delta > 0 and not any_null
    # Soft Spearman reported; does not override MAE hard fail
    lines = [
        "E052-A Phase-1 verdict: fixtures=v1_sxg vs v1",
        f"seasons={len(results)} mae60_all_ok={mae_all} "
        f"total_n_mu_delta={total_delta} any_season_identity_null={any_null}",
        f"Spearman AGG mean ctrl={sp_agg_c:.4f} treat={sp_agg_t:.4f} soft_ok={sp_agg_ok}",
        f"VERDICT={'SURVIVES' if survive else 'KILL'} Phase-1",
        "Phase-2 Cap/XI0 NOT opened (forbidden until Phase-1 SURVIVES).",
    ]
    for r in results:
        lines.append(
            f"  {r['season']} gate={r['e024_gate']} "
            f"MAE {r['ctrl_mae60']:.4f}->{r['treat_mae60']:.4f} ok={r['mae60_ok']} "
            f"Sp {r['ctrl_spearman60']:.3f}->{r['treat_spearman60']:.3f} "
            f"delta={r['n_mu_delta']} null={r['identity_null']}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="E052-A Phase-1: fixtures=v1_sxg vs v1.")
    parser.add_argument("--season", choices=SUPPORTED_SEASONS, default=None)
    parser.add_argument(
        "--smoke-gw", type=int, default=None,
        help="Single GW smoke (e.g. 20); skip full Phase-1 verdict",
    )
    args = parser.parse_args()

    print("[e052] Control = minutes=v2am_fpla + rates=v1 + fixtures=v1")
    print("[e052] Treatment = fixtures=v1_sxg + dated fplcache strength hydrate")
    print("[e052] Phase-1 projection only — no Cap/XI0/ILP")
    print("[e052] Production stays fixtures=v1")

    seasons = (args.season,) if args.season else SUPPORTED_SEASONS
    results = [
        eval_season(s, smoke_gw=args.smoke_gw) for s in seasons
    ]
    if args.smoke_gw is not None:
        tag = f"smoke_gw{args.smoke_gw}"
        if args.season:
            write_summary(results, OUT_DIR / f"v1_sxg_{tag}_{args.season}.csv")
        else:
            write_summary(results, OUT_DIR / f"v1_sxg_{tag}.csv")
        print(f"[e052] smoke done (GW{args.smoke_gw}); not a Phase-1 verdict")
        return

    if args.season:
        write_summary(results, OUT_DIR / f"v1_sxg_phase1_{args.season}.csv")
        write_verdict(results, OUT_DIR / f"e052_phase1_verdict_{args.season}.txt")
    else:
        write_summary(results, OUT_DIR / "v1_sxg_phase1_summary.csv")
        write_verdict(results, OUT_DIR / "e052_phase1_verdict.txt")


if __name__ == "__main__":
    main()
