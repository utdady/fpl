"""V1 CLI: live projections + £100m squad / XI / captain.

Usage:
    python fpl.py --horizon 6 --strategy balanced
    python fpl.py suggest --squad myteam.json
    python fpl.py suggest --squad myteam.json --allow-hit --json
    # suggest = next-GW FT-spending optimizer; default free transfers only
    python fpl.py tc
    python fpl.py tc --season 2024-25
    python fpl.py bb
    python fpl.py bb --season 2024-25
    python fpl.py fh
    python fpl.py fh --season 2024-25
    python fpl.py fh --squad myteam.json
    python fpl.py prefs --json
    python fpl.py prefs --json --prefs prefs.json
    python fpl.py prefs --json --lock 123 --bank 1.0 --club 1=2
    # prefs = Model A vs Model A under LOCK/BAN/BANK/CLUB (same U; feasible set only)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python fpl.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.api import load_snapshot
from engine.display import render, render_suggestions
from engine.model_config import PRODUCTION
from engine.optimize import solve_squad
from engine.project import STRATEGIES, project_all
from engine.suggest import result_to_json, suggest_from_payload


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "suggest":
        return _suggest_cli(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "prefs":
        return _prefs_cli(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "tc":
        from engine.e040_tc_recommend import main as tc_main

        return tc_main(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "bb":
        from engine.e041_bb_recommend import main as bb_main

        return bb_main(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "fh":
        from engine.e046_fh_recommend import main as fh_main

        return fh_main(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "wc":
        from engine.e050_wc_recommend import main as wc_main

        return wc_main(sys.argv[2:])
    return _greenfield_cli()


def _greenfield_cli() -> int:
    parser = argparse.ArgumentParser(description="FPL V1 projection + squad optimizer")
    parser.add_argument("--horizon", type=int, default=6, help="gameweeks to look ahead")
    parser.add_argument(
        "--strategy",
        choices=STRATEGIES,
        default="balanced",
        help="safe: mean - 0.4 sd; balanced: mean; aggressive: mean + 3 P(10+)",
    )
    parser.add_argument("--top", type=int, default=20, help="how many GW projections to print")
    parser.add_argument("--refresh", action="store_true", help="bypass the 30-minute API cache")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.horizon < 1 or args.horizon > 10:
        parser.error("--horizon must be between 1 and 10")

    snapshot = load_snapshot(refresh=args.refresh)
    projections = project_all(snapshot, horizon=args.horizon, strategy=args.strategy, seed=args.seed)
    solution = solve_squad(snapshot, projections, strategy=args.strategy)
    print(render(snapshot, projections, solution, top_n=args.top))
    return 0


def _suggest_cli(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        prog="fpl.py suggest",
        description=(
            "Next-GW FT-spending optimizer: highest projected XI+C plan given available "
            "free transfers (not a selective 'should you transfer?' advisor; not V5/V7)."
        ),
    )
    parser.add_argument(
        "--squad",
        required=True,
        help="my-team JSON path, or - for stdin",
    )
    parser.add_argument(
        "--allow-hit",
        action="store_true",
        help="aggressive opt-in: also rank FT+1 plans with -4 deducted (default: free transfers only)",
    )
    parser.add_argument("--json", action="store_true", help="stdout JSON only (for the web API)")
    parser.add_argument("--refresh", action="store_true", help="bypass snapshot and projection caches")
    parser.add_argument(
        "--strategy",
        choices=STRATEGIES,
        default=PRODUCTION["strategy"],
    )
    parser.add_argument("--horizon", type=int, default=PRODUCTION["horizon_resolv"])
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    if args.squad == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(args.squad).read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"invalid squad JSON: {exc}", file=sys.stderr)
        return 2

    if not args.json:
        print("[suggest] loading snapshot + projections…", file=sys.stderr)
    snapshot = load_snapshot(refresh=args.refresh)
    result = suggest_from_payload(
        payload,
        snapshot=snapshot,
        strategy=args.strategy,
        horizon=args.horizon,
        seed=args.seed,
        refresh=args.refresh,
        allow_hit=args.allow_hit,
    )
    if args.json:
        print(json.dumps(result_to_json(result), separators=(",", ":")))
    else:
        print(render_suggestions(result))
    return 0


def _prefs_cli(argv: list[str]) -> int:
    """Model A vs Model A under v0 preference constraints."""
    from engine.preferences import (
        BANK_MENU_M,
        preferences_from_payload,
        result_to_json as prefs_to_json,
        solve_preference_pair,
    )

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="fpl.py prefs",
        description=(
            "Greenfield Model A optimum, optionally re-solved under LOCK/BAN/BANK/CLUB. "
            "Same objective; feasible set only. Not a second strategy."
        ),
    )
    parser.add_argument("--json", action="store_true", help="stdout JSON only (web API)")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--prefs", help="JSON path, or - for stdin")
    parser.add_argument("--lock", type=int, nargs="*", default=[], help="element ids to lock")
    parser.add_argument("--ban", type=int, nargs="*", default=[], help="element ids to ban")
    parser.add_argument(
        "--bank",
        type=float,
        default=None,
        help=f"min ITB in £m; one of {BANK_MENU_M}",
    )
    parser.add_argument(
        "--club",
        action="append",
        default=[],
        metavar="TEAM_ID=MAX",
        help="club cap, e.g. 1=2 (repeatable); MAX in 0..2",
    )
    parser.add_argument("--strategy", choices=STRATEGIES, default=PRODUCTION["strategy"])
    parser.add_argument("--horizon", type=int, default=PRODUCTION["horizon_resolv"])
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    payload: dict = {"lock": list(args.lock), "ban": list(args.ban), "club_max": {}}
    if args.bank is not None:
        payload["min_bank_m"] = args.bank
    for item in args.club:
        if "=" not in item:
            parser.error(f"--club expects TEAM_ID=MAX, got {item!r}")
        tid_s, lim_s = item.split("=", 1)
        payload["club_max"][int(tid_s)] = int(lim_s)
    if args.prefs:
        raw = sys.stdin.read() if args.prefs == "-" else Path(args.prefs).read_text(encoding="utf-8")
        try:
            file_payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"invalid prefs JSON: {exc}", file=sys.stderr)
            return 2
        if not isinstance(file_payload, dict):
            print("prefs JSON must be an object", file=sys.stderr)
            return 2
        # CLI flags merge over file.
        merged = {**file_payload, **{k: v for k, v in payload.items() if v}}
        if args.bank is not None:
            merged["min_bank_m"] = args.bank
        if args.lock:
            merged["lock"] = list(args.lock)
        if args.ban:
            merged["ban"] = list(args.ban)
        if args.club:
            merged["club_max"] = payload["club_max"]
        payload = merged

    try:
        prefs = preferences_from_payload(payload)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not args.json:
        print("[prefs] loading snapshot + projections…", file=sys.stderr)
    snapshot = load_snapshot(refresh=args.refresh)
    projections = project_all(
        snapshot,
        horizon=args.horizon,
        strategy=args.strategy,
        seed=args.seed,
        minutes_version=PRODUCTION["minutes_version"],
        rates_version=PRODUCTION["rates_version"],
        fixtures_version="v1",
    )
    result = solve_preference_pair(snapshot, projections, prefs, strategy=args.strategy)
    out = prefs_to_json(result)
    if args.json:
        print(json.dumps(out, separators=(",", ":")))
    else:
        s1 = out["s1"]
        print(f"Model A  U={s1['u']:.2f}  bank=£{s1['bank_m']:.1f}m  C {s1['captain']}")
        print(f"  XI: {', '.join(s1['xi'])}")
        if out["s2"]:
            s2 = out["s2"]
            print(
                f"Under prefs  U={s2['u']:.2f}  ΔU={out['delta_u']}  "
                f"D={out['distance']}  bank=£{s2['bank_m']:.1f}m  C {s2['captain']}"
            )
            print(f"  XI: {', '.join(s2['xi'])}")
            if out["enters"]:
                print(f"  in: {', '.join(out['enters'])}")
            if out["exits"]:
                print(f"  out: {', '.join(out['exits'])}")
        elif not result.preferences.empty():
            print(out["message"] or "No feasible squad under these constraints")
        else:
            print("(no preferences — S1 only)")
    return 0 if result.feasible or result.preferences.empty() else 0


if __name__ == "__main__":
    raise SystemExit(main())
