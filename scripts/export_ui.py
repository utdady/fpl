"""Export frozen research artifacts and the cached FPL snapshot to JSON for web/.

Read-only with respect to records/ and .cache/. Run after the engine produces
new records:

    python scripts/export_ui.py

Output goes to web/public/data/ and is committed as a versioned artifact so
Vercel builds need only Node.
"""

from __future__ import annotations

import csv
import json
import math
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.model_config import PRODUCTION, V1_CONTROL

RECORDS = ROOT / "records"
HISTORICAL = RECORDS / "historical"
CACHE = ROOT / ".cache" / "fpl"
VAASTAV = ROOT / "data" / "vaastav" / "data"
OUT = ROOT / "web" / "public" / "data"

LIVE_SEASON = "2026-27"

POSITION_BY_TYPE = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

DIAGNOSTIC_FLAGS = (
    "horizon",
    "minutes",
    "fixture",
    "price_value",
    "captain",
    "projection_rank",
)

# Sourced from docs/LAB_LOG.md and docs/FORMAL.md. These travel with the data so
# a chart cannot reach the UI without its caveat.
CAVEATS = {
    "b0": (
        "Vaastav xP (B0) is flagged for possible post-deadline information on "
        "10/38 (2025/26) to 34/38 (2024/25) gameweeks. E008 pre-registered the "
        "flag at Spearman(xP, actual) > 0.70. B0 is an upper-bound diagnostic, "
        "never a baseline or a ceiling."
    ),
    "regret": (
        "Nested hindsight regret is measured against a god-mode oracle, not "
        "against B0. R_total = R_squad + R_XI + R_cap = P(oracle) - P(V1 "
        "realized). Do not read the squad share as 'the optimizer is the B0 "
        "problem'."
    ),
    "p_start": (
        "Model p_start >= 0.90 corresponds to a 75-78% actual start rate across "
        "all four seasons (E013 p90_fitted). The upper tail is overconfident."
    ),
    "new_club": (
        "New-club vs established splits are confounded by differing selection "
        "into the high p_start bucket. Cite with n only; alpha/beta fits flip "
        "sign across seasons and are diagnostic appendix only."
    ),
    "horizon": (
        "Player-level record files are horizon-1 projections. The decision "
        "decomposition used horizon 6. V1_GW1 is the same mu solved with a "
        "next-GW objective; its sign is inconsistent across seasons (H2 weak)."
    ),
    "xi_only": (
        "decision_decomp.csv holds the union of the V1 and B0 elevens, not the "
        "15-man squad. Bench and squad membership are not persisted yet."
    ),
    "live_pool": (
        "The live season record is a prediction pool only. capture.py does not "
        "persist squad selection, so no XI is available for this season."
    ),
    "diagnostics": (
        "Quantiles and mu_components come from 2500 Monte Carlo draws per player "
        "per gameweek. They are not a fitted Normal. P(0) is P(total <= 0), "
        "distinct from 1 - p_start."
    ),
    "audit_loo": (
        "Leave-one-out delta uses bench-weighted horizon utility with the next-GW "
        "XI as starters. Re-solved from the cached snapshot, not the frozen GW1 CSV."
    ),
    "did_start": (
        "did_start is a proxy: capture.py sets it from minutes >= 45, because "
        "the FPL API does not expose whether a player started."
    ),
}


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def write_json(rel: str, payload) -> int:
    dest = OUT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"), allow_nan=False)
    return dest.stat().st_size


def num(value, digits: int | None = None):
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    # 2022/23 GW7 has no Vaastav actuals, so its metrics are nan (E013).
    if not math.isfinite(out):
        return None
    if digits == 0:
        return int(out)
    return round(out, digits) if digits is not None else out


def flag(value) -> int:
    return 1 if str(value).strip() == "1" else 0


def mean(values) -> float | None:
    clean = [v for v in values if v is not None]
    return round(sum(clean) / len(clean), 4) if clean else None


