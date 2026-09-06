"""E044-A: decision-time FPL availability from Randdalf/fplcache.

Selection rule (LAB_LOG E044-A):
  last cache/{Y}/{M}/{D}/{HHMM}.json.xz with path-UTC ≤ GW deadline.
Slim per-GW extracts under data/fplcache_avail/{season}/gw{NN}.json.
"""
from __future__ import annotations

import csv
import json
import lzma
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from engine.models import Player

ROOT = Path(__file__).resolve().parents[1]
SLIM_DIR = ROOT / "data" / "fplcache_avail"
COVERAGE_CSV = ROOT / "records" / "historical" / "e044_fplcache_deadline_coverage.csv"
MANIFEST_PATH = SLIM_DIR / "manifest.json"

FPLCACHE_RAW = "https://raw.githubusercontent.com/Randdalf/fplcache/main/cache"
FPLCACHE_API = "https://api.github.com/repos/Randdalf/fplcache"
USER_AGENT = "fpl-e044-a-v2am-fpla (local research)"


@dataclass(frozen=True)
class AvailFields:
    status: str
    chance_this: int | None
    chance_next: int | None
    can_select: bool
    code: int | None = None


def _get_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def _get_json(url: str) -> object:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def parse_snapshot_utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def snapshot_utc_to_relpath(dt: datetime) -> str:
    """Match Randdalf/fplcache layout: year/month/day/HHMM.json.xz (no zero-pad M/D)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return f"{dt.year}/{dt.month}/{dt.day}/{dt.hour:02d}{dt.minute:02d}.json.xz"


def slim_path(season: str, gw: int) -> Path:
    return SLIM_DIR / season / f"gw{gw:02d}.json"


def _as_int(v: object) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def extract_avail_from_bootstrap(boot: dict) -> dict[int, AvailFields]:
    out: dict[int, AvailFields] = {}
    for el in boot.get("elements") or []:
        eid = _as_int(el.get("id"))
        if eid is None:
            continue
        status = str(el.get("status") or "a")
        if "can_select" in el and el.get("can_select") is not None:
            can_select = bool(el.get("can_select"))
        else:
            can_select = status not in {"u", "n"}
        out[eid] = AvailFields(
            status=status,
            chance_this=_as_int(el.get("chance_of_playing_this_round")),
            chance_next=_as_int(el.get("chance_of_playing_next_round")),
            can_select=can_select,
            code=_as_int(el.get("code")),
        )
    return out


def download_bootstrap_relpath(rel: str) -> dict:
    url = f"{FPLCACHE_RAW}/{rel}"
    raw = _get_bytes(url)
    return json.loads(lzma.decompress(raw))


def read_coverage_rows() -> list[dict[str, str]]:
    if not COVERAGE_CSV.exists():
        raise FileNotFoundError(
            f"Missing {COVERAGE_CSV}; run scripts/e044_availability_source_survey.py first"
        )
    with COVERAGE_CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def materialize_gw(season: str, gw: int, snapshot_utc: str, deadline_utc: str) -> Path:
    path = slim_path(season, gw)
    if path.exists():
        return path
    dt = parse_snapshot_utc(snapshot_utc)
    rel = snapshot_utc_to_relpath(dt)
    boot = download_bootstrap_relpath(rel)
    by_id = extract_avail_from_bootstrap(boot)
    payload = {
        "season": season,
        "gw": gw,
        "deadline_utc": deadline_utc,
        "snapshot_utc": snapshot_utc,
        "cache_relpath": rel,
        "n_elements": len(by_id),
        "by_id": {
            str(eid): {
                "status": f.status,
                "chance_this": f.chance_this,
                "chance_next": f.chance_next,
                "can_select": f.can_select,
                "code": f.code,
            }
            for eid, f in sorted(by_id.items())
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return path


def pin_fplcache_sha() -> str | None:
    try:
        meta = _get_json(f"{FPLCACHE_API}/commits/main")
        assert isinstance(meta, dict)
        return str(meta.get("sha") or "") or None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, AssertionError):
        return None


def ensure_fplcache_avail(
    seasons: tuple[str, ...] | None = None,
    *,
    force: bool = False,
) -> dict:
    """Materialize slim GW extracts for the panel (idempotent)."""
    rows = read_coverage_rows()
    wanted = set(seasons) if seasons else None
    SLIM_DIR.mkdir(parents=True, exist_ok=True)
    done = 0
    skipped = 0
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
            print(f"[fplcache_avail] materialized {done} new GW files…", flush=True)

    sha = pin_fplcache_sha()
    manifest = {
        "fplcache_sha": sha,
        "coverage_csv": COVERAGE_CSV.as_posix(),
        "slim_dir": SLIM_DIR.as_posix(),
        "n_existing": sum(1 for _ in SLIM_DIR.glob("*/gw*.json")),
        "newly_written": done,
        "skipped_existing": skipped,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def load_overlay(season: str, gw: int) -> dict[int, AvailFields] | None:
    path = slim_path(season, gw)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[int, AvailFields] = {}
    for k, v in (data.get("by_id") or {}).items():
        eid = int(k)
        out[eid] = AvailFields(
            status=str(v.get("status") or "a"),
            chance_this=_as_int(v.get("chance_this")),
            chance_next=_as_int(v.get("chance_next")),
            can_select=bool(v.get("can_select", True)),
            code=_as_int(v.get("code")),
        )
    return out


def hydrate_players(
    players: list[Player],
    overlay: dict[int, AvailFields] | None,
) -> tuple[list[Player], list[str]]:
    """Return new Player list with availability fields overlaid; identity on miss.

    Also try code join when id miss: map overlay codes → fields, match player if
    we stored code on overlay (Player has no code field — join id only per freeze
    primary key; code fallback requires snapshot-side code which harness lacks).

    Freeze: prefer id; fallback code. Without player.code, id-only + optional
    reverse map if we can match via overlay values keyed by scanning — skip code
    fallback unless we add code to Player later. Document identity on id miss.
    """
    if overlay is None:
        return list(players), ["no_overlay"] * len(players)

    out: list[Player] = []
    reasons: list[str] = []
    for p in players:
        f = overlay.get(p.id)
        if f is None:
            out.append(p)
            reasons.append("join_miss")
            continue
        out.append(
            replace(
                p,
                status=f.status,
                chance_this=f.chance_this,
                chance_next=f.chance_next,
                can_select=f.can_select,
            )
        )
        reasons.append("joined_id")
    return out, reasons
