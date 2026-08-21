"""Refresh the live strategy board on a daily / deadline cadence.

Writes only:
  web/public/data/season/2026-27/strategies.json
  .cache/fpl/strategies_refresh.json   (run stamp)

Does not touch records/, engine/, or the frozen GW1 capture.

Cadence (default --auto, intended for an hourly Task Scheduler tick):
  - Within 12 hours before the next GW deadline: run at most every 45 minutes.
  - Otherwise: run at most once per ~23 hours.

Usage:
  .venv\\Scripts\\python.exe scripts\\refresh_strategies.py           # auto
  .venv\\Scripts\\python.exe scripts\\refresh_strategies.py --force    # always
  .venv\\Scripts\\python.exe scripts\\refresh_strategies.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.api import load_snapshot  # noqa: E402

STAMP = ROOT / ".cache" / "fpl" / "strategies_refresh.json"
DEADLINE_WINDOW = timedelta(hours=12)
DEADLINE_MIN_GAP = timedelta(minutes=45)
DAILY_MIN_GAP = timedelta(hours=23)


def _export(*, refresh: bool) -> int:
    # scripts/ is not a package; load the exporter by path.
    import importlib.util

    path = ROOT / "scripts" / "export_strategies.py"
    spec = importlib.util.spec_from_file_location("export_strategies", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return int(mod.export_strategies(refresh=refresh))


def _parse_deadline(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        # FPL returns e.g. 2026-08-21T17:30:00Z
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_stamp() -> datetime | None:
    if not STAMP.exists():
        return None
    try:
        data = json.loads(STAMP.read_text(encoding="utf-8"))
        return datetime.fromisoformat(data["last_run"])
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        return None


def _write_stamp(now: datetime, *, reason: str, deadline: str | None) -> None:
    STAMP.parent.mkdir(parents=True, exist_ok=True)
    STAMP.write_text(
        json.dumps(
            {
                "last_run": now.isoformat(),
                "reason": reason,
                "next_deadline": deadline,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def decide(now: datetime, deadline: datetime | None, last: datetime | None) -> tuple[bool, str]:
    """Return (should_run, reason)."""
    in_window = (
        deadline is not None
        and now <= deadline
        and (deadline - now) <= DEADLINE_WINDOW
    )
    if in_window:
        gap = DEADLINE_MIN_GAP
        label = "deadline-window"
    else:
        gap = DAILY_MIN_GAP
        label = "daily"

    if last is None:
        return True, f"{label}: never run before"
    age = now - last
    if age >= gap:
        return True, f"{label}: last run {age} ago (gap {gap})"
    return False, f"{label}: skip, last run {age} ago (need {gap})"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cadenced FPL refresh + strategy re-solve for the live UI."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cadence and always refresh + export.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the cadence decision without writing strategies.json.",
    )
    args = parser.parse_args()

    # Need a fresh bootstrap to know the next deadline; cheap relative to three ILPs.
    snapshot = load_snapshot(refresh=True)
    nxt = snapshot.next_event()
    deadline = _parse_deadline(nxt.deadline)
    now = datetime.now(timezone.utc)
    last = _load_stamp()

    if args.force:
        should, reason = True, "forced"
    else:
        should, reason = decide(now, deadline, last)

    print(f"[refresh] now={now.isoformat()}")
    print(f"[refresh] next={nxt.name} deadline={nxt.deadline}")
    print(f"[refresh] decision: {reason}")

    if not should:
        return 0
    if args.dry_run:
        print("[refresh] dry-run: would export strategies")
        return 0

    # Snapshot already refreshed above; export without a second network round-trip.
    code = _export(refresh=False)
    if code == 0:
        _write_stamp(now, reason=reason, deadline=nxt.deadline)
        print(f"[refresh] stamped {STAMP}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