def git_info() -> dict:
    def run(*args: str) -> str | None:
        try:
            done = subprocess.run(
                args, cwd=ROOT, capture_output=True, text=True, timeout=10, check=True
            )
            return done.stdout.strip() or None
        except (subprocess.SubprocessError, OSError):
            return None

    return {
        "sha": run("git", "rev-parse", "--short", "HEAD"),
        "tag": run("git", "describe", "--tags", "--abbrev=0"),
    }


def snapshot_as_of() -> str | None:
    path = CACHE / "meta.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh).get("as_of")


def gw_files(season_dir: Path) -> list[tuple[int, Path]]:
    found = []
    for path in sorted(season_dir.glob("gw*_v1.0.csv")):
        digits = "".join(ch for ch in path.stem.split("_")[0] if ch.isdigit())
        if digits:
            found.append((int(digits), path))
    return sorted(found)


def actual_minutes_index(season_dir: Path) -> dict[tuple[int, str], int]:
    """Minutes per player-GW, summed across duplicate DGW rows as E007 does.

    A key present with an empty actual_minutes resolves to 0: the player was in
    the frozen pool but scoring found no appearance.
    """
    index: dict[tuple[int, str], int] = {}
    for gw, path in gw_files(season_dir):
        for row in read_csv(path):
            key = (gw, row["player_id"])
            index[key] = index.get(key, 0) + (num(row.get("actual_minutes"), 0) or 0)
    return index


# --------------------------------------------------------------------------
# Tier B: cached FPL snapshot
# --------------------------------------------------------------------------


def export_live_metadata() -> dict:
    boot_path = CACHE / "bootstrap.json"
    fixtures_path = CACHE / "fixtures.json"
    if not boot_path.exists():
        return {"teams": 0, "players": 0, "fixtures": 0}

    with boot_path.open(encoding="utf-8") as fh:
        boot = json.load(fh)
    fixtures = []
    if fixtures_path.exists():
        with fixtures_path.open(encoding="utf-8") as fh:
            fixtures = json.load(fh)

    teams = [
        {
            "id": t["id"],
            "code": t["short_name"],
            "name": t["name"],
            "strength_home": t.get("strength_overall_home"),
            "strength_away": t.get("strength_overall_away"),
        }
        for t in boot.get("teams", [])
    ]
    write_json("teams.json", {"season": LIVE_SEASON, "teams": teams})

    players = {}
    for el in boot.get("elements", []):
        players[str(el["id"])] = {
            "code": el["code"],
            "name": el["web_name"],
            "full": f"{el.get('first_name', '')} {el.get('second_name', '')}".strip(),
            "team": el["team"],
            "pos": POSITION_BY_TYPE.get(el["element_type"]),
            "cost": el["now_cost"],
            "owned": num(el.get("selected_by_percent"), 1),
            "status": el.get("status"),
            "news": el.get("news") or None,
            # Third opinion beside V1 p_start and historical calibration.
            "chance_next": el.get("chance_of_playing_next_round"),
            "ep_next": num(el.get("ep_next"), 2),
            "photo": el.get("photo"),
            "form": num(el.get("form"), 2),
            "ppg": num(el.get("points_per_game"), 2),
        }
    write_json(
        "players.json",
        {
            "season": LIVE_SEASON,
            "as_of": snapshot_as_of(),
            "note": (
                "ep_next is published pre-deadline and is not the flagged "
                "historical Vaastav xP."
            ),
            "players": players,
        },
    )

    trimmed = [
        {
            "id": f["id"],
            "gw": f.get("event"),
            "h": f["team_h"],
            "a": f["team_a"],
            "hd": f.get("team_h_difficulty"),
            "ad": f.get("team_a_difficulty"),
            "kickoff": f.get("kickoff_time"),
            "finished": bool(f.get("finished")),
        }
        for f in fixtures
    ]
    write_json("fixtures.json", {"season": LIVE_SEASON, "fixtures": trimmed})
    return {"teams": len(teams), "players": len(players), "fixtures": len(trimmed)}


def historical_team_map(season: str) -> dict[str, str]:
    """Team id to FPL short code, matching the live season's teams.json.

    Read from the per-season teams.csv, not master_team_list.csv: the master list
    stops at 2023-24, and the display names it does carry cannot be abbreviated
    safely because "Man City" and "Man Utd" collapse to the same three letters.
    """
    rows = read_csv(VAASTAV / season / "teams.csv")
    return {r["id"]: r["short_name"] for r in rows}


