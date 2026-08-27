"""E021c diagnostic: cold vs warm prior_str entrants by actual minutes.

Reads records/historical/e021_fixture_movers.csv (no re-projection).

Cells (entered only, had_prior_strength=1):
  COLD: recent4 < 90
  WARM: recent4 >= 90

Buckets: 0 / 1-59 / 60+ (n + share). Among 60+: treat_mu, mu_delta,
actual_points, treat_mu - actual.

Usage:
    python scripts/e021c_cold_minutes_breakdown.py
"""
from __future__ import annotations

import csv
import statistics
from pathlib import Path

IN = Path("records") / "historical" / "e021_fixture_movers.csv"
OUT_TXT = Path("records") / "historical" / "e021c_cold_minutes_breakdown.txt"
OUT_CSV = Path("records") / "historical" / "e021c_cold_minutes_breakdown.csv"


def mean(xs: list[float]) -> float:
    return statistics.mean(xs) if xs else float("nan")


def bucket(mins: float) -> str:
    if mins <= 0:
        return "0"
    if mins < 60:
        return "1-59"
    return "60+"


def load_entered() -> list[dict]:
    rows: list[dict] = []
    with IN.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["movement"] != "entered":
                continue
            if int(r["had_prior_strength"]) != 1:
                continue
            rows.append({
                "season": r["season"],
                "gw": int(r["gw"]),
                "player_id": r["player_id"],
                "web_name": r["web_name"],
                "position": r["position"],
                "recent4_minutes": int(float(r["recent4_minutes"])),
                "treat_mu": float(r["treat_mu"]),
                "ctrl_mu": float(r["ctrl_mu"]),
                "mu_delta": float(r["mu_delta"]),
                "actual_minutes": float(r["actual_minutes"]),
                "actual_points": float(r["actual_points"] or 0),
                "cell": "COLD" if float(r["recent4_minutes"]) < 90 else "WARM",
                "bucket": bucket(float(r["actual_minutes"])),
            })
    return rows


def summarize_cell(label: str, subset: list[dict], lines: list[str], csv_rows: list[dict]) -> None:
    n = len(subset)
    lines.append(f"\n=== {label}: prior_str & recent4 {'< 90' if label == 'COLD' else '>= 90'} ===")
    lines.append(f"n={n}")
    if not n:
        return

    lines.append(f"{'bucket':8} {'n':>5} {'share%':>8}")
    for b in ("0", "1-59", "60+"):
        g = [r for r in subset if r["bucket"] == b]
        share = 100.0 * len(g) / n
        lines.append(f"{b:8} {len(g):5} {share:8.1f}")
        csv_rows.append({
            "cell": label,
            "section": "bucket_share",
            "bucket": b,
            "n": len(g),
            "share_pct": round(share, 2),
            "mean_treat_mu": "",
            "mean_mu_delta": "",
            "mean_actual_pts": "",
            "mean_treat_mu_minus_actual": "",
        })

    played = [r for r in subset if r["bucket"] == "60+"]
    lines.append("\nAmong 60+:")
    if not played:
        lines.append("  (none)")
        return
    tmu = mean([r["treat_mu"] for r in played])
    dmu = mean([r["mu_delta"] for r in played])
    pts = mean([r["actual_points"] for r in played])
    gap = mean([r["treat_mu"] - r["actual_points"] for r in played])
    lines.append(f"  n={len(played)}")
    lines.append(f"  mean treat_mu              = {tmu:.3f}")
    lines.append(f"  mean mu_delta              = {dmu:.3f}")
    lines.append(f"  mean actual_points         = {pts:.3f}")
    lines.append(f"  mean treat_mu - actual_pts = {gap:.3f}")
    csv_rows.append({
        "cell": label,
        "section": "among_60plus",
        "bucket": "60+",
        "n": len(played),
        "share_pct": round(100.0 * len(played) / n, 2),
        "mean_treat_mu": round(tmu, 4),
        "mean_mu_delta": round(dmu, 4),
        "mean_actual_pts": round(pts, 4),
        "mean_treat_mu_minus_actual": round(gap, 4),
    })

    # Also report 0 and 1-59 mean mu_delta for context
    lines.append("\nMean mu_delta by bucket:")
    for b in ("0", "1-59", "60+"):
        g = [r for r in subset if r["bucket"] == b]
        if not g:
            lines.append(f"  {b:8} n=0")
            continue
        lines.append(
            f"  {b:8} n={len(g):3} mean_mu_delta={mean([r['mu_delta'] for r in g]):.3f} "
            f"mean_treat_mu={mean([r['treat_mu'] for r in g]):.3f} "
            f"mean_actual_pts={mean([r['actual_points'] for r in g]):.3f}"
        )


def main() -> None:
    if not IN.exists():
        raise SystemExit(f"Missing {IN}; run scripts/e021_fixture_movers.py first.")

    rows = load_entered()
    cold = [r for r in rows if r["cell"] == "COLD"]
    warm = [r for r in rows if r["cell"] == "WARM"]

    lines = [
        "E021c: cold vs warm prior_str entrants by actual minutes",
        f"Source: {IN}",
        "Entered only; had_prior_strength=1.",
        "No re-projection; no model changes.",
        f"Total prior_str entered: {len(rows)} (COLD={len(cold)}, WARM={len(warm)})",
    ]
    csv_rows: list[dict] = []
    summarize_cell("COLD", cold, lines, csv_rows)
    summarize_cell("WARM", warm, lines, csv_rows)

    # Fork hint
    lines.append("\n=== interpretation hint ===")
    if cold:
        z = sum(1 for r in cold if r["bucket"] == "0")
        p60 = sum(1 for r in cold if r["bucket"] == "60+")
        lines.append(
            f"COLD share 0-min={100.0 * z / len(cold):.1f}% | "
            f"60+={100.0 * p60 / len(cold):.1f}%"
        )
        if z / len(cold) >= 0.5:
            lines.append("-> Mostly non-playing: packaging primarily minutes-reliability of increments.")
        elif p60 / len(cold) >= 0.25:
            lines.append("-> Material 60+ share: check wrong-player / projection gap among cold 60+.")
        else:
            lines.append("-> Mixed: compare cold vs warm 60+ treat_mu-actual before choosing packaging shape.")

    text = "\n".join(lines) + "\n"
    OUT_TXT.parent.mkdir(parents=True, exist_ok=True)
    OUT_TXT.write_text(text, encoding="utf-8")
    print(text)

    fields = [
        "cell", "section", "bucket", "n", "share_pct",
        "mean_treat_mu", "mean_mu_delta", "mean_actual_pts", "mean_treat_mu_minus_actual",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(csv_rows)
    print(f"Wrote {OUT_TXT}")
    print(f"Wrote {OUT_CSV}")


if __name__ == "__main__":
    main()
