import type { Position } from "./types";

export const ELEMENT_POS: Record<number, Position> = {
  1: "GKP",
  2: "DEF",
  3: "MID",
  4: "FWD",
};

export const XI_RANGE: Record<Position, { min: number; max: number }> = {
  GKP: { min: 1, max: 1 },
  DEF: { min: 3, max: 5 },
  MID: { min: 2, max: 5 },
  FWD: { min: 1, max: 3 },
};

export const MAX_PER_CLUB = 3;

export const CHIP_LABEL: Record<string, string> = {
  wildcard: "Wildcard",
  freehit: "Free Hit",
  bboost: "Bench Boost",
  "3xc": "Triple Captain",
};

export function xiLegal(positions: Position[]): string | null {
  if (positions.length !== 11) return "Starting XI must have 11 players";
  for (const pos of Object.keys(XI_RANGE) as Position[]) {
    const n = positions.filter((p) => p === pos).length;
    const { min, max } = XI_RANGE[pos];
    if (n < min || n > max) return `Need ${min}–${max} ${pos} in the XI (have ${n})`;
  }
  return null;
}

export function clubLegal(teamIds: number[]): string | null {
  const counts = new Map<number, number>();
  for (const id of teamIds) {
    const n = (counts.get(id) ?? 0) + 1;
    if (n > MAX_PER_CLUB) return "Max three players from one club";
    counts.set(id, n);
  }
  return null;
}

export function transferHit(
  made: number,
  limit: number | null,
  extra: number,
  costPer = 4,
): number {
  const cap = limit ?? 1;
  return Math.max(0, made + extra - cap) * costPer;
}

export function formationOf(positions: Position[]): string {
  const n = (p: Position) => positions.filter((x) => x === p).length;
  return `${n("DEF")}-${n("MID")}-${n("FWD")}`;
}
