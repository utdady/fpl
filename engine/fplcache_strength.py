"""E047-A: dated fplcache team overall strengths (fixtures path only).

Selection rule: same as E044 — last cache snap with path-UTC ≤ GW deadline.
Slim extracts: data/fplcache_strength/{season}/gwNN.json
Fields: strength_overall_home / strength_overall_away only.
Does NOT touch ATK/CONCEDE tables (fixtures=v1 maps stay).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from engine.fplcache_avail import (
    COVERAGE_CSV,
    download_bootstrap_relpath,
    parse_snapshot_utc,
    pin_fplcache_sha,
    read_coverage_rows,
    snapshot_utc_to_relpath,
)
from engine.models import Snapshot, Team

ROOT = Path(__file__).resolve().parents[1]
SLIM_DIR = ROOT / "data" / "fplcache_strength"
MANIFEST_PATH = SLIM_DIR / "manifest.json"


@dataclass(frozen=True)
class StrengthFields:
    strength_home: int
    strength_away: int


@dataclass(frozen=True)
class StrengthDiag:
    team_id: int
    short_name: str
    strength_home_0: int
    strength_away_0: int
    strength_home_1: int
    strength_away_1: int
    replaced: bool
    identity_reason: str


def slim_path(season: str, gw: int) -> Path:
    return SLIM_DIR / season / f"gw{gw:02d}.json"


def _as_int(v: object, default: int = 3) -> int:
    if v is None or v == "":
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def extract_strengths(boot: dict) -> dict[int, StrengthFields]:
    out: dict[int, StrengthFields] = {}
    for t in boot.get("teams") or []:
        tid = t.get("id")
        if tid is None:
            continue
        out[int(tid)] = StrengthFields(
            strength_home=_as_int(t.get("strength_overall_home"), 3),
            strength_away=_as_int(t.get("strength_overall_away"), 3),
        )
    return out


def materialize_gw(season: str, gw: int, snapshot_utc: str, deadline_utc: str) -> Path:
    path = slim_path(season, gw)
    if path.exists():
        return path
    dt = parse_snapshot_utc(snapshot_utc)
    rel = snapshot_utc_to_relpath(dt)
    boot = download_bootstrap_relpath(rel)
    by_id = extract_strengths(boot)
    payload = {
        "season": season,
        "gw": gw,
        "deadline_utc": deadline_utc,
        "snapshot_utc": snapshot_utc,
        "cache_relpath": rel,
        "n_teams": len(by_id),
        "by_id": {
            str(k): {"strength_home": v.strength_home, "strength_away": v.strength_away}
            for k, v in sorted(by_id.items())
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return path


def ensure_fplcache_strength(
    seasons: tuple[str, ...] | None = None,
    *,
    force: bool = False,
) -> dict:
    rows = read_coverage_rows()
    wanted = set(seasons) if seasons else None
    SLIM_DIR.mkdir(parents=True, exist_ok=True)
    done = skipped = 0
    for row in rows:
        if row.get("pre_deadline_ok", "").lower() not in {"true", "1"}:
            continue
        season = row["season"]
        if wanted is not None and season not in wanted:
            continue
        gw = int(row["gw"])
        path = slim_path(season, gw)
        if path.exists() and not force:
            skipped += 1
            continue
        if force and path.exists():
            path.unlink()
        materialize_gw(season, gw, row["last_pre_snapshot_utc"], row["deadline_utc"])
        done += 1
        if done % 10 == 0:
            print(f"[fplcache_strength] materialized {done} new GW files…", flush=True)
    sha = pin_fplcache_sha()
    man = {
        "fplcache_sha": sha,
        "coverage_csv": COVERAGE_CSV.as_posix(),
        "slim_dir": SLIM_DIR.as_posix(),
        "n_existing": sum(1 for _ in SLIM_DIR.glob("*/gw*.json")),
        "newly_written": done,
        "skipped_existing": skipped,
        "fields": ["strength_overall_home", "strength_overall_away"],
    }
    MANIFEST_PATH.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    return man


def load_strengths(season: str, gw: int) -> dict[int, StrengthFields] | None:
    path = slim_path(season, gw)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[int, StrengthFields] = {}
    for k, v in (data.get("by_id") or {}).items():
        out[int(k)] = StrengthFields(
            strength_home=_as_int(v.get("strength_home"), 3),
            strength_away=_as_int(v.get("strength_away"), 3),
        )
    return out


def hydrate_snapshot_teams(
    snapshot: Snapshot,
    *,
    season: str | None,
    as_of_gw: int,
) -> tuple[Snapshot, list[StrengthDiag]]:
    """Replace Team.strength_* from dated overlay. Identity if no season/overlay."""
    diags: list[StrengthDiag] = []
    if not season:
        for t in snapshot.teams.values():
            diags.append(
                StrengthDiag(
                    t.id, t.short_name, t.strength_home, t.strength_away,
                    t.strength_home, t.strength_away, False, "no_season",
                )
            )
        return snapshot, diags

    overlay = load_strengths(season, as_of_gw)
    if overlay is None:
        for t in snapshot.teams.values():
            diags.append(
                StrengthDiag(
                    t.id, t.short_name, t.strength_home, t.strength_away,
                    t.strength_home, t.strength_away, False, "no_overlay",
                )
            )
        return snapshot, diags

    new_teams: dict[int, Team] = {}
    n_replaced = 0
    for tid, t0 in snapshot.teams.items():
        ov = overlay.get(tid)
        if ov is None:
            new_teams[tid] = t0
            diags.append(
                StrengthDiag(
                    tid, t0.short_name, t0.strength_home, t0.strength_away,
                    t0.strength_home, t0.strength_away, False, "missing_team",
                )
            )
            continue
        t1 = replace(t0, strength_home=ov.strength_home, strength_away=ov.strength_away)
        new_teams[tid] = t1
        changed = (t0.strength_home != t1.strength_home) or (
            t0.strength_away != t1.strength_away
        )
        n_replaced += int(changed)
        diags.append(
            StrengthDiag(
                tid, t0.short_name, t0.strength_home, t0.strength_away,
                t1.strength_home, t1.strength_away, changed, "",
            )
        )
    return replace(snapshot, teams=new_teams), diags