# --------------------------------------------------------------------------
# Tier A: frozen research artifacts
# --------------------------------------------------------------------------


def merge_gw_diagnostics(season_dir: Path, players: dict, gws: list[int]) -> int:
    """Attach p0, quantiles, mu_components from gw##_diagnostics.json when present."""
    merged = 0
    extra_keys = ("p0", "q05", "q25", "q50", "q75", "q95")
    comp_keys = (
        "appearance",
        "goals",
        "assists",
        "clean_sheet",
        "defensive",
        "saves",
        "goals_conceded",
        "yellow",
        "bonus",
    )
    for gw, _path in gw_files(season_dir):
        diag_path = season_dir / f"gw{gw:02d}_diagnostics.json"
        if not diag_path.exists():
            continue
        with diag_path.open(encoding="utf-8") as fh:
            diag = json.load(fh)
        for pid, info in diag.get("players", {}).items():
            entry = players.get(pid)
            if entry is None:
                continue
            if "p0" not in entry:
                for k in extra_keys:
                    entry[k] = []
                for k in comp_keys:
                    entry[f"mu_{k}"] = []
            idx = entry["gw"].index(gw) if gw in entry["gw"] else None
            if idx is None:
                continue
            # Pad arrays if shorter than gw list (shouldn't happen)
            for k in extra_keys:
                while len(entry[k]) <= idx:
                    entry[k].append(None)
            qu = info.get("quantiles") or [None] * 5
            entry["p0"][idx] = num(info.get("p_0"), 4)
            for j, qk in enumerate(("q05", "q25", "q50", "q75", "q95")):
                entry[qk][idx] = num(qu[j] if j < len(qu) else None, 3)
            comps = info.get("mu_components") or {}
            for ck in comp_keys:
                if f"mu_{ck}" not in entry:
                    entry[f"mu_{ck}"] = []
                while len(entry[f"mu_{ck}"]) <= idx:
                    entry[f"mu_{ck}"].append(None)
                entry[f"mu_{ck}"][idx] = num(comps.get(ck), 3)
            merged += 1
    return merged


def export_diagnostics_gw(season: str, season_dir: Path, gw: int) -> dict | None:
    path = season_dir / f"gw{gw:02d}_diagnostics.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    write_json(
        f"season/{season}/gw/{gw:02d}/diagnostics.json",
        {
            "season": season,
            "gw": gw,
            "caveats": [CAVEATS["diagnostics"]],
            **payload,
        },
    )
    return {"players": len(payload.get("players", {})), "strategies": len(payload.get("squads", {}))}


def export_audit(season: str, season_dir: Path) -> dict:
    loo = read_csv(season_dir / "audit_loo.csv")
    cf = read_csv(season_dir / "audit_counterfactual.csv")
    write_json(
        f"season/{season}/audit.json",
        {
            "season": season,
            "caveats": [CAVEATS["audit_loo"], CAVEATS["diagnostics"]],
            "model_config": {**PRODUCTION, "role": "live_resolv", "horizon": PRODUCTION["horizon_resolv"]},
            "baseline_u_note": "Delta = U* - U without player (LOO). Counterfactual lock/exclude vs baseline.",
            "loo": [
                {
                    "id": num(r["player_id"], 0),
                    "name": r["web_name"],
                    "pos": r["position"],
                    "cost": num(r["cost"], 0),
                    "next_mu": num(r["next_mu"], 4),
                    "horizon_u": num(r["horizon_u"], 4),
                    "p_start": num(r["p_start"], 4),
                    "delta": num(r["delta"], 4),
                    "tag": r["tag"],
                    "incoming": r.get("incoming") or "",
                    "strategy": r.get("strategy"),
                }
                for r in loo
            ],
            "counterfactuals": [
                {
                    "id": num(r["player_id"], 0),
                    "name": r["web_name"],
                    "action": r["action"],
                    "delta": num(r["delta"], 4),
                    "baseline_u": num(r["baseline_u"], 4),
                    "alt_u": num(r["alt_u"], 4),
                }
                for r in cf
            ],
            "as_of": loo[0].get("as_of") if loo else None,
        },
    )
    return {"loo": len(loo), "counterfactuals": len(cf)}


