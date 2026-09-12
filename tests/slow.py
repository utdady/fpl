"""Markers for intentionally expensive integration tests.

Default `python -m unittest discover` / ordinary module runs stay fast.

Opt in to historical full-season recomputes:

    set FPL_RUN_SLOW=1          # Windows cmd
    $env:FPL_RUN_SLOW=1         # PowerShell
    FPL_RUN_SLOW=1 python -m unittest ...
"""
from __future__ import annotations

import os
import unittest

_TRUTHY = {"1", "true", "yes", "on"}


def slow_enabled() -> bool:
    return os.environ.get("FPL_RUN_SLOW", "").strip().lower() in _TRUTHY


def skip_unless_slow(
    reason: str = "slow historical recompute; set FPL_RUN_SLOW=1 to run",
):
    """Decorator: skip unless FPL_RUN_SLOW is truthy."""
    return unittest.skipUnless(slow_enabled(), reason)
