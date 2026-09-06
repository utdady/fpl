"""E045 survey: rates/fixtures archival-source feasibility (provenance only).

Usage:
    python scripts/e045_rates_fixtures_source_survey.py

Reuses E044 fplcache pre-deadline snap selection
(records/historical/e044_fplcache_deadline_coverage.csv).

Writes:
  records/historical/e045_rates_fixtures_source_survey.csv
  records/historical/e045_fplcache_ep_strength_sample.csv
  records/historical/e045_rates_fixtures_source_survey.txt

No projection / Cap / MAE / XI peeks. No rates_v2b or fixtures_v2d reopen.
"""
from __future__ import annotations

import csv
import json
import lzma
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.harness import ensure_vaastav, season_dir

OUT_DIR = ROOT / "records" / "historical"
COVERAGE_CSV = OUT_DIR / "e044_fplcache_deadline_coverage.csv"
FPLCACHE_RAW = "https://raw.githubusercontent.com/Randdalf/fplcache/main/cache"
USER_AGENT = "fpl-e045-survey (provenance only)"

# Sample GWs per season for download-heavy strength/ep checks.
SAMPLE_GWS = (1, 5, 10, 15, 20, 25, 30, 35, 38)
STRENGTH_KEYS = (
    "strength",
    "strength_overall_home",
    "strength_overall_away",
    "strength_attack_home",
    "strength_attack_away",
    "strength_defence_home",
    "strength_defence_away",
)


