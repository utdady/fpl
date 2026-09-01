import type { PlayerSeries } from "./types";

export type PlayerDiagSlice = {
  quantiles: [number, number, number, number, number] | null;
  p0: number | null;
  components: Record<string, number> | null;
  actual: number | null;
  mu: number | null;
};

const COMP_KEYS = [
  "appearance",
  "goals",
  "assists",
  "clean_sheet",
  "defensive",
  "saves",
  "goals_conceded",
  "yellow",
  "bonus",
] as const;

/** Diagnostics slice for one GW from columnar predictions export. */
export function playerDiagAt(series: PlayerSeries, gw: number): PlayerDiagSlice | null {
  const i = series.gw.indexOf(gw);
  if (i < 0) return null;
  const q05 = series.q05?.[i];
  const q25 = series.q25?.[i];
  const q50 = series.q50?.[i];
  const q75 = series.q75?.[i];
  const q95 = series.q95?.[i];
  const hasQ =
    q05 != null && q25 != null && q50 != null && q75 != null && q95 != null;
  const components: Record<string, number> = {};
  let hasComp = false;
  for (const k of COMP_KEYS) {
    const v = series[`mu_${k}` as keyof PlayerSeries] as (number | null)[] | undefined;
    const val = v?.[i];
    if (val != null) {
      components[k] = val;
      hasComp = true;
    }
  }
  return {
    quantiles: hasQ ? [q05, q25, q50, q75, q95] : null,
    p0: series.p0?.[i] ?? null,
    components: hasComp ? components : null,
    actual: series.pts[i],
    mu: series.mu[i],
  };
}
