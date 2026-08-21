"use client";

import { Pitch } from "./pitch";
import type { CellPlayer } from "./player-cell";
import type { FplPick } from "@/lib/fpl-entry";
import type { ComparePoolPlayer } from "@/lib/team-compare";
import type { Position } from "@/lib/types";

function toCell(
  pick: FplPick,
  byId: Map<number, ComparePoolPlayer>,
): CellPlayer {
  const p = byId.get(pick.element);
  return {
    id: pick.element,
    name: p?.name ?? `#${pick.element}`,
    pos: (p?.pos ?? "MID") as Position,
    teamCode: p?.teamCode ?? null,
    cost: p?.cost ?? null,
    mu: p?.mu ?? null,
    sigma: p?.sigma ?? null,
    pStart: p?.pStart ?? null,
    p10: null,
    pts: null,
    mins: null,
    captain: pick.is_captain,
    vice: pick.is_vice_captain && !pick.is_captain,
  };
}

export function picksToCells(
  picks: FplPick[],
  byId: Map<number, ComparePoolPlayer>,
): { xi: CellPlayer[]; bench: CellPlayer[] } {
  const sorted = [...picks].sort((a, b) => a.position - b.position);
  return {
    xi: sorted.filter((p) => p.position <= 11).map((p) => toCell(p, byId)),
    bench: sorted.filter((p) => p.position > 11).map((p) => toCell(p, byId)),
  };
}

export function EntryPitch({
  picks,
  pool,
  season,
  gw,
}: {
  picks: FplPick[];
  pool: ComparePoolPlayer[];
  season: string;
  gw: number;
}) {
  const byId = new Map(pool.map((p) => [p.id, p]));
  const { xi, bench } = picksToCells(picks, byId);
  if (xi.length === 0) {
    return (
      <p className="text-[12px] text-muted">
        No starting XI on the API for this gameweek yet.
      </p>
    );
  }
  return <Pitch players={xi} bench={bench} season={season} gw={gw} />;
}
