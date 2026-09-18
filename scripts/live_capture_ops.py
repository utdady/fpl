"""Idempotent live capture ops: freeze before deadline, score after data_checked.

Measurement only — does not retune the model.

Usage
-----
    python scripts/live_capture_ops.py              # freeze + score as needed
    python scripts/live_capture_ops.py --freeze-only
    python scripts/live_capture_ops.py --score-only
    python scripts/live_capture_ops.py --dry-run

Freeze window: next GW with no records/gwNN_v1.0.csv, only if
    now < deadline AND deadline is within FREEZE_WINDOW_HOURS (default 48).
Never invents post-deadline freezes.

Score: any existing freeze with empty scored_at whose event has data_checked.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.capture import freeze, score  # noqa: E402
from engine.live_ops import (  # noqa: E402
    DEFAULT_FREEZE_WINDOW_HOURS,
    should_freeze,
    should_score,
)

API_BASE = "https://fantasy.premierleague.com/api"
USER_AGENT = "fpl-live-capture-ops/0.1"
RECORDS = ROOT / "records"


def _get_bootstrap() -> dict:
    req = urllib.request.Request(
        f"{API_BASE}/bootstrap-static/",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def record_path(gw: int) -> Path:
    return RECORDS / f"gw{gw:02d}_v1.0.csv"


def parse_deadline(iso: str | None) -> datetime | None:
    if not iso:
        return None
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def freeze_already_exists(gw: int) -> bool:
    return record_path(gw).exists()


def freeze_already_scored(gw: int) -> bool:
    path = record_path(gw)
    if not path.exists():
        return False
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return False
    return bool(rows[0].get("scored_at"))


def next_event(events: list[dict]) -> dict | None:
    for e in events:
        if e.get("is_next"):
            return e
    return None


def events_by_id(events: list[dict]) -> dict[int, dict]:
    return {int(e["id"]): e for e in events if e.get("id") is not None}


def run_export() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "export_ui.py")],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-only", action="store_true")
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--window-hours",
        type=float,
        default=DEFAULT_FREEZE_WINDOW_HOURS,
        help="Freeze only if deadline is this many hours away (or less).",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Skip scripts/export_ui.py even when records change.",
    )
    args = parser.parse_args()
    do_freeze = not args.score_only
    do_score = not args.freeze_only

    now = datetime.now(timezone.utc)
    print(f"[live_ops] now={now.isoformat()} window={args.window_hours}h")

    boot = _get_bootstrap()
    events = boot.get("events") or []
    by_id = events_by_id(events)
    changed = False
    os.chdir(ROOT)

    if do_freeze:
        nxt = next_event(events)
        if nxt is None:
            print("[live_ops] freeze: no is_next event")
        else:
            gw = int(nxt["id"])
            deadline = parse_deadline(nxt.get("deadline_time"))
            exists = freeze_already_exists(gw)
            ok = should_freeze(
                now=now,
                deadline=deadline,
                path_exists=exists,
                window_hours=args.window_hours,
            )
            print(
                f"[live_ops] freeze candidate GW{gw} deadline={deadline} "
                f"exists={exists} -> {'YES' if ok else 'skip'}"
            )
            if ok:
                if args.dry_run:
                    print("[live_ops] dry-run: would freeze")
                else:
                    freeze(gw, refresh=True)
                    changed = True

    if do_score:
        for path in sorted(RECORDS.glob("gw*_v1.0.csv")):
            digits = "".join(ch for ch in path.stem.split("_")[0] if ch.isdigit())
            if not digits:
                continue
            gw = int(digits)
            ev = by_id.get(gw)
            data_checked = bool(ev.get("data_checked")) if ev else False
            scored = freeze_already_scored(gw)
            ok = should_score(
                path_exists=True,
                already_scored=scored,
                data_checked=data_checked,
            )
            print(
                f"[live_ops] score GW{gw} data_checked={data_checked} "
                f"scored={scored} -> {'YES' if ok else 'skip'}"
            )
            if ok:
                if args.dry_run:
                    print(f"[live_ops] dry-run: would score GW{gw}")
                else:
                    score(gw)
                    changed = True

    if changed and not args.no_export and not args.dry_run:
        print("[live_ops] exporting UI data ...")
        run_export()
        print("[live_ops] export done")
    elif not changed:
        print("[live_ops] nothing to do")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
