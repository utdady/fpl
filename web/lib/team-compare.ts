/**
 * Squad overlap, XI+C xP, and this-GW win chance under independent Normal totals.
 * Uses frozen V1 μ/σ only — not live FPL xP.
 */

import type { FplPick } from "./fpl-entry";
import type { Position } from "./types";

export type ComparePoolPlayer = {
  id: number;
  name: string;
  pos: Position;
  teamCode: string | null;
  cost: number | null;
  mu: number | null;
  sigma: number | null;
  pStart: number | null;
};

export type SquadTotals = {
  mu: number;
  sigma: number | null;
  complete: boolean;
};

function xiPicks(picks: FplPick[]): FplPick[] {
  return picks.filter((p) => p.position <= 11);
}

/** XI + captain (2μ / 4σ²). Missing σ → sigma null but μ still summed. */
export function xiCaptainTotals(
  picks: FplPick[],
  byId: Map<number, ComparePoolPlayer>,
): SquadTotals {
  const xi = xiPicks(picks);
  let mu = 0;
  let varSum = 0;
  let sigmaOk = true;
  for (const p of xi) {
    const player = byId.get(p.element);
    const m = player?.mu;
    const s = player?.sigma;
    if (m == null) {
      sigmaOk = false;
      continue;
    }
    const mult = p.is_captain ? 2 : 1;
    mu += mult * m;
    if (s == null) sigmaOk = false;
    else varSum += mult * mult * s * s;
  }
  return {
    mu,
    sigma: sigmaOk && xi.length > 0 ? Math.sqrt(varSum) : null,
    complete: xi.length === 11 && xi.every((p) => byId.get(p.element)?.mu != null),
  };
}