def export_predictions(season: str, season_dir: Path) -> dict:
    """Columnar per-player series. One file serves the pool and the drawer."""
    players: dict[str, dict] = {}
    gws: list[int] = []
    rows_seen = 0

    series_keys = (
        "gw",
        "cost",
        "mu",
        "sigma",
        "p_start",
        "p_sub",
        "p_60",
        "p10",
        "nfix",
        "pts",
        "min",
        "start",
    )

    for gw, path in gw_files(season_dir):
        rows = read_csv(path)
        if not rows:
            continue
        gws.append(gw)
        rows_seen += len(rows)
        for row in rows:
            pid = row["player_id"]
            entry = players.get(pid)
            if entry is None:
                entry = players[pid] = {
                    "name": row["web_name"],
                    "team": num(row["team_id"], 0),
                    "pos": row["position"],
                    **{key: [] for key in series_keys},
                }
            entry["gw"].append(gw)
            entry["cost"].append(num(row["now_cost"], 0))
            entry["mu"].append(num(row["mu"], 3))
            entry["sigma"].append(num(row["sigma"], 3))
            entry["p_start"].append(num(row["p_start"], 3))
            entry["p_sub"].append(num(row["p_sub"], 3))
            entry["p_60"].append(num(row["p_60"], 3))
            entry["p10"].append(num(row["p_10_plus"], 4))
            entry["nfix"].append(num(row["n_fixtures"], 0))
            entry["pts"].append(num(row.get("actual_points"), 0))
            entry["min"].append(num(row.get("actual_minutes"), 0))
            entry["start"].append(num(row.get("did_start"), 0))

    diag_merged = merge_gw_diagnostics(season_dir, players, gws)
    caveats = [CAVEATS["horizon"], CAVEATS["p_start"], CAVEATS["did_start"]]
    if diag_merged:
        caveats.append(CAVEATS["diagnostics"])

    size = write_json(
        f"season/{season}/predictions.json",
        {
            "season": season,
            "gws": gws,
            "caveats": caveats,
            "has_diagnostics": diag_merged > 0,
            "model_config": (
                {**V1_CONTROL, "role": "frozen_record"}
                if season == LIVE_SEASON
                else {**V1_CONTROL, "role": "historical_control"}
            ),
            "players": players,
        },
    )
    for gw in gws:
        export_diagnostics_gw(season, season_dir, gw)
    return {
        "gws": len(gws),
        "players": len(players),
        "rows": rows_seen,
        "bytes": size,
        "diagnostics": diag_merged,
    }


def export_xi(season: str, season_dir: Path) -> dict:
    """V1 and B0 elevens per GW, with actual minutes joined from the record files."""
    decomp = read_csv(season_dir / "decision_decomp.csv")
    if not decomp:
        return {"gws": 0}

    minutes = actual_minutes_index(season_dir)
    by_gw: dict[int, list[dict]] = defaultdict(list)

    for row in decomp:
        gw = int(row["gw"])
        by_gw[gw].append(
            {
                "id": num(row["player_id"], 0),
                "name": row["web_name"],
                "pos": row["position"],
                "cost": num(row["now_cost"], 0),
                "v1_xi": flag(row["in_v1_xi"]),
                "b0_xi": flag(row["in_b0_xi"]),
                "v1_cap": flag(row["is_v1_captain"]),
                "b0_cap": flag(row["is_b0_captain"]),
                "pts": num(row.get("actual_points"), 0),
                "mins": minutes.get((gw, row["player_id"])),
                "v1_mu": num(row.get("v1_mu"), 3),
                "b0_mu": num(row.get("b0_mu"), 3),
                "v1_u": num(row.get("v1_horizon_u"), 3),
                "v1_p_start": num(row.get("v1_p_start"), 3),
                "flags": {
                    key: flag(row.get(f"{key}_flag")) for key in DIAGNOSTIC_FLAGS
                },
            }
        )

    write_json(
        f"season/{season}/xi.json",
        {
            "season": season,
            "caveats": [CAVEATS["xi_only"], CAVEATS["p_start"], CAVEATS["b0"]],
            "gws": {str(gw): rows for gw, rows in sorted(by_gw.items())},
        },
    )
    return {"gws": len(by_gw)}


