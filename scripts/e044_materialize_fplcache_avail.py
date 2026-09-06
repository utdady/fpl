"""Materialize E044-A fplcache slim availability extracts.

Usage:
    python scripts/e044_materialize_fplcache_avail.py
    python scripts/e044_materialize_fplcache_avail.py --season 2022-23
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.fplcache_avail import ensure_fplcache_avail
from engine.harness import SUPPORTED_SEASONS


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--season", choices=SUPPORTED_SEASONS, action="append")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    seasons = tuple(args.season) if args.season else None
    print("[e044] materializing fplcache_avail slim extracts…", flush=True)
    man = ensure_fplcache_avail(seasons, force=args.force)
    print(man)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
