"""E045-A: dated fplcache ep_next overlays (rates path only).

Selection rule: same as E044 — last cache snap with path-UTC ≤ GW deadline.
Slim extracts: data/fplcache_ep/{season}/gw{NN}.json
Does NOT hydrate Player.ep_next (minutes path must stay blind).
"""
from __future__ import annotations

import json
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
SLIM_DIR = ROOT / "data" / "fplcache_ep"
MANIFEST_PATH = SLIM_DIR / "manifest.json"

EP_LAMBDA = 0.35


def slim_path(season: str, gw: int) -> Path:
    return SLIM_DIR / season / f"gw{gw:02d}.json"


def _as_float(v: object) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def extract_ep_next(boot: dict) -> dict[int, float]:
    out: dict[int, float] = {}
    for el in boot.get("elements") or []:
        eid = el.get("id")
        if eid is None:
            continue
        ep = _as_float(el.get("ep_next"))
        if ep is None:
            continue
        out[int(eid)] = ep
    return out


def materialize_gw(season: str, gw: int, snapshot_utc: str, deadline_utc: str) -> Path:
    path = slim_path(season, gw)
    if path.exists():
        return path
    dt = parse_snapshot_utc(snapshot_utc)
    rel = snapshot_utc_to_relpath(dt)
    boot = download_bootstrap_relpath(rel)
    by_id = extract_ep_next(boot)
    payload = {
        "season": season,
        "gw": gw,
        "deadline_utc": deadline_utc,
        "snapshot_utc": snapshot_utc,
        "cache_relpath": rel,
        "n_ep_next": len(by_id),
        "by_id": {str(k): v for k, v in sorted(by_id.items())},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return path


def ensure_fplcache_ep(
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
            print(f"[fplcache_ep] materialized {done} new GW files…", flush=True)
    sha = pin_fplcache_sha()
    man = {
        "fplcache_sha": sha,
        "coverage_csv": COVERAGE_CSV.as_posix(),
        "slim_dir": SLIM_DIR.as_posix(),
        "n_existing": sum(1 for _ in SLIM_DIR.glob("*/gw*.json")),
        "newly_written": done,
        "skipped_existing": skipped,
        "lambda": EP_LAMBDA,
    }
    MANIFEST_PATH.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    return man


def load_ep_next(season: str, gw: int) -> dict[int, float] | None:
    path = slim_path(season, gw)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[int, float] = {}
    for k, v in (data.get("by_id") or {}).items():
        ep = _as_float(v)
        if ep is None:
            continue
        out[int(k)] = ep
    return out


def blend_mu(mu0: float, ep_next: float | None, *, lam: float = EP_LAMBDA) -> tuple[float, bool]:
    """Return (mu1, blended). Identity if ep_next is None."""
    if ep_next is None:
        return float(mu0), False
    return (1.0 - lam) * float(mu0) + lam * float(ep_next), True
