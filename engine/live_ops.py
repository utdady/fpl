"""Live capture decision helpers (freeze window / score gate). No I/O."""
from __future__ import annotations

from datetime import datetime

DEFAULT_FREEZE_WINDOW_HOURS = 48


def should_freeze(
    *,
    now: datetime,
    deadline: datetime | None,
    path_exists: bool,
    window_hours: float = DEFAULT_FREEZE_WINDOW_HOURS,
) -> bool:
    """Pre-deadline only; only inside the approaching window; never overwrite."""
    if path_exists or deadline is None:
        return False
    if now >= deadline:
        return False
    hours_left = (deadline - now).total_seconds() / 3600.0
    return 0 < hours_left <= window_hours


def should_score(
    *,
    path_exists: bool,
    already_scored: bool,
    data_checked: bool,
) -> bool:
    return path_exists and not already_scored and data_checked
