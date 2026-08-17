"""Plain-text report. No UI."""
from __future__ import annotations

from engine.models import PlayerProjection, Snapshot, SquadSolution


def _money(tenths: int) -> str:
    return f"£{tenths / 10:.1f}m"


def _row(cols: list[str], widths: list[int]) -> str:
    return "  ".join(c[:w].ljust(w) for c, w in zip(cols, widths))


def render(
    snapshot: Snapshot,
    projections: list[PlayerProjection],
    solution: SquadSolution,
    top_n: int = 20,
) -> str:
    next_e = snapshot.next_event()
    by_id = {p.player.id: p for p in projections}
    gws = solution.horizon_gws
    gw_span = f"GW{gws[0]}–GW{gws[-1]}" if gws else ""
    as_of = snapshot.as_of.strftime("%Y-%m-%d %H:%M UTC")
    deadline = next_e.deadline or "?"
    lines = [
        f"FPL V1  |  {snapshot.season_label}  |  as of {as_of}",
        f"Next: {next_e.name}  deadline {deadline}",
        f"Strategy: {solution.strategy}   Horizon: {gw_span}   Decay: 0.90",
        "",
        f"--- {next_e.name} projections (top {top_n} by xP) ---",
    ]

    ranked = sorted(projections, key=lambda p: p.next_mu, reverse=True)
    widths = [18, 3, 3, 6, 5, 5, 6, 5, 6]
    lines.append(_row(["player", "pos", "tm", "price", "xP", "sd", "P(st)", "P60", "P10+"], widths))
    for proj in ranked[:top_n]:
        p = proj.player
        tm = snapshot.team(p.team_id).short_name
        lines.append(
            _row(
                [
                    p.web_name,
                    p.position,
                    tm,
                    _money(p.now_cost),
                    f"{proj.next_mu:.2f}",
                    f"{proj.next_sigma:.2f}",
                    f"{proj.next_p_start:.2f}",
                    f"{proj.next_p_60:.2f}",
                    f"{proj.next_p_10:.2f}",
                ],
                widths,
            )
        )

    lines += ["", f"--- Optimal {_money(snapshot.squad.budget)} squad ---"]
    sw = [18, 3, 3, 6, 8, 6, 6]
    lines.append(_row(["player", "pos", "tm", "price", "horiz xP", "GW xP", "P(st)"], sw))
    for p in solution.players:
        proj = by_id[p.id]
        tm = snapshot.team(p.team_id).short_name
        lines.append(
            _row(
                [
                    p.web_name,
                    p.position,
                    tm,
                    _money(p.now_cost),
                    f"{proj.horizon_mu:.2f}",
                    f"{proj.next_mu:.2f}",
                    f"{proj.next_p_start:.2f}",
                ],
                sw,
            )
        )
    lines.append(
        f"Cost {_money(solution.cost)}   Bank {_money(solution.bank)}   "
        f"Horizon utility {solution.horizon_utility:.1f}"
    )

    lines += ["", f"--- Best XI ({next_e.name}) ---"]
    for p in solution.xi:
        proj = by_id[p.id]
        flag = ""
        if p.id == solution.captain.id:
            flag = " (C)"
        elif p.id == solution.vice.id:
            flag = " (VC)"
        tm = snapshot.team(p.team_id).short_name
        lines.append(
            f"  {p.position:3} {p.web_name:16} {tm:3}  {_money(p.now_cost):>6}  "
            f"xP {proj.next_mu:5.2f}  sd {proj.next_sigma:4.2f}  P10+ {proj.next_p_10:.2f}{flag}"
        )
    lines.append("  Bench:")
    for i, p in enumerate(solution.bench, start=1):
        proj = by_id[p.id]
        tm = snapshot.team(p.team_id).short_name
        lines.append(
            f"    {i}. {p.position:3} {p.web_name:16} {tm:3}  {_money(p.now_cost):>6}  xP {proj.next_mu:5.2f}"
        )
    lines.append(
        f"XI + captain xP {solution.next_xi_mu:.2f}   utility {solution.next_xi_utility:.2f}"
    )

    lines += ["", "--- Top alternatives (not in squad) ---"]
    for pos, p, mu in solution.alternatives:
        tm = snapshot.team(p.team_id).short_name
        lines.append(f"  {pos:3} {p.web_name:16} {tm:3}  {_money(p.now_cost):>6}  GW xP {mu:5.2f}")

    lines.append("")
    lines.append(
        "Notes: xP is minutes- and fixture-adjusted. sd / P10+ come from an event simulation, "
        "not a second ML model. FDR is not used as the fixture engine; team overall strength is."
    )
    return "\n".join(lines)
