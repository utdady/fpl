"""Materialize E045-A fplcache ep_next slim extracts.

Usage:
    python scripts/e045_materialize_fplcache_ep.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.fplcache_ep import ensure_fplcache_ep
from engine.harness import SUPPORTED_SEASONS


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--season", choices=SUPPORTED_SEASONS, action="append")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    seasons = tuple(args.season) if args.season else None
    print("[e045] materializing fplcache_ep slim extracts…", flush=True)
    print(ensure_fplcache_ep(seasons, force=args.force))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
