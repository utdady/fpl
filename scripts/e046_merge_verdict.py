"""Merge per-season E046-A summaries and write gate verdict."""
from __future__ import annotations

import csv
from pathlib import Path

OUT = Path("records/historical")
rows: list[dict] = []
for s in ("2022-23", "2023-24", "2024-25", "2025-26"):
    with (OUT / f"e046_free_hit_roi_season_{s}.csv").open(encoding="utf-8", newline="") as f:
        rows.extend(csv.DictReader(f))

fields = list(rows[0].keys())
with (OUT / "e046_free_hit_roi_season.csv").open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

sb = sum(float(r["r_b0"]) for r in rows)
s1 = sum(float(r["r_b1"]) for r in rows)
sc = sum(float(r["r_c"]) for r in rows)
fb = sum(float(r["r_b0"]) for r in rows if r["e024_gate"] == "FAIL")
f1 = sum(float(r["r_b1"]) for r in rows if r["e024_gate"] == "FAIL")
fc = sum(float(r["r_c"]) for r in rows if r["e024_gate"] == "FAIL")
agg = (sc > sb) and (sc > s1)
fail = (fc >= fb) and (fc >= f1)
verdict = "SURVIVES" if agg and fail else "KILL"

lines = [
    "E046-A: Free Hit ROI (sticky HELD_0 / 0 FT; production stack)",
    "B0=never FH (held XI); B1=FH@GW20; C=argmax U_FH (tie=lowest GW)",
    "U_FH = next_xi_utility(blank) - next_xi_utility(held)",
    "Gates: AGG sum4 C>B0 and C>B1; FAIL sum_FAIL C>=B0 and C>=B1",
    "Degeneracy lock: B0 never weekly blank-slate.",
    "",
]
for r in rows:
    lines.append(
        f"  {r['season']} [{r['e024_gate']}] n={r['n_gw']} "
        f"t*={r['t_star']} g*_eff={r['g_star_effective']} | "
        f"R0={float(r['r_b0']):.1f} R1={float(r['r_b1']):.1f} Rc={float(r['r_c']):.1f} | "
        f"C-B0={float(r['delta_c_b0']):.1f} C-B1={float(r['delta_c_b1']):.1f}"
    )
lines += [
    "",
    "=== AGGREGATE (4 seasons) ===",
    f"  sum R(B0)={sb:.1f}  sum R(B1)={s1:.1f}  sum R(C)={sc:.1f}",
    f"  AGG C>B0: {sc > sb}  AGG C>B1: {sc > s1}",
    "",
    "=== FAIL seasons ===",
    f"  sum R(B0)={fb:.1f}  sum R(B1)={f1:.1f}  sum R(C)={fc:.1f}",
    f"  FAIL C>=B0: {fc >= fb}  FAIL C>=B1: {fc >= f1}",
    "",
    "=== PRIMARY GATE ===",
    f"  AGG: {agg}",
    f"  FAIL robustness: {fail}",
    f"  CALL: E046-FH {verdict}",
    "",
]
text = "\n".join(lines)
print(text)
(OUT / "e046_free_hit_roi_summary.txt").write_text(text, encoding="utf-8")
(OUT / "e046_fh_verdict.txt").write_text(
    f"VERDICT: {verdict}\nAGG={agg} FAIL={fail}\n"
    f"sumC={sc} sumB0={sb} sumB1={s1}\n",
    encoding="utf-8",
)
