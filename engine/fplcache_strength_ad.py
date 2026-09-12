"""E053-A: dated fplcache team attack/defence strengths (fixtures path only).

Selection rule: same as E044 — last cache snap with path-UTC ≤ GW deadline.
Slim extracts: data/fplcache_strength_ad/{season}/gwNN.json
Fields: strength_attack_* / strength_defence_* only (not overall).
Does NOT touch ATK/CONCEDE tables or Team.strength_*.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from engine.fplcache_avail import (
    COVERAGE_CSV,
    download_bootstrap_relpath,
    parse_snapshot_utc,
    pin_fplcache_sha,
    read_coverage_rows,
    snapshot_utc_to_relpath,
)

ROOT = Path(__file__).resolve().parents[1]
SLIM_DIR = ROOT / "data" / "fplcache_strength_ad"
MANIFEST_PATH = SLIM_DIR / "manifest.json"


@dataclass(frozen=True)
class AdxgFields:
    attack_home: int
    attack_away: int
    defence_home: int
    defence_away: int


def slim_path(season: str, gw: int) -> Path:
    return SLIM_DIR / season / f"gw{gw:02d}.json"


def _as_int(v: object, default: int = 0) -> int:
    if v is None or v == "":
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def extract_adxg(boot: dict) -> dict[int, AdxgFields]:
    out: dict[int, AdxgFields] = {}
    for t in boot.get("teams") or []:
        tid = t.get("id")
        if tid is None:
            continue
        out[int(tid)] = AdxgFields(
            attack_home=_as_int(t.get("strength_attack_home"), 0),
            attack_away=_as_int(t.get("strength_attack_away"), 0),
            defence_home=_as_int(t.get("strength_defence_home"), 0),
            defence_away=_as_int(t.get("strength_defence_away"), 0),
        )
    return out


def materialize_gw(season: str, gw: int, snapshot_utc: str, deadline_utc: str) -> Path:
    path = slim_path(season, gw)
    if path.exists():
        return path
    dt = parse_snapshot_utc(snapshot_utc)
    rel = snapshot_utc_to_relpath(dt)
    boot = download_bootstrap_relpath(rel)
    by_id = extract_adxg(boot)
    payload = {
        "season": season,
        "gw": gw,
        "deadline_utc": deadline_utc,
        "snapshot_utc": snapshot_utc,
        "cache_relpath": rel,
        "n_teams": len(by_id),
        "by_id": {
            str(k): {
                "attack_home": v.attack_home,
                "attack_away": v.attack_away,
                "defence_home": v.defence_home,
                "defence_away": v.defence_away,
            }
            for k, v in sorted(by_id.items())
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return path


def ensure_fplcache_strength_ad(
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
            print(f"[fplcache_strength_ad] materialized {done} new GW files…", flush=True)
    sha = pin_fplcache_sha()
    man = {
        "fplcache_sha": sha,
        "coverage_csv": COVERAGE_CSV.as_posix(),
        "slim_dir": SLIM_DIR.as_posix(),
        "n_existing": sum(1 for _ in SLIM_DIR.glob("*/gw*.json")),
        "newly_written": done,
        "skipped_existing": skipped,
        "fields": [
            "strength_attack_home",
            "strength_attack_away",
            "strength_defence_home",
            "strength_defence_away",
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    return man


def load_adxg(season: str, gw: int) -> dict[int, AdxgFields] | None:
    path = slim_path(season, gw)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[int, AdxgFields] = {}
    for k, v in (data.get("by_id") or {}).items():
        out[int(k)] = AdxgFields(
            attack_home=_as_int(v.get("attack_home"), 0),
            attack_away=_as_int(v.get("attack_away"), 0),
            defence_home=_as_int(v.get("defence_home"), 0),
            defence_away=_as_int(v.get("defence_away"), 0),
        )
    return out
