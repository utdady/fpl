import csv
import statistics
from pathlib import Path
from engine.harness import gw_actuals

SEASONS = [
    ("2022-23", "2022/23"),
    ("2023-24", "2023/24"),
    ("2024-25", "2024/25"),
    ("2025-26", "2025/26"),
]

def load_csv(path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))

for season, label in SEASONS:
    base = Path("records/historical") / season
    flagged = sum(1 for r in load_csv(base / "b0_leakage.csv") if r.get("leakage_flag") == "1")
    tail = next(r for r in load_csv(base / "minutes_cal.csv") if r["split"] == "all" and r["bucket"] == "0.90-1.00")
    fit = next(r for r in load_csv(base / "minutes_cal_fit.csv") if r["split"] == "all")
    cmp_rows = load_csv(base / "b0_b3_comparison.csv")
    def mean_xi(model):
        vals = [float(r["xi_points"]) for r in cmp_rows if r["model"] == model and r.get("xi_points")]
        return statistics.mean(vals)
    v1, b1, b2 = mean_xi("B3_v1"), mean_xi("B1_season_pts"), mean_xi("B2_pp90")
    clean = [r for r in load_csv(base / "decision_gw.csv") if r.get("evaluation_status") == "clean"]
    delta = statistics.mean(float(r["v1_gw1_xi_cap"]) - float(r["v1_xi_cap"]) for r in clean)
    xi_slots = [r for r in load_csv(base / "decision_decomp.csv") if r.get("in_v1_xi") == "1"]
    z = 0
    for r in xi_slots:
        gw, pid = int(r["gw"]), int(r["player_id"])
        mins = float(gw_actuals(season, gw).get(pid, {}).get("actual_minutes", 0) or 0)
        z += int(mins == 0)
    xi_pct = 100 * z / len(xi_slots)
    print(f"| {label} | {flagged}/38 | {tail['n']} | {tail['start_pct']} | {xi_pct:.1f} | {delta:+.2f} | {v1:.1f} | {b1:.1f} | {b2:.1f} | yes | yes | {fit['alpha']}/{fit['beta']} | {fit['p90_fitted']} |")