/** Φ(z) for standard Normal — Abramowitz & Stegun 26.2.17. */
export function normalCdf(z: number): number {
  if (!Number.isFinite(z)) return 0.5;
  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const d = 0.3989423 * Math.exp((-z * z) / 2);
  const p =
    d *
    t *
    (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return z > 0 ? 1 - p : p;
}

export type GwEdge = {
  /** P(mine total > rival total) under independent Normal */
  pMineAhead: number | null;
  d: number;
  sigmaD: number | null;
  mine: SquadTotals;
  rival: SquadTotals;
};

export function gwEdge(
  minePicks: FplPick[],
  rivalPicks: FplPick[],
  byId: Map<number, ComparePoolPlayer>,
): GwEdge {
  const mine = xiCaptainTotals(minePicks, byId);
  const rival = xiCaptainTotals(rivalPicks, byId);
  const d = mine.mu - rival.mu;
  if (mine.sigma == null || rival.sigma == null || mine.sigma + rival.sigma === 0) {
    return { pMineAhead: null, d, sigmaD: null, mine, rival };
  }
  const sigmaD = Math.sqrt(mine.sigma * mine.sigma + rival.sigma * rival.sigma);
  if (sigmaD === 0) return { pMineAhead: null, d, sigmaD, mine, rival };
  return {
    pMineAhead: normalCdf(d / sigmaD),
    d,
    sigmaD,
    mine,
    rival,
  };
}

export type Overlap = {
  both: number[];
  onlyMine: number[];
  onlyRival: number[];
  mineCap: number | null;
  rivalCap: number | null;
  mineVc: number | null;
  rivalVc: number | null;
};

export function squadOverlap(minePicks: FplPick[], rivalPicks: FplPick[]): Overlap {
  const mineIds = new Set(minePicks.map((p) => p.element));
  const rivalIds = new Set(rivalPicks.map((p) => p.element));
  const both: number[] = [];
  const onlyMine: number[] = [];
  const onlyRival: number[] = [];
  for (const id of mineIds) {
    if (rivalIds.has(id)) both.push(id);
    else onlyMine.push(id);
  }
  for (const id of rivalIds) {
    if (!mineIds.has(id)) onlyRival.push(id);
  }
  return {
    both,
    onlyMine,
    onlyRival,
    mineCap: minePicks.find((p) => p.is_captain)?.element ?? null,
    rivalCap: rivalPicks.find((p) => p.is_captain)?.element ?? null,
    mineVc: minePicks.find((p) => p.is_vice_captain)?.element ?? null,
    rivalVc: rivalPicks.find((p) => p.is_vice_captain)?.element ?? null,
  };
}

export type NotesVsV1 = {
  startNotes: string[];
  upgrades: string[];
  inBalanced: number[];
  notBalanced: number[];
};

export function notesVsV1(
  picks: FplPick[],
  pool: ComparePoolPlayer[],
  balancedIds: number[],
  bank: number,
  formatMu: (n: number | null) => string,
  formatPrice: (n: number | null) => string,
): NotesVsV1 {
  const byId = new Map(pool.map((p) => [p.id, p]));
  const squadIds = new Set(picks.map((p) => p.element));
  const xi = picks.filter((p) => p.position <= 11);
  const bench = picks.filter((p) => p.position > 11);

  const startNotes = bench.flatMap((b) => {
    const benchP = byId.get(b.element);
    if (benchP?.mu == null) return [];
    const weaker = xi
      .map((s) => byId.get(s.element))
      .filter(
        (s): s is ComparePoolPlayer =>
          !!s && s.pos === benchP.pos && (s.mu ?? 0) + 0.3 < (benchP.mu ?? 0),
      );
    return weaker
      .slice(0, 1)
      .map(
        (s) =>
          `${benchP.name} (${formatMu(benchP.mu)}) over ${s.name} (${formatMu(s.mu)})`,
      );
  });

  const upgrades = [...squadIds]
    .map((pid) => {
      const have = byId.get(pid);
      if (!have || have.cost == null || have.mu == null) return null;
      const better = pool
        .filter(
          (p) =>
            p.pos === have.pos &&
            !squadIds.has(p.id) &&
            p.cost != null &&
            p.mu != null &&
            p.cost <= (have.cost ?? 0) + bank &&
            p.mu > (have.mu ?? 0) + 0.4,
        )
        .sort((a, b) => (b.mu ?? 0) - (a.mu ?? 0))[0];
      if (!better) return null;
      return `${have.name} → ${better.name} (${formatMu(have.mu)} to ${formatMu(better.mu)}, ${formatPrice(better.cost)})`;
    })
    .filter((n): n is string => !!n)
    .slice(0, 5);

  return {
    startNotes,
    upgrades,
    inBalanced: balancedIds.filter((pid) => !squadIds.has(pid)),
    notBalanced: [...squadIds].filter((pid) => !balancedIds.includes(pid)),
  };
}

/** Diff-focused notes between two 15s (rival vs mine), not vs V1. */
export type NotesVsMine = {
  startGaps: string[];
  onlyThem: string[];
  onlyMe: string[];
};

export function notesVsMine(
  rivalPicks: FplPick[],
  minePicks: FplPick[],
  byId: Map<number, ComparePoolPlayer>,
  formatMu: (n: number | null) => string,
): NotesVsMine {
  const rivalBench = rivalPicks.filter((p) => p.position > 11);
  const mineXi = minePicks.filter((p) => p.position <= 11);
  const mineIds = new Set(minePicks.map((p) => p.element));
  const rivalIds = new Set(rivalPicks.map((p) => p.element));

  const startGaps = rivalBench.flatMap((b) => {
    const benchP = byId.get(b.element);
    if (benchP?.mu == null) return [];
    const weakerOnMine = mineXi
      .map((s) => byId.get(s.element))
      .filter(
        (s): s is ComparePoolPlayer =>
          !!s && s.pos === benchP.pos && (s.mu ?? 0) + 0.3 < (benchP.mu ?? 0),
      );
    return weakerOnMine
      .slice(0, 1)
      .map(
        (s) =>
          `Their bench ${benchP.name} (${formatMu(benchP.mu)}) vs your ${s.name} (${formatMu(s.mu)})`,
      );
  });

  const onlyThem = [...rivalIds]
    .filter((id) => !mineIds.has(id))
    .map((id) => byId.get(id)?.name ?? `#${id}`)
    .slice(0, 8);
  const onlyMe = [...mineIds]
    .filter((id) => !rivalIds.has(id))
    .map((id) => byId.get(id)?.name ?? `#${id}`)
    .slice(0, 8);

  return { startGaps, onlyThem, onlyMe };
}
