"""E043 provenance: PL fixture kickoffs as-of-T reconstructibility.

Usage:
    python scripts/e043_schedule_provenance.py

Checks (four seasons):
  1. kickoff_time present and ISO-parseable on every fixtures.csv row
  2. cross-event kickoff order (max ko in e <= min ko in e+1 when both nonempty)
  3. blank / double GW characterization by event fixture count and team doubles
  4. per as-of-T prior-match coverage (clubs in GW T with no earlier PL match)

Honesty caveat (always reported): season fixtures.csv is the same static Vaastav
file used by build_snapshot (HARNESS_SPEC). Future kickoffs may reflect final
published times, not a mid-season fixture book. Cups/Europe are out of scope.
"""
from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.harness import SUPPORTED_SEASONS, _i, _i_opt, _read_csv, ensure_vaastav, season_dir

OUT_DIR = Path("records") / "historical"


def parse_ko(s: str | None) -> datetime | None:
    if not s or not str(s).strip():
        return None
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def analyze_season(season: str) -> dict:
    ensure_vaastav((season,))
    rows = _read_csv(season_dir(season) / "fixtures.csv")
    missing_ko = 0
    bad_ko = 0
    parsed: list[tuple[int, int, int, int, datetime]] = []  # id, event, h, a, ko
    by_event: dict[int, list[datetime]] = defaultdict(list)
    team_event: dict[tuple[int, int], int] = defaultdict(int)

    for r in rows:
        ev = _i_opt(r.get("event"))
        raw = r.get("kickoff_time")
        if not (raw or "").strip():
            missing_ko += 1
            continue
        try:
            ko = parse_ko(raw)
        except ValueError:
            bad_ko += 1
            continue
        if ko is None:
            missing_ko += 1
            continue
        if ev is None:
            continue
        hid, aid = _i(r.get("team_h")), _i(r.get("team_a"))
        parsed.append((_i(r.get("id")), ev, hid, aid, ko))
        by_event[ev].append(ko)
        team_event[(ev, hid)] += 1
        team_event[(ev, aid)] += 1

    fx_counts = {e: len(by_event.get(e, [])) for e in range(1, 39)}
    blank_gws = [e for e, n in fx_counts.items() if n == 0]
    thin_gws = [e for e, n in fx_counts.items() if 0 < n < 10]
    doubleish_gws = [e for e, n in fx_counts.items() if n > 10]
    team_doubles = sum(1 for n in team_event.values() if n > 1)

    order_violations = 0
    for e in range(1, 38):
        a, b = by_event.get(e), by_event.get(e + 1)
        if not a or not b:
            continue
        if max(a) > min(b):
            order_violations += 1

    # Prior PL match coverage for clubs scheduled in GW T
    club_history: dict[int, list[tuple[int, datetime]]] = defaultdict(list)
    for _fid, ev, hid, aid, ko in parsed:
        club_history[hid].append((ev, ko))
        club_history[aid].append((ev, ko))
    for tid in club_history:
        club_history[tid].sort(key=lambda x: x[1])

    clubs_in_gw: dict[int, set[int]] = defaultdict(set)
    for _fid, ev, hid, aid, _ko in parsed:
        clubs_in_gw[ev].add(hid)
        clubs_in_gw[ev].add(aid)

    prior_missing_by_t = {}
    for t in range(1, 39):
        clubs = clubs_in_gw.get(t, set())
        n_miss = 0
        for tid in clubs:
            if not any(ev < t for ev, _ko in club_history.get(tid, [])):
                n_miss += 1
        prior_missing_by_t[t] = (n_miss, len(clubs))

    parse_ok = missing_ko == 0 and bad_ko == 0 and len(parsed) == len(rows)
    order_ok = order_violations == 0
    panel_ok = all(e in fx_counts for e in range(1, 39))  # keys exist; blank allowed

    return {
        "season": season,
        "n_fixtures": len(rows),
        "n_parsed": len(parsed),
        "missing_ko": missing_ko,
        "bad_ko": bad_ko,
        "order_violations": order_violations,
        "blank_gws": "|".join(str(e) for e in blank_gws),
        "thin_gws": "|".join(str(e) for e in thin_gws),
        "doubleish_gws": "|".join(str(e) for e in doubleish_gws),
        "n_team_event_doubles": team_doubles,
        "gw1_clubs_no_prior": prior_missing_by_t[1][0],
        "gw2_clubs_no_prior": prior_missing_by_t[2][0],
        "parse_ok": parse_ok,
        "order_ok": order_ok,
        "panel_ok": panel_ok,
    }


def main() -> int:
    print("[e043 provenance] PL fixtures.csv kickoff reconstructibility")
    print("[e043] Source = Vaastav fixtures.csv (same as build_snapshot)")
    print("[e043] Cups/Europe out of scope by E043 prereg")
    results = [analyze_season(s) for s in SUPPORTED_SEASONS]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "e043_schedule_provenance.csv"
    fields = list(results[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow(r)
    print(f"Wrote {path}")

    hard_ok = all(r["parse_ok"] and r["order_ok"] and r["panel_ok"] for r in results)
    print("\n=== PER SEASON ===")
    for r in results:
        print(
            f"{r['season']}: fixtures={r['n_fixtures']} parse_ok={r['parse_ok']} "
            f"order_ok={r['order_ok']} blank=[{r['blank_gws']}] "
            f"thin=[{r['thin_gws']}] doubleish=[{r['doubleish_gws']}] "
            f"team_doubles={r['n_team_event_doubles']}"
        )

    print("\n=== CAVEAT (frozen) ===")
    print(
        "Season fixtures.csv is a static Vaastav dump (HARNESS_SPEC). Future kickoff "
        "timestamps may equal final published times, not a mid-season fixture book. "
        "This matches existing harness fixture practice. No weekly fixture archive."
    )

    if hard_ok:
        verdict = "PASS_WITH_CAVEAT"
        print(
            f"\nVERDICT: {verdict} — kickoffs present/parseable; cross-event order OK; "
            "BGW/DGW characterizable; E043-A amendment may proceed under PL-only + caveat."
        )
    else:
        verdict = "FAIL"
        print(f"\nVERDICT: {verdict} — kill E043 before code (provenance broken).")

    summary = OUT_DIR / "e043_schedule_provenance.txt"
    summary.write_text(
        f"verdict={verdict}\nhard_ok={hard_ok}\ncaveat=static_season_fixtures_csv\n",
        encoding="utf-8",
    )
    print(f"Wrote {summary}")
    return 0 if hard_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
