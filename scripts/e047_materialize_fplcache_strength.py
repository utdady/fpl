"""Materialize E047-A fplcache team strength slim extracts.

Usage:
    python scripts/e047_materialize_fplcache_strength.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.fplcache_strength import ensure_fplcache_strength
from engine.harness import SUPPORTED_SEASONS


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--season", choices=SUPPORTED_SEASONS, action="append")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    seasons = tuple(args.season) if args.season else None
    print("[e047] materializing fplcache_strength slim extracts…", flush=True)
    print(ensure_fplcache_strength(seasons, force=args.force))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
