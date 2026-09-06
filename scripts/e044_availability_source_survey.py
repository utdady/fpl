"""E044 survey: decision-time availability archive feasibility (provenance only).

Usage:
    python scripts/e044_availability_source_survey.py

Writes:
  records/historical/e044_availability_source_survey.csv
  records/historical/e044_fplcache_deadline_coverage.csv
  records/historical/e044_availability_source_survey.txt

No projection, Cap, MAE, or XI peeks. Measures whether candidate archives expose
timestamped pre-deadline FPL availability fields joinable by element id/code.
"""
from __future__ import annotations

import csv
import json
import lzma
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "records" / "historical"

FPLCACHE_API = "https://api.github.com/repos/Randdalf/fplcache"
FPLCACHE_RAW = "https://raw.githubusercontent.com/Randdalf/fplcache/main/cache"
USER_AGENT = "fpl-e044-survey (local research; provenance only)"

# Panel seasons used by existing FAIL/PASS gates.
PANEL = (
    ("2022-23", 2023, 5, 28),  # near-final snapshot used only to read event deadlines
    ("2023-24", 2024, 5, 19),
    ("2024-25", 2025, 5, 25),
    ("2025-26", 2026, 5, 25),
)

LOOKBACK_HOURS = 7 * 24  # max age of last snapshot before deadline


def _get_json(url: str) -> object:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def _get_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def _parse_cache_path(year: int, rel: str) -> datetime | None:
    # rel: month/day/HHMM.json.xz
    try:
        month_s, day_s, fn = rel.split("/")
        hhmm = fn.split(".")[0]
        return datetime(
            year,
            int(month_s),
            int(day_s),
            int(hhmm[:2]),
            int(hhmm[2:]),
            tzinfo=timezone.utc,
        )
    except (ValueError, IndexError):
        return None


def index_fplcache_years(years: range) -> list[datetime]:
    """All snapshot datetimes (UTC, from path) for year folders."""
    root = _get_json(f"{FPLCACHE_API}/contents/cache?ref=main")
    assert isinstance(root, list)
    by_name = {d["name"]: d for d in root if d.get("type") == "dir"}
    stamps: list[datetime] = []
    for y in years:
        d = by_name.get(str(y))
        if not d:
            continue
        tree = _get_json(d["git_url"] + "?recursive=1")
        assert isinstance(tree, dict)
        for t in tree.get("tree", []):
            if t.get("type") != "blob":
                continue
            path = t.get("path") or ""
            if not path.endswith(".json.xz"):
                continue
            dt = _parse_cache_path(y, path)
            if dt is not None:
                stamps.append(dt)
    stamps.sort()
    return stamps


def load_bootstrap_near(year: int, month: int, day: int) -> dict:
    last_err: Exception | None = None
    for delta in range(0, 10):
        for sign in (0, -1, 1) if delta == 0 else (-1, 1):
            if delta == 0 and sign != 0:
                continue
            dd = day + sign * delta
            if dd < 1 or dd > 28:
                continue
            try:
                listing = _get_json(
                    f"{FPLCACHE_API}/contents/cache/{year}/{month}/{dd}?ref=main"
                )
            except urllib.error.HTTPError as e:
                last_err = e
                continue
            assert isinstance(listing, list)
            files = sorted(
                (
                    x
                    for x in listing
                    if str(x.get("name", "")).endswith(".json.xz")
                ),
                key=lambda x: str(x["name"]),
            )
            if not files:
                continue
            pick = files[min(2, len(files) - 1)]
            raw = _get_bytes(pick["download_url"])
            return json.loads(lzma.decompress(raw))
    raise RuntimeError(
        f"no snapshots near {year}-{month}-{day}: {last_err}"
    )


def last_pre_deadline(
    stamps: list[datetime], deadline: datetime
) -> datetime | None:
    lo = deadline - timedelta(hours=LOOKBACK_HOURS)
    best: datetime | None = None
    for s in stamps:
        if s < lo:
            continue
        if s > deadline:
            break
        best = s
    return best


@dataclass
class GwRow:
    season: str
    gw: int
    deadline_utc: str
    last_pre_utc: str
    lag_hours: float | None
    ok: bool


def measure_fplcache_coverage(stamps: list[datetime]) -> list[GwRow]:
    rows: list[GwRow] = []
    for season, y, m, d in PANEL:
        boot = load_bootstrap_near(y, m, d)
        events = {int(ev["id"]): ev for ev in boot["events"]}
        for gw in range(1, 39):
            ev = events.get(gw)
            if not ev or not ev.get("deadline_time"):
                rows.append(GwRow(season, gw, "", "", None, False))
                continue
            dl = datetime.fromisoformat(
                str(ev["deadline_time"]).replace("Z", "+00:00")
            )
            pre = last_pre_deadline(stamps, dl)
            if pre is None:
                rows.append(GwRow(season, gw, dl.isoformat(), "", None, False))
            else:
                lag = (dl - pre).total_seconds() / 3600.0
                rows.append(
                    GwRow(
                        season,
                        gw,
                        dl.isoformat(),
                        pre.isoformat(),
                        round(lag, 2),
                        True,
                    )
                )
    return rows


