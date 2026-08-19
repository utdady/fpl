import type { PlayerSeries, Position } from "./types";

export const POSITIONS: Position[] = ["GKP", "DEF", "MID", "FWD"];

/** FPL stores price in tenths of a million. */
export const price = (cost: number | null | undefined) =>
  cost == null ? "—" : `£${(cost / 10).toFixed(1)}m`;

export const dec = (value: number | null | undefined, digits = 2) =>
  value == null ? "—" : value.toFixed(digits);

export const pct = (value: number | null | undefined, digits = 0) =>
  value == null ? "—" : `${(value * 100).toFixed(digits)}%`;

export const signed = (value: number | null | undefined, digits = 1) =>
  value == null ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;

/**
 * Actual start rate observed at each model p_start bucket, from E013's
 * four-season panel. The UI shows this beside every p_start so a high model
 * confidence is never read at face value.
 */
const CALIBRATION: { min: number; observed: number }[] = [
  { min: 0.9, observed: 0.77 },
  { min: 0.8, observed: 0.74 },
  { min: 0.7, observed: 0.46 },
  { min: 0.6, observed: 0.67 },
  { min: 0.0, observed: 0.23 },
];

export function calibratedStart(pStart: number | null | undefined): number | null {
  if (pStart == null) return null;
  return CALIBRATION.find((band) => pStart >= band.min)?.observed ?? null;
}

/** Index into a columnar series for a given gameweek. */
export function atGw(series: PlayerSeries, gw: number): number {
  return series.gw.indexOf(gw);
}

export function seriesValue(
  series: PlayerSeries,
  key: keyof PlayerSeries,
  gw: number,
): number | null {
  const i = atGw(series, gw);
  if (i < 0) return null;
  const column = series[key];
  return Array.isArray(column) ? ((column[i] as number | null) ?? null) : null;
}

/** Formation string from an eleven, e.g. "3-5-2". */
export function formation(positions: Position[]): string {
  const count = (p: Position) => positions.filter((x) => x === p).length;
  return `${count("DEF")}-${count("MID")}-${count("FWD")}`;
}

export const POSITION_LABEL: Record<Position, string> = {
  GKP: "Goalkeeper",
  DEF: "Defender",
  MID: "Midfielder",
  FWD: "Forward",
};

/** Fixture difficulty 1-5 to a colour from the risk/actual axis. */
export function difficultyColor(fdr: number | null): string {
  if (fdr == null) return "var(--color-faint)";
  if (fdr <= 2) return "var(--color-actual)";
  if (fdr === 3) return "var(--color-muted)";
  if (fdr === 4) return "color-mix(in oklab, var(--color-risk) 65%, var(--color-oracle))";
  return "var(--color-risk)";
}

export const seasonLabel = (season: string) => season.replace("-", "/");
