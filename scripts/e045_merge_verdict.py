"""Merge per-season E045-A summaries and print gate verdict."""
from __future__ import annotations

import csv
import statistics
from pathlib import Path

OUT = Path("records/historical")
FAIL = {"2022-23", "2025-26"}
rows: list[dict] = []
for s in ("2022-23", "2023-24", "2024-25", "2025-26"):
    p = OUT / f"v1_ep_summary_{s}.csv"
    if not p.exists() and s == "2022-23":
        p = OUT / "v1_ep_summary.csv"
    with p.open(encoding="utf-8", newline="") as f:
        rows.extend(csv.DictReader(f))

fields = list(rows[0].keys())
with (OUT / "v1_ep_summary.csv").open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
with (OUT / "v1_ep_summary_2022-23.csv").open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerow(rows[0])


def f(x: str) -> float:
    try:
        return float(x)
    except ValueError:
        return float("nan")


xi0_all = all(r["xi0_ok"] == "True" for r in rows)
mae_all = all(r["mae60_ok"] == "True" for r in rows)
fail_cap = all(r["xicap_ok"] == "True" for r in rows if r["season"] in FAIL)
agg_c = statistics.mean(f(r["ctrl_xicap_mean"]) for r in rows)
agg_t = statistics.mean(f(r["treat_xicap_mean"]) for r in rows)
agg_ok = agg_t + 1e-9 >= agg_c
verdict = "SURVIVES" if (xi0_all and mae_all and fail_cap and agg_ok) else "KILL"

print("=== GATE SUMMARY ===")
for r in rows:
    print(
        f"{r['season']:8} [{r['e024_gate']:4}] "
        f"XI0 {f(r['ctrl_xi0']):.1f}->{f(r['treat_xi0']):.1f} "
        f"MAE {f(r['ctrl_mae60']):.3f}->{f(r['treat_mae60']):.3f} "
        f"Cap {f(r['ctrl_xicap_mean']):.1f}->{f(r['treat_xicap_mean']):.1f} "
        f"g_treat={f(r['g_treat_mean']):.3f} blended={r['n_blended']}"
    )
print(
    f"XI0_all={xi0_all} MAE_all={mae_all} FAIL_Cap={fail_cap} "
    f"AGG {agg_c:.2f}->{agg_t:.2f} ok={agg_ok}"
)
print(f"VERDICT: {verdict}")
with (OUT / "e045_v1_ep_verdict.txt").open("w", encoding="utf-8") as f:
    f.write(f"VERDICT: {verdict}\n")
    f.write(f"XI0_all={xi0_all} MAE_all={mae_all} FAIL_Cap={fail_cap} AGG_ok={agg_ok}\n")