def write_coverage_csv(path: Path, rows: list[GwRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "season",
                "gw",
                "deadline_utc",
                "last_pre_snapshot_utc",
                "lag_hours",
                "pre_deadline_ok",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    r.season,
                    r.gw,
                    r.deadline_utc,
                    r.last_pre_utc,
                    "" if r.lag_hours is None else r.lag_hours,
                    r.ok,
                ]
            )


def survey_rows(fplcache_summary: str) -> list[dict[str, str]]:
    """One row per concrete archive / source class instance."""
    return [
        {
            "source": "Randdalf/fplcache (GitHub; LZMA bootstrap-static)",
            "snapshot_timestamp": "path year/month/day/HHMM.json.xz (treated as UTC)",
            "pre_deadline_proof": (
                "filename capture clock; select last snap <= events[].deadline_time; "
                "spot-check shows post-deadline snaps on same day must be excluded"
            ),
            "seasons_gws_covered": fplcache_summary,
            "fields": "status, chance_of_playing_this/next_round, news, news_added (+ full bootstrap)",
            "identity_join": "elements[].id and elements[].code",
            "reproducible": "yes — pin repo SHA + path; 4x/day GHA cache",
            "verdict": "PASS_CANDIDATE",
        },
        {
            "source": "Vaastav Fantasy-Premier-League season-end players_raw.csv",
            "snapshot_timestamp": "none (season dump / evolving file)",
            "pre_deadline_proof": "no — HARNESS_SPEC excludes undated chance_*/news",
            "seasons_gws_covered": "panel seasons as end-state only",
            "fields": "status, chance_*, news (final values)",
            "identity_join": "id / code",
            "reproducible": "yes (pinned commit)",
            "verdict": "REJECT",
        },
        {
            "source": "Live FPL api/bootstrap-static/",
            "snapshot_timestamp": "HTTP request time only",
            "pre_deadline_proof": "N/A for historical panel",
            "seasons_gws_covered": "current season live state only",
            "fields": "status, chance_*, news",
            "identity_join": "id / code",
            "reproducible": "yes for live; no historical replay",
            "verdict": "REJECT",
        },
        {
            "source": "olbauday/FPL-Core-Insights By Gameweek playerstats",
            "snapshot_timestamp": "GW folder label; README: end-of-gameweek state",
            "pre_deadline_proof": "weak/fail — documents end-of-GW not pre-deadline capture clock",
            "seasons_gws_covered": "2025-26 has GW1–38 folders; 2024-25 flat (no By Gameweek); not 2022-24",
            "fields": "chance_*, status, news (claimed)",
            "identity_join": "player id",
            "reproducible": "yes if pinned commit",
            "verdict": "REJECT",
        },
        {
            "source": "Internet Archive CDX of bootstrap-static",
            "snapshot_timestamp": "Wayback timestamp",
            "pre_deadline_proof": "yes when capture ts <= deadline",
            "seasons_gws_covered": "sparse (CDX sample from 2019+; not 4x/day panel density)",
            "fields": "full bootstrap when archived",
            "identity_join": "id / code",
            "reproducible": "yes via CDX URL+timestamp",
            "verdict": "REJECT_FOR_PANEL",
        },
        {
            "source": "martgra/fpl-timeseries-data (Azure blobs)",
            "snapshot_timestamp": "%Y-%m-%dT%H:%M:%SZ filename (claimed)",
            "pre_deadline_proof": "possible if blobs retained",
            "seasons_gws_covered": "stale — last push ~2021-09; outside panel",
            "fields": "bootstrap-static",
            "identity_join": "id / code",
            "reproducible": "uncertain (Azure access / retention)",
            "verdict": "REJECT",
        },
        {
            "source": "Jiayu S3 fpl-2018-19-data (historical blog)",
            "snapshot_timestamp": "filename ISO (twice daily)",
            "pre_deadline_proof": "yes for 2018-19",
            "seasons_gws_covered": "2018-19 only — outside panel",
            "fields": "bootstrap-static",
            "identity_join": "id / code",
            "reproducible": "if S3 still public",
            "verdict": "REJECT",
        },
        {
            "source": "Official FPL element-summary history",
            "snapshot_timestamp": "per-match history rows; no status timeline",
            "pre_deadline_proof": "does not timestamp chance_*/status",
            "seasons_gws_covered": "match history across seasons",
            "fields": "minutes/points history — not availability status",
            "identity_join": "element id",
            "reproducible": "yes",
            "verdict": "REJECT",
        },
        {
            "source": "Understat / FBRef lineups",
            "snapshot_timestamp": "match/event time (usually post-KO)",
            "pre_deadline_proof": "fail for pre-deadline decision cutoff",
            "seasons_gws_covered": "broad",
            "fields": "lineups / xG — not FPL chance_*",
            "identity_join": "fuzzy name",
            "reproducible": "partial",
            "verdict": "REJECT",
        },
        {
            "source": "Project self-capture going forward (engine.capture / bootstrap cache)",
            "snapshot_timestamp": "controlled local stamp",
            "pre_deadline_proof": "yes by design",
            "seasons_gws_covered": "future GWs only — cannot backfill panel",
            "fields": "chosen bootstrap fields",
            "identity_join": "id / code",
            "reproducible": "yes",
            "verdict": "PASS_FUTURE_ONLY",
        },
    ]