def export_decisions(season: str, season_dir: Path) -> dict:
    rows = read_csv(season_dir / "decision_gw.csv")
    gws = [
        {
            "gw": num(r["gw"], 0),
            "status": r["evaluation_status"],
            "flags": [f for f in (r.get("structural_flags") or "").split(";") if f],
            "n_fixtures": num(r.get("n_fixtures"), 0),
            "b0": num(r.get("b0_xi_cap"), 1),
            "v1": num(r.get("v1_xi_cap"), 1),
            "v1_gw1": num(r.get("v1_gw1_xi_cap"), 1),
            "oracle": num(r.get("hindsight_oracle_cap"), 1),
            "squad_overlap": num(r.get("squad_overlap"), 0),
            "xi_overlap": num(r.get("xi_overlap"), 0),
            "r_squad": num(r.get("hindsight_squad_regret"), 1),
            "r_xi": num(r.get("hindsight_xi_regret"), 1),
            "r_cap": num(r.get("hindsight_cap_regret"), 1),
            "vs_b0": num(r.get("vs_b0_gap"), 1),
        }
        for r in rows
    ]
    write_json(
        f"season/{season}/decisions.json",
        {
            "season": season,
            "oracle": "god-mode nested hindsight over the same actuals",
            "caveats": [CAVEATS["regret"], CAVEATS["b0"], CAVEATS["horizon"]],
            "gws": gws,
        },
    )
    return {"gws": len(gws)}


def export_scores(season: str, season_dir: Path) -> dict:
    rows = read_csv(season_dir / "scores.csv")
    write_json(
        f"season/{season}/scores.json",
        {
            "season": season,
            "note": (
                "Per-GW player-level error. ECE is not persisted per GW; "
                "calibration lives in minutes.json."
            ),
            "gws": [
                {
                    "gw": num(r["gw"], 0),
                    "n": num(r["n"], 0),
                    "mae": num(r["mae"], 4),
                    "rmse": num(r["rmse"], 4),
                    "bias": num(r["bias"], 4),
                    "spearman": num(r["spearman"], 4),
                }
                for r in rows
            ],
        },
    )
    return {"gws": len(rows)}


def export_leakage(season: str, season_dir: Path) -> dict:
    rows = read_csv(season_dir / "b0_leakage.csv")
    flagged = sum(1 for r in rows if flag(r.get("leakage_flag")))
    write_json(
        f"season/{season}/leakage.json",
        {
            "season": season,
            "threshold": 0.70,
            "threshold_note": "Pre-registered in E008 before the query was run.",
            "flagged": flagged,
            "total": len(rows),
            "caveats": [CAVEATS["b0"]],
            "gws": [
                {
                    "gw": num(r["gw"], 0),
                    "n": num(r["n"], 0),
                    "spearman": num(r["spearman"], 4),
                    "mae": num(r["mae"], 4),
                    "bias": num(r["bias"], 4),
                    "flag": flag(r.get("leakage_flag")),
                }
                for r in rows
            ],
        },
    )
    return {"flagged": flagged, "total": len(rows)}


def export_compare(season: str, season_dir: Path) -> dict:
    rows = read_csv(season_dir / "b0_b3_comparison.csv")
    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(
            {
                "gw": num(r["gw"], 0),
                "n": num(r["n"], 0),
                "mae": num(r["mae"], 4),
                "rmse": num(r["rmse"], 4),
                "bias": num(r["bias"], 4),
                "spearman": num(r["spearman"], 4),
                "xi": num(r["xi_points"], 1),
                "cap": num(r["captain_points"], 1),
            }
        )
    summary = {
        model: {
            "mae": mean([g["mae"] for g in games]),
            "spearman": mean([g["spearman"] for g in games]),
            "xi": mean([g["xi"] for g in games]),
        }
        for model, games in by_model.items()
    }
    write_json(
        f"season/{season}/compare.json",
        {
            "season": season,
            "note": "xi_points already includes the captain double-count.",
            "caveats": [CAVEATS["b0"]],
            "summary": summary,
            "models": {model: games for model, games in sorted(by_model.items())},
        },
    )
    return {"models": len(by_model)}