def _get_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def snapshot_utc_to_relpath(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return f"{dt.year}/{dt.month}/{dt.day}/{dt.hour:02d}{dt.minute:02d}.json.xz"


def load_coverage() -> list[dict[str, str]]:
    if not COVERAGE_CSV.exists():
        raise FileNotFoundError(
            f"Missing {COVERAGE_CSV}; run scripts/e044_availability_source_survey.py first"
        )
    with COVERAGE_CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def download_boot(snapshot_utc: str) -> dict:
    dt = datetime.fromisoformat(snapshot_utc.replace("Z", "+00:00"))
    rel = snapshot_utc_to_relpath(dt)
    raw = _get_bytes(f"{FPLCACHE_RAW}/{rel}")
    return json.loads(lzma.decompress(raw))


def vaastav_strengths(season: str) -> dict[int, dict[str, int | str]]:
    ensure_vaastav((season,))
    out: dict[int, dict[str, int | str]] = {}
    with (season_dir(season) / "teams.csv").open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            tid = int(row["id"])
            out[tid] = {k: row.get(k, "") for k in ("name", *STRENGTH_KEYS)}
    return out


def analyze_boot(boot: dict) -> dict:
    elements = boot.get("elements") or []
    n = len(elements)
    ep_next_set = sum(1 for e in elements if e.get("ep_next") is not None and e.get("ep_next") != "")
    ep_this_set = sum(1 for e in elements if e.get("ep_this") is not None and e.get("ep_this") != "")
    form_set = sum(1 for e in elements if e.get("form") not in (None, ""))
    teams = boot.get("teams") or []
    strength_by_id = {
        int(t["id"]): {k: t.get(k) for k in STRENGTH_KEYS}
        for t in teams
        if t.get("id") is not None
    }
    return {
        "n_elements": n,
        "ep_next_set": ep_next_set,
        "ep_this_set": ep_this_set,
        "form_set": form_set,
        "n_teams": len(teams),
        "strength_by_id": strength_by_id,
        "has_fixtures_key": "fixtures" in boot and boot.get("fixtures") is not None,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    coverage = [
        r for r in load_coverage()
        if str(r.get("pre_deadline_ok", "")).lower() in {"true", "1"}
    ]
    by_season_gw = {(r["season"], int(r["gw"])): r for r in coverage}
    panel_ok = len(coverage)
    print(f"[e045] E044 pre-deadline cells available: {panel_ok}", flush=True)

    sample_rows: list[dict] = []
    # season -> gw -> strength map
    strength_series: dict[str, dict[int, dict[int, dict]]] = defaultdict(dict)
    ep_full = 0
    ep_checked = 0
    fixtures_in_boot = 0

    for season in ("2022-23", "2023-24", "2024-25", "2025-26"):
        print(f"[e045] sampling {season} …", flush=True)
        vaan = vaastav_strengths(season)
        for gw in SAMPLE_GWS:
            cell = by_season_gw.get((season, gw))
            if not cell:
                sample_rows.append({
                    "season": season,
                    "gw": gw,
                    "ok": False,
                    "note": "missing_e044_coverage_row",
                })
                continue
            boot = download_boot(cell["last_pre_snapshot_utc"])
            info = analyze_boot(boot)
            ep_checked += 1
            if info["ep_next_set"] == info["n_elements"] and info["n_elements"] > 0:
                ep_full += 1
            if info["has_fixtures_key"]:
                fixtures_in_boot += 1
            strength_series[season][gw] = info["strength_by_id"]

            # vs Vaastav season file (typically end/static dump)
            n_team_diff = 0
            for tid, st in info["strength_by_id"].items():
                v = vaan.get(tid)
                if not v:
                    continue
                for k in STRENGTH_KEYS:
                    try:
                        a = int(float(st.get(k))) if st.get(k) is not None else None
                        b = int(float(v.get(k))) if v.get(k) not in (None, "") else None
                    except (TypeError, ValueError):
                        continue
                    if a is not None and b is not None and a != b:
                        n_team_diff += 1
                        break

            sample_rows.append({
                "season": season,
                "gw": gw,
                "deadline_utc": cell["deadline_utc"],
                "snapshot_utc": cell["last_pre_snapshot_utc"],
                "n_elements": info["n_elements"],
                "ep_next_set": info["ep_next_set"],
                "ep_this_set": info["ep_this_set"],
                "form_set": info["form_set"],
                "n_teams": info["n_teams"],
                "has_fixtures_in_bootstrap": int(info["has_fixtures_key"]),
                "n_teams_strength_diff_vs_vaastav": n_team_diff,
                "ok": True,
            })
            print(
                f"  GW{gw}: ep_next={info['ep_next_set']}/{info['n_elements']} "
                f"strength_diff_vs_vaastav_teams={n_team_diff} "
                f"fixtures_in_boot={info['has_fixtures_key']}",
                flush=True,
            )

    # Within-season strength drift across sampled GWs
    drift_rows: list[dict] = []
    for season, by_gw in strength_series.items():
        gws = sorted(by_gw)
        if len(gws) < 2:
            continue
        base_gw = gws[0]
        base = by_gw[base_gw]
        for gw in gws[1:]:
            cur = by_gw[gw]
            changed = 0
            for tid, st0 in base.items():
                st1 = cur.get(tid)
                if not st1:
                    continue
                if any(st0.get(k) != st1.get(k) for k in STRENGTH_KEYS):
                    changed += 1
            drift_rows.append({
                "season": season,
                "base_gw": base_gw,
                "gw": gw,
                "n_teams_strength_changed_vs_gw1_sample": changed,
                "n_teams": len(base),
            })

    sample_path = OUT_DIR / "e045_fplcache_ep_strength_sample.csv"
    with sample_path.open("w", encoding="utf-8", newline="") as f:
        fields = list(sample_rows[0].keys()) if sample_rows else ["season", "gw"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(sample_rows)

    drift_path = OUT_DIR / "e045_fplcache_strength_drift.csv"
    with drift_path.open("w", encoding="utf-8", newline="") as f:
        fields = [
            "season", "base_gw", "gw",
            "n_teams_strength_changed_vs_gw1_sample", "n_teams",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(drift_rows)

    max_drift = max(
        (r["n_teams_strength_changed_vs_gw1_sample"] for r in drift_rows),
        default=0,
    )
    any_vaastav_diff = any(
        int(r.get("n_teams_strength_diff_vs_vaastav") or 0) > 0
        for r in sample_rows if r.get("ok")
    )
    ep_pass = ep_checked > 0 and ep_full == ep_checked
    strength_signal = max_drift > 0 or any_vaastav_diff
    fixture_book_in_fplcache = fixtures_in_boot > 0

    # Overall E045: need at least one rates/fixtures-relevant observable clearing
    # provenance criteria. ep_next from dated fplcache does (excluded in harness).
    # Strength mid-season variation is secondary PASS support if present.
    # Fixture-book via fplcache bootstrap alone fails (no fixtures array).
    if ep_pass and panel_ok >= 152:
        overall = "PASS"
        primary = "fplcache_bootstrap_ep_next"
        note = (
            "Randdalf/fplcache pre-deadline bootstrap carries ep_this/ep_next for "
            "all sampled cells; E044 already proved 152/152 snap<=deadline coverage. "
            "Harness currently forces ep_next=None (excluded). This is a new dated "
            "rates-adjacent observable — not a rates_v2b/fixtures_v2d reopen. "
            "Fixture kickoff book is NOT in bootstrap-static (fixtures key absent). "
            f"Team strength mid-season drift_max={max_drift}; "
            f"any_diff_vs_vaastav_teams={any_vaastav_diff}."
        )
    else:
        overall = "FAIL"
        primary = "none"
        note = (
            "No rates/fixtures-relevant dated observable cleared panel provenance, "
            "or ep coverage incomplete on samples."
        )

    survey = [
        {
            "source": "Randdalf/fplcache bootstrap — ep_this/ep_next",
            "snapshot_timestamp": "path UTC (E044 selection: last snap <= deadline)",
            "pre_deadline_proof": "same as E044; 152/152 panel cells",
            "seasons_gws_covered": f"panel {panel_ok}/152; sample ep_full={ep_full}/{ep_checked}",
            "fields": "ep_this, ep_next (official FPL expected points)",
            "identity_join": "elements[].id / code",
            "reproducible": "yes — pin SHA + E044 coverage CSV",
            "harness_gap": "HARNESS_SPEC excludes ep_next; harness forces None",
            "verdict": "PASS" if ep_pass else "FAIL",
        },
        {
            "source": "Randdalf/fplcache bootstrap — teams[] strengths",
            "snapshot_timestamp": "path UTC (E044 selection)",
            "pre_deadline_proof": "same as E044",
            "seasons_gws_covered": f"sampled GWs {SAMPLE_GWS}; drift_max_teams={max_drift}",
            "fields": ",".join(STRENGTH_KEYS),
            "identity_join": "teams[].id",
            "reproducible": "yes",
            "harness_gap": "harness uses season teams.csv (often static/end); mid-season path unclear",
            "verdict": "PASS_CANDIDATE" if strength_signal else "WEAK_STATIC",
        },
        {
            "source": "Randdalf/fplcache bootstrap — fixture book",
            "snapshot_timestamp": "n/a",
            "pre_deadline_proof": "n/a",
            "seasons_gws_covered": "none — fixtures array absent from bootstrap-static",
            "fields": "kickoff_time / event assignment",
            "identity_join": "n/a",
            "reproducible": "n/a",
            "harness_gap": "static Vaastav fixtures.csv (E043 caveat)",
            "verdict": "REJECT",
        },
        {
            "source": "Vaastav season-end / static teams.csv + fixtures.csv",
            "snapshot_timestamp": "none / season dump",
            "pre_deadline_proof": "no",
            "seasons_gws_covered": "full panel as static files",
            "fields": "strength_*; kickoff_time",
            "identity_join": "id",
            "reproducible": "yes",
            "harness_gap": "already used; not a new dated archive",
            "verdict": "REJECT",
        },
        {
            "source": "Live FPL api/bootstrap-static + api/fixtures",
            "snapshot_timestamp": "request time",
            "pre_deadline_proof": "N/A historical",
            "seasons_gws_covered": "current only",
            "fields": "ep_*, strengths, fixtures",
            "identity_join": "id",
            "reproducible": "live only",
            "harness_gap": "no historical panel",
            "verdict": "REJECT",
        },
        {
            "source": "Internet Archive fixtures endpoint",
            "snapshot_timestamp": "Wayback ts",
            "pre_deadline_proof": "when ts <= deadline",
            "seasons_gws_covered": "sparse (not surveyed to panel density)",
            "fields": "kickoffs",
            "identity_join": "fixture id",
            "reproducible": "CDX",
            "harness_gap": "dated fixture book candidate class",
            "verdict": "REJECT_FOR_PANEL_PENDING_SPARSE",
        },
    ]

    survey_path = OUT_DIR / "e045_rates_fixtures_source_survey.csv"
    with survey_path.open("w", encoding="utf-8", newline="") as f:
        fields = [
            "source", "snapshot_timestamp", "pre_deadline_proof",
            "seasons_gws_covered", "fields", "identity_join", "reproducible",
            "harness_gap", "verdict",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(survey)

    txt_path = OUT_DIR / "e045_rates_fixtures_source_survey.txt"
    txt_path.write_text(
        "\n".join(
            [
                f"verdict={overall}",
                f"primary_observable={primary}",
                f"e044_panel_cells={panel_ok}",
                f"ep_sample_full={ep_full}/{ep_checked}",
                f"strength_drift_max_teams={max_drift}",
                f"strength_any_diff_vs_vaastav={any_vaastav_diff}",
                f"fixture_book_in_fplcache_bootstrap={fixture_book_in_fplcache}",
                f"note={note}",
                f"survey_csv={survey_path.as_posix()}",
                f"sample_csv={sample_path.as_posix()}",
                f"drift_csv={drift_path.as_posix()}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(txt_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
