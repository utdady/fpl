"""Production vs control model settings for export and UI provenance.

Single place so export_ui.py, export_strategies.py, and capture diagnostics
stay aligned with engine.project.project_all defaults.
"""

from __future__ import annotations

# Live CLI / re-solve defaults (engine.project.project_all)
PRODUCTION = {
    "minutes_version": "v2am_s",
    "rates_version": "v1",
    "strategy": "balanced",
    "horizon_resolv": 6,
    "horizon_capture": 1,
}

# Permanent frozen control — records/gw##_v1.0.csv and historical harness v1 arm
V1_CONTROL = {
    "tag": "v1.0-gw1-baseline",
    "minutes_version": "v1",
    "rates_version": "v1",
    "strategy": "balanced",
    "horizon": 1,
    "role": "historical_control",
    "note": (
        "Frozen before deadline. V1 minutes and rates. "
        "Permanent control for backtests; do not overwrite."
    ),
}