def export_minutes(season: str, season_dir: Path) -> dict:
    buckets = read_csv(season_dir / "minutes_cal.csv")
    fits = read_csv(season_dir / "minutes_cal_fit.csv")
    write_json(
        f"season/{season}/minutes.json",
        {
            "season": season,
            "caveats": [CAVEATS["p_start"], CAVEATS["new_club"], CAVEATS["did_start"]],
            "buckets": [
                {
                    "split": r["split"],
                    "bucket": r["bucket"],
                    "n": num(r["n"], 0),
                    "start_pct": num(r["start_pct"], 2),
                    "zero_min_pct": num(r["zero_min_pct"], 2),
                    "avg_pts": num(r["avg_pts"], 3),
                }
                for r in buckets
            ],
            "fits": [
                {
                    "split": r["split"],
                    "min_p": num(r["min_p"], 2),
                    "n": num(r["n"], 0),
                    "alpha": num(r["alpha"], 4),
                    "beta": num(r["beta"], 4),
                    "p90_fitted": num(r["p90_fitted"], 2),
                    "diagnostic_only": True,
                }
                for r in fits
            ],
        },
    )
    return {"buckets": len(buckets), "fits": len(fits)}


def xi_zero_min(season_dir: Path) -> dict:
    """Share of V1 XI slots whose player recorded zero minutes.

    Every XI slot counts toward the denominator, matching E009's 69/418. A slot
    with no minutes recorded is a blank, not a missing observation.
    """
    decomp = read_csv(season_dir / "decision_decomp.csv")
    if not decomp:
        return {}
    minutes = actual_minutes_index(season_dir)
    totals = {"all": [0, 0], "clean": [0, 0]}
    for row in decomp:
        if not flag(row["in_v1_xi"]):
            continue
        zero = 0 if minutes.get((int(row["gw"]), row["player_id"])) else 1
        totals["all"][0] += zero
        totals["all"][1] += 1
        if row.get("evaluation_status") == "clean":
            totals["clean"][0] += zero
            totals["clean"][1] += 1
    return {
        name: {
            "zero": zero,
            "slots": slots,
            "pct": round(100 * zero / slots, 1) if slots else None,
        }
        for name, (zero, slots) in totals.items()
    }


