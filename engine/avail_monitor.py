"""Live / snapshot monitor: is non-trivial FPL availability being applied?

Catches soft API degrade where bootstrap succeeds but every player reads as
fully available (status=a, availability()==1). Not an fplcache reachability check.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from engine.minutes import availability
from engine.models import Player

# Soft caution: mid-season panels historically show many demotions.
# Zero demotions on a full squad list is the dangerous "everyone's fine" mode.
WARN_IF_ZERO_DEMOTIONS = True
# Optional low-share caution (fraction of players with availability < 1).
LOW_SHARE_WARN = 0.01


def availability_application_report(players: list[Player]) -> dict[str, Any]:
    """Summarize whether availability() would demote anyone on this snapshot."""
    n = len(players)
    status_counts = Counter((p.status or "?") for p in players)
    n_not_a = sum(1 for p in players if (p.status or "a") != "a")
    n_avail_lt1 = 0
    n_chance_set = 0
    for p in players:
        if availability(p, 0) < 1.0 - 1e-12:
            n_avail_lt1 += 1
        if p.chance_this is not None or p.chance_next is not None:
            n_chance_set += 1

    share_not_a = (n_not_a / n) if n else 0.0
    share_avail_lt1 = (n_avail_lt1 / n) if n else 0.0

    warnings: list[str] = []
    if n == 0:
        warnings.append("empty_player_list")
    elif WARN_IF_ZERO_DEMOTIONS and n_avail_lt1 == 0:
        warnings.append("zero_availability_demotions")
    elif share_avail_lt1 < LOW_SHARE_WARN:
        warnings.append("very_low_availability_demotion_share")

    ok = len(warnings) == 0
    return {
        "ok": ok,
        "n_players": n,
        "n_status_not_a": n_not_a,
        "share_status_not_a": round(share_not_a, 6),
        "n_avail_lt1": n_avail_lt1,
        "share_avail_lt1": round(share_avail_lt1, 6),
        "n_chance_fields_set": n_chance_set,
        "status_counts": dict(sorted(status_counts.items())),
        "warnings": warnings,
        "note": (
            "Live soft-fail monitor: non-trivial availability application on "
            "snapshot Player fields via availability(player, 0). Not fplcache."
        ),
    }


def format_availability_monitor_line(report: dict[str, Any]) -> str:
    flag = "OK" if report.get("ok") else "WARN"
    warns = ",".join(report.get("warnings") or []) or "-"
    return (
        f"[avail_monitor] {flag} "
        f"n={report.get('n_players')} "
        f"status_not_a={report.get('n_status_not_a')} "
        f"({100.0 * float(report.get('share_status_not_a') or 0):.1f}%) "
        f"avail<1={report.get('n_avail_lt1')} "
        f"({100.0 * float(report.get('share_avail_lt1') or 0):.1f}%) "
        f"chance_set={report.get('n_chance_fields_set')} "
        f"warnings={warns}"
    )
