"""PRODUCT: k-best squad landscape on frozen Model A.

Not an E-card. Live snapshot first; historical only after a manual inspect.

    python scripts/kbest_landscape.py --live
    python scripts/kbest_landscape.py --historical
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.api import load_snapshot
from engine.candidates import Candidate, format_squad, solve_k_best
from engine.fplcache_avail import ensure_fplcache_avail
from engine.harness import build_snapshot, ensure_vaastav
from engine.model_config import PRODUCTION
from engine.project import project_all

OUT_DIR = ROOT / "records" / "historical"
SEED = 7
K = 10
OBJECTIVE = "horizon"
FAIL_SEASONS = ("2022-23", "2025-26")
PASS_SEASONS = ("2023-24", "2024-25")
HIST_GWS = (4, 18, 32)

LIVE_CSV = OUT_DIR / "kbest_live_candidates.csv"
LIVE_TXT = OUT_DIR / "kbest_live_summary.txt"
HIST_CSV = OUT_DIR / "kbest_landscape_gw.csv"
HIST_TXT = OUT_DIR / "kbest_landscape_summary.txt"

CSV_FIELDS = [
    "scope",
    "season",
    "gw",
    "gate",
    "rank",
    "u",
    "delta_u",
    "distance",
    "jaccard",
    "bank",
    "cost",
    "club_max",
    "minutes_risk",
    "captain",
    "vice",
    "enters",
    "exits",
    "ids",
    "names",
]


def _project(snapshot):
    return project_all(
        snapshot,
        horizon=PRODUCTION["horizon_resolv"],
        strategy=PRODUCTION["strategy"],
        seed=SEED,
        minutes_version=PRODUCTION["minutes_version"],
        rates_version=PRODUCTION["rates_version"],
        fixtures_version="v1",
    )


def _row(scope: str, season: str, gw: int, gate: str, cand: Candidate) -> dict:
    d = cand.diagnostics
    return {
        "scope": scope,
        "season": season,
        "gw": gw,
        "gate": gate,
        "rank": d.rank,
        "u": f"{d.u:.4f}",
        "delta_u": f"{d.delta_u:.4f}",
        "distance": d.distance,
        "jaccard": f"{d.jaccard:.4f}",
        "bank": d.bank,
        "cost": d.cost,
        "club_max": d.club_max,
        "minutes_risk": d.minutes_risk,
        "captain": d.captain,
        "vice": d.vice,
        "enters": ";".join(d.enters),
        "exits": ";".join(d.exits),
        "ids": " ".join(str(i) for i in sorted(d.ids)),
        "names": ";".join(d.names),
    }


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)


def _table_lines(pool: list[Candidate]) -> list[str]:
    lines = [
        f"{'rank':>4}  {'U':>8}  {'dU':>7}  {'D':>3}  {'Jac':>6}  "
        f"{'bank':>5}  {'club':>4}  {'risk':>4}  C / VC  enters -> exits"
    ]
    for c in pool:
        d = c.diagnostics
        swap = ""
        if d.distance:
            swap = f"{', '.join(d.enters)} <- {', '.join(d.exits)}"
        lines.append(
            f"{d.rank:4d}  {d.u:8.2f}  {d.delta_u:7.2f}  {d.distance:3d}  "
            f"{d.jaccard:6.3f}  {d.bank:5d}  {d.club_max:4d}  {d.minutes_risk:4d}  "
            f"{d.captain} / {d.vice}  {swap}"
        )
    return lines


def run_live(*, k: int, refresh: bool) -> list[Candidate]:
    snapshot = load_snapshot(refresh=refresh)
    nxt = snapshot.next_event()
    print(
        f"LIVE  {snapshot.season_label}  next=GW{nxt.id}  "
        f"as_of={snapshot.as_of.isoformat()}  Model A {PRODUCTION}"
    )
    projections = _project(snapshot)
    pool = solve_k_best(
        snapshot,
        projections,
        strategy=PRODUCTION["strategy"],
        k=k,
        objective=OBJECTIVE,
    )
    rows = [
        _row("live", snapshot.season_label, nxt.id, "live", c) for c in pool
    ]
    _write_csv(LIVE_CSV, rows)
    lines = [
        "PRODUCT k-best live snapshot (inspect before --historical)",
        f"season={snapshot.season_label} gw={nxt.id} k={len(pool)}",
        "",
        *_table_lines(pool),
        "",
    ]
    for c in pool:
        lines.append(f"S{c.rank}: {format_squad(c.solution)}")
        lines.append("")
    LIVE_TXT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"wrote {LIVE_CSV}")
    print(f"wrote {LIVE_TXT}")
    return pool


def run_historical(*, k: int) -> list[dict]:
    rows: list[dict] = []
    blocks: list[str] = [
        "PRODUCT k-best historical landscape (Model A, not an E-card)",
        f"k={k} objective={OBJECTIVE} snapshots={len(FAIL_SEASONS)+len(PASS_SEASONS)}x{len(HIST_GWS)}",
        "",
    ]
    for season in (*FAIL_SEASONS, *PASS_SEASONS):
        gate = "FAIL" if season in FAIL_SEASONS else "PASS"
        ensure_vaastav((season,))
        ensure_fplcache_avail((season,))
        for gw in HIST_GWS:
            print(f"  [{season}] GW{gw} ({gate})")
            snap = build_snapshot(season, as_of_gw=gw)
            projections = _project(snap)
            pool = solve_k_best(
                snap,
                projections,
                strategy=PRODUCTION["strategy"],
                k=k,
                objective=OBJECTIVE,
            )
            for c in pool:
                rows.append(_row("historical", season, gw, gate, c))
            blocks.append(f"=== {season} GW{gw} {gate}  n={len(pool)} ===")
            blocks.extend(_table_lines(pool))
            interesting = [c for c in pool if c.diagnostics.distance >= 3]
            if interesting:
                blocks.append("what changed (D>=3):")
                for c in interesting:
                    d = c.diagnostics
                    blocks.append(
                        f"  S{d.rank} dU={d.delta_u:.2f} D={d.distance} "
                        f"in={', '.join(d.enters)} out={', '.join(d.exits)}"
                    )
            blocks.append("")
    _write_csv(HIST_CSV, rows)
    HIST_TXT.write_text("\n".join(blocks), encoding="utf-8")
    print("\n".join(blocks))
    print(f"wrote {HIST_CSV}")
    print(f"wrote {HIST_TXT}")
    return rows


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="PRODUCT k-best landscape (Model A)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--live", action="store_true")
    group.add_argument("--historical", action="store_true")
    parser.add_argument("--k", type=int, default=K)
    parser.add_argument("--refresh", action="store_true", help="refresh live FPL cache")
    args = parser.parse_args()
    if args.live:
        run_live(k=args.k, refresh=args.refresh)
        return
    run_historical(k=args.k)


if __name__ == "__main__":
    main()