def build_panel(seasons: list[str]) -> dict:
    """Reproduce the E013 four-season synthesis from artifacts."""
    rows = []
    for season in seasons:
        season_dir = HISTORICAL / season
        leak = read_csv(season_dir / "b0_leakage.csv")
        buckets = read_csv(season_dir / "minutes_cal.csv")
        fits = read_csv(season_dir / "minutes_cal_fit.csv")
        decisions = read_csv(season_dir / "decision_gw.csv")
        compare = read_csv(season_dir / "b0_b3_comparison.csv")

        tail = next(
            (b for b in buckets if b["split"] == "all" and b["bucket"] == "0.90-1.00"),
            None,
        )
        fit = next((f for f in fits if f["split"] == "all"), None)

        clean_delta = []
        for d in decisions:
            if d.get("evaluation_status") != "clean":
                continue
            gw1 = num(d.get("v1_gw1_xi_cap"))
            base = num(d.get("v1_xi_cap"))
            if gw1 is not None and base is not None:
                clean_delta.append(gw1 - base)

        xi_by_model: dict[str, list[float]] = defaultdict(list)
        for c in compare:
            value = num(c.get("xi_points"))
            if value is not None:
                xi_by_model[c["model"]].append(value)

        rows.append(
            {
                "season": season,
                "b0_flagged": sum(1 for r in leak if flag(r.get("leakage_flag"))),
                "b0_total": len(leak),
                "tail_n": num(tail["n"], 0) if tail else None,
                "start_pct_at_90": num(tail["start_pct"], 2) if tail else None,
                "p90_fitted": num(fit["p90_fitted"], 2) if fit else None,
                "xi_zero_min": xi_zero_min(season_dir),
                "v1_gw1_minus_v1_clean": mean(clean_delta),
                "xi_cap": {m: mean(v) for m, v in sorted(xi_by_model.items())},
            }
        )

    payload = {
        "experiment": "E013 four-season robustness panel",
        "xi_zero_min_source": (
            "Computed from actual_minutes in the frozen gw record files, summed "
            "across duplicate DGW rows. E009 derived it from gw_actuals instead, "
            "which gives 122/418 for 2025/26 against 123/418 here. The other "
            "three seasons match E009 exactly."
        ),
        "verdict": (
            "V1's repeatable weakness is upper-tail playing-time overconfidence, "
            "which propagates into XI blank selections. It is not supported as "
            "generic transfer mispricing or an optimizer-objective failure."
        ),
        "caveats": [
            CAVEATS["b0"],
            CAVEATS["p_start"],
            CAVEATS["new_club"],
            CAVEATS["horizon"],
        ],
        "seasons": rows,
    }
    write_json("panel.json", payload)
    return payload


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    live_counts = export_live_metadata()

    seasons = sorted(p.name for p in HISTORICAL.iterdir() if p.is_dir())
    report: dict[str, dict] = {}

    for season in seasons:
        season_dir = HISTORICAL / season
        report[season] = {
            "predictions": export_predictions(season, season_dir),
            "xi": export_xi(season, season_dir),
            "decisions": export_decisions(season, season_dir),
            "scores": export_scores(season, season_dir),
            "leakage": export_leakage(season, season_dir),
            "compare": export_compare(season, season_dir),
            "minutes": export_minutes(season, season_dir),
        }

    live = export_predictions(LIVE_SEASON, RECORDS)
    audit_live = export_audit(LIVE_SEASON, RECORDS)
    report[LIVE_SEASON] = {"predictions": live, "audit": audit_live}
    write_json(
        f"season/{LIVE_SEASON}/meta.json",
        {
            "season": LIVE_SEASON,
            "caveats": [CAVEATS["live_pool"]],
            "has_xi": False,
            "production": PRODUCTION,
            "controls": {"v1_gw1_baseline": V1_CONTROL},
        },
    )

    write_json(
        "teams_historical.json",
        {season: historical_team_map(season) for season in seasons},
    )

    panel = build_panel(seasons)

    write_json(
        "manifest.json",
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "engine": git_info(),
            "snapshot_as_of": snapshot_as_of(),
            "live_season": LIVE_SEASON,
            "production": PRODUCTION,
            "controls": {"v1_gw1_baseline": V1_CONTROL},
            "seasons": [
                {
                    "season": season,
                    "gws": report[season]["predictions"]["gws"],
                    "has_xi": report[season]["xi"]["gws"] > 0,
                    "has_lab": True,
                }
                for season in seasons
            ]
            + [
                {
                    "season": LIVE_SEASON,
                    "gws": live["gws"],
                    "has_xi": False,
                    "has_lab": False,
                }
            ],
            "caveats": CAVEATS,
        },
    )

    print(f"wrote {OUT}")
    print(f"  live snapshot: {live_counts}")
    for season in seasons + [LIVE_SEASON]:
        info = report[season]
        pred = info["predictions"]
        extra = ""
        if "xi" in info:
            leak = info["leakage"]
            extra = f"  xi_gws={info['xi']['gws']}  flagged={leak['flagged']}/{leak['total']}"
        mb = pred["bytes"] / 1_048_576
        print(
            f"  {season}: gws={pred['gws']:>2} players={pred['players']:>3} "
            f"rows={pred['rows']:>6} predictions={mb:.2f}MB{extra}"
        )
    for row in panel["seasons"]:
        zero = row["xi_zero_min"].get("all", {})
        print(
            f"  panel {row['season']}: flagged={row['b0_flagged']}/{row['b0_total']} "
            f"start@90={row['start_pct_at_90']} p90_fitted={row['p90_fitted']} "
            f"xi_0min={zero.get('pct')}% v1gw1-v1={row['v1_gw1_minus_v1_clean']}"
        )


if __name__ == "__main__":
    main()
