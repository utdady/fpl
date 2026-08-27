"""E018s thin synthesis: pool E016–E018 summaries + E017b entrant profiles.

Diagnostic only. No new rates_version. No threshold retune.
"""
from __future__ import annotations

import csv
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path("records") / "historical"


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gate_map() -> None:
    print("=== GATE SIGNATURE MAP ===")
    specs = [
        ("E016 full", ROOT / "v2b_rates_summary.csv"),
        ("E017 damp", ROOT / "v2b_d_rates_summary.csv"),
        ("E018 elig", ROOT / "v2b_e_rates_summary.csv"),
    ]
    for label, path in specs:
        print(f"\n{label}")
        for r in load(path):
            ok = all(str(r[k]) == "True" for k in ("mae60_ok", "spearman60_ok", "xicap_ok", "xi0_ok"))
            fails = []
            if str(r["xicap_ok"]) != "True":
                fails.append("Cap")
            if str(r["xi0_ok"]) != "True":
                fails.append("XI0")
            tag = "PASS" if ok else ("FAIL " + "+".join(fails))
            swaps = r.get("n_swaps", "n/a")
            eb = r.get("entered_blank_pct", "n/a")
            dmu = r.get("mean_entered_mu_delta", "n/a")
            print(
                f"  {r['season']} MAE {float(r['ctrl_mae60']):.3f}->{float(r['treat_mae60']):.3f} "
                f"Sp {float(r['ctrl_spearman60']):.3f}->{float(r['treat_spearman60']):.3f} "
                f"Cap {float(r['ctrl_xicap_mean']):.1f}->{float(r['treat_xicap_mean']):.1f} "
                f"XI0 {float(r['ctrl_xi0']):.1f}->{float(r['treat_xi0']):.1f} "
                f"swaps={swaps} entered_blank={eb} dmu={dmu} [{tag}]"
            )


def entrant_profile() -> None:
    rows = load(ROOT / "e017_entrant_profile.csv")
    entered = [r for r in rows if r["movement"] == "entered"]
    print("\n=== E017b ENTERED (rates_v1 -> rates_v2b max contrast) ===")
    print(f"n={len(entered)} blank%={100 * sum(int(r['blank']) for r in entered) / len(entered):.1f}")
    print("pos", dict(Counter(r["position"] for r in entered)))

    for gate in ("FAIL", "PASS"):
        sub = [r for r in entered if r["e016_gate"] == gate]
        n = len(sub)
        print(f"\n--- ENTERED {gate} n={n} ---")
        print(f"blank%={100 * sum(int(r['blank']) for r in sub) / n:.1f}")
        print(f"had_prior%={100 * sum(int(r['had_club_prior']) for r in sub) / n:.1f}")
        print(f"new_club%={100 * sum(int(r['new_club']) for r in sub) / n:.1f}")
        print(f"mean_mu_delta={statistics.mean(float(r['mu_delta']) for r in sub):.3f}")
        print(f"mean_recent4={statistics.mean(float(r['recent4_minutes']) for r in sub):.0f}")
        print(f"mean_season_mins={statistics.mean(float(r['season_minutes']) for r in sub):.0f}")
        print("pos", dict(Counter(r["position"] for r in sub)))
        defs = [
            ("prior+cold r4<90", lambda r: int(r["had_club_prior"]) and float(r["recent4_minutes"]) < 90),
            ("prior+warm r4>=90", lambda r: int(r["had_club_prior"]) and float(r["recent4_minutes"]) >= 90),
            ("prior+thin s<450", lambda r: int(r["had_club_prior"]) and float(r["season_minutes"]) < 450),
            ("prior+thick s>=450", lambda r: int(r["had_club_prior"]) and float(r["season_minutes"]) >= 450),
            ("no prior", lambda r: not int(r["had_club_prior"])),
            ("MID", lambda r: r["position"] == "MID"),
            ("FWD", lambda r: r["position"] == "FWD"),
            ("DEF", lambda r: r["position"] == "DEF"),
        ]
        for name, fn in defs:
            ss = [r for r in sub if fn(r)]
            if not ss:
                print(f"  {name}: n=0")
                continue
            bp = 100 * sum(int(r["blank"]) for r in ss) / len(ss)
            print(f"  {name}: n={len(ss)} blank%={bp:.1f}")


def mae_among_played() -> None:
    """Among entered movers who actually played (>=60), was mu_delta still positive?"""
    rows = load(ROOT / "e017_entrant_profile.csv")
    entered = [r for r in rows if r["movement"] == "entered"]
    print("\n=== MU DELTA among entered who played vs blanked ===")
    for gate in ("FAIL", "PASS"):
        sub = [r for r in entered if r["e016_gate"] == gate]
        played = [r for r in sub if float(r["actual_minutes"]) >= 60]
        blanked = [r for r in sub if int(r["blank"])]
        thin = [r for r in sub if 0 < float(r["actual_minutes"]) < 60]
        for label, ss in (("played60+", played), ("blank", blanked), ("1-59min", thin)):
            if not ss:
                print(f"  {gate} {label}: n=0")
                continue
            dmu = statistics.mean(float(r["mu_delta"]) for r in ss)
            print(f"  {gate} {label}: n={len(ss)} mean_mu_delta={dmu:.3f}")


def main() -> None:
    gate_map()
    entrant_profile()
    mae_among_played()
    print("\n=== VERDICT HINT ===")
    print("A = information weak; B = information useful, unsafe under current ILP.")
    print("MAE/Sp improved all seasons all treatments -> leans B.")
    print("Failure relocates with mechanism (full/damp Cap+XI0 toxic; elig XI0 elsewhere) -> leans B.")


if __name__ == "__main__":
    main()