def write_survey_csv(path: Path, rows: list[dict[str, str]]) -> None:
    cols = [
        "source",
        "snapshot_timestamp",
        "pre_deadline_proof",
        "seasons_gws_covered",
        "fields",
        "identity_join",
        "reproducible",
        "verdict",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r[c] for c in cols})


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[e044] indexing Randdalf/fplcache snapshot paths…", flush=True)
    stamps = index_fplcache_years(range(2021, 2027))
    if not stamps:
        print("ERROR: no fplcache stamps", file=sys.stderr)
        return 1
    print(
        f"[e044] fplcache n={len(stamps)} "
        f"first={stamps[0].isoformat()} last={stamps[-1].isoformat()}",
        flush=True,
    )

    print("[e044] measuring pre-deadline coverage vs panel deadlines…", flush=True)
    cov = measure_fplcache_coverage(stamps)
    cov_path = OUT_DIR / "e044_fplcache_deadline_coverage.csv"
    write_coverage_csv(cov_path, cov)

    by_season: dict[str, list[GwRow]] = {}
    for r in cov:
        by_season.setdefault(r.season, []).append(r)

    parts = []
    all_ok = True
    lags: list[float] = []
    for season, rs in by_season.items():
        ok_n = sum(1 for x in rs if x.ok)
        all_ok = all_ok and ok_n == 38
        season_lags = [x.lag_hours for x in rs if x.lag_hours is not None]
        lags.extend(season_lags)
        mx = max(season_lags) if season_lags else None
        parts.append(f"{season}:{ok_n}/38" + (f" max_lag_h={mx}" if mx is not None else ""))

    fplcache_summary = (
        f"continuous cache {stamps[0].date()}→{stamps[-1].date()}; "
        + "; ".join(parts)
        + ("; ALL panel GWs have last snap <= deadline" if all_ok else "; GAPS")
    )

    rows = survey_rows(fplcache_summary)
    # Upgrade / downgrade fplcache verdict from measured coverage
    if all_ok:
        rows[0]["verdict"] = "PASS"
        overall = "PASS"
        note = (
            "Randdalf/fplcache clears all six E044 criteria at survey depth. "
            "E044-A may freeze exactly one availability signal+map; no minutes "
            "code in this card."
        )
    else:
        rows[0]["verdict"] = "PASS_CANDIDATE_GAPS"
        overall = "FAIL" if not any(r.ok for r in cov) else "INCOMPLETE"
        note = (
            "fplcache is the only strong candidate but panel pre-deadline "
            "coverage is incomplete; do not open E044-A until gaps resolved "
            "or coverage minimum frozen."
        )

    survey_csv = OUT_DIR / "e044_availability_source_survey.csv"
    write_survey_csv(survey_csv, rows)

    lag_mean = sum(lags) / len(lags) if lags else None
    lag_max = max(lags) if lags else None
    txt = OUT_DIR / "e044_availability_source_survey.txt"
    txt.write_text(
        "\n".join(
            [
                f"verdict={overall}",
                f"primary_source=Randdalf/fplcache",
                f"fplcache_snapshots={len(stamps)}",
                f"fplcache_first={stamps[0].isoformat()}",
                f"fplcache_last={stamps[-1].isoformat()}",
                f"panel_gw_ok={sum(1 for r in cov if r.ok)}/{len(cov)}",
                f"lag_hours_mean={lag_mean}",
                f"lag_hours_max={lag_max}",
                f"lookback_hours={LOOKBACK_HOURS}",
                f"timezone_assumption=filename_HHMM_as_UTC",
                f"note={note}",
                f"survey_csv={survey_csv.as_posix()}",
                f"coverage_csv={cov_path.as_posix()}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(txt.read_text(encoding="utf-8"))
    print(f"[e044] wrote {survey_csv}")
    print(f"[e044] wrote {cov_path}")
    print(f"[e044] wrote {txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
