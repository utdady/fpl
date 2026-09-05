"""E041-A frozen Bench Boost policy (shared offline ↔ product).

Contract (docs/LAB_LOG.md E041-A):
  C: t* = argmax_t U_bench(t), tie → lowest GW
  U_bench(t) = sum next_utility over sol.bench after solve_squad (objective=next)
  Stack: same as E040-A (v2am_s + rates=v1 + fixtures v1)

Live semantics: same as E040-A (charter §19 / §22) —
  past as-of-t when rebuildable; current+future under I_N only.

Independent of TC. Any policy change requires a new preregistered experiment.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from engine.e040_tc_policy import (
    OBJECTIVE,
    STRATEGY,
    bind_next_to_event,
    project_e040,
)
from engine.models import PlayerProjection, Snapshot
from engine.optimize import solve_squad

G_STAR = 20  # B1 benchmark only
POLICY_ID = "E041-A"

CLAIM = (
    "Under the frozen E041-A policy, the model recommends Bench Boost "
    "in the GW where projected bench utility is highest."
)

LIVE_SEMANTICS = (
    "Past GWs use as-of-t freezes when available; current and future GWs "
    "are scored under the current information set I_N only "
    "(unique online completion of argmax U_bench)."
)

# Product guardrail — not a joint-chip policy (charter §22 / §23).
INDEPENDENCE = (
    "Independent of Triple Captain (E040-A): this is not a combined chip calendar. "
    "TC and BB may recommend different GWs; joint feasibility is not claimed."
)


@dataclass(frozen=True)
class BenchRow:
    gw: int
    u_bench: float
    bench_ids: tuple[int, ...]
    bench_names: tuple[str, ...]
    source: str  # "as_of_t" | "live_I_N"


@dataclass(frozen=True)
class BBRecommendation:
    policy_id: str
    t_star: int
    u_bench: float
    bench_ids: tuple[int, ...]
    bench_names: tuple[str, ...]
    claim: str
    rows: tuple[BenchRow, ...]
    live_semantics: str


def select_t_star(rows: Iterable[BenchRow]) -> BenchRow:
    """C: argmax U_bench; tie → lowest GW."""
    rows = list(rows)
    if not rows:
        raise ValueError("select_t_star requires at least one BenchRow")
    return sorted(rows, key=lambda r: (-r.u_bench, r.gw))[0]


def bench_row_from_projections(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    gw: int,
    *,
    source: str,
) -> BenchRow | None:
    try:
        sol = solve_squad(
            snapshot, projections, strategy=STRATEGY, objective=OBJECTIVE
        )
    except RuntimeError:
        return None
    by_id = {p.player.id: p for p in projections}
    bench = list(sol.bench)
    u_bench = sum(by_id[p.id].next_utility for p in bench)
    return BenchRow(
        gw=gw,
        u_bench=float(u_bench),
        bench_ids=tuple(p.id for p in bench),
        bench_names=tuple(p.web_name for p in bench),
        source=source,
    )


def rows_as_of_t_season(season: str) -> list[BenchRow]:
    from engine.harness import build_snapshot, ensure_vaastav, gw_actuals
    from engine.metrics import record_path

    ensure_vaastav((season,))
    rows: list[BenchRow] = []
    for gw in range(1, 39):
        if not record_path(gw, season=season).exists():
            continue
        snap = build_snapshot(season, as_of_gw=gw)
        if not gw_actuals(season, gw):
            continue
        projections = project_e040(snap, horizon=1)
        row = bench_row_from_projections(snap, projections, gw, source="as_of_t")
        if row is not None:
            rows.append(row)
    return rows


def rows_live_remaining(snapshot: Snapshot) -> list[BenchRow]:
    next_e = snapshot.next_event()
    remaining = [e.id for e in snapshot.events if e.id >= next_e.id and e.id <= 38]
    if not remaining:
        return []
    projections = project_e040(snapshot, horizon=len(remaining))
    rows: list[BenchRow] = []
    for gw in remaining:
        bound = bind_next_to_event(projections, gw)
        row = bench_row_from_projections(snapshot, bound, gw, source="live_I_N")
        if row is not None:
            rows.append(row)
    return rows


def recommend_from_rows(rows: list[BenchRow]) -> BBRecommendation:
    best = select_t_star(rows)
    return BBRecommendation(
        policy_id=POLICY_ID,
        t_star=best.gw,
        u_bench=best.u_bench,
        bench_ids=best.bench_ids,
        bench_names=best.bench_names,
        claim=CLAIM,
        rows=tuple(rows),
        live_semantics=LIVE_SEMANTICS,
    )


def recommend_historical(season: str) -> BBRecommendation:
    return recommend_from_rows(rows_as_of_t_season(season))


def recommend_live(snapshot: Snapshot) -> BBRecommendation:
    rows = rows_live_remaining(snapshot)
    if not rows:
        raise RuntimeError("No remaining GWs to score for E041-A BB recommendation")
    return recommend_from_rows(rows)


def format_recommendation(rec: BBRecommendation) -> str:
    bench = ", ".join(rec.bench_names)
    lines = [
        f"Policy: {rec.policy_id} (frozen Bench Boost)",
        rec.claim,
        INDEPENDENCE,
        "",
        f"  planned GW:  {rec.t_star}",
        f"  bench:       {bench}",
        f"  U_bench(t*): {rec.u_bench:.4f}",
        f"  incremental: ~{rec.u_bench:.4f} projected pts vs no-BB "
        f"(BB adds bench xP under mu)",
        "",
        f"Live semantics: {rec.live_semantics}",
        f"Scored GWs: {len(rec.rows)}",
    ]
    return "\n".join(lines) + "\n"
