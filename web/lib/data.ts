import { readFile } from "node:fs/promises";
import path from "node:path";
import { cache } from "react";

import type {
  Compare,
  Decisions,
  Fixtures,
  Leakage,
  LivePlayers,
  Manifest,
  Minutes,
  Panel,
  Predictions,
  Scores,
  Strategies,
  Teams,
  Xi,
} from "./types";

const DATA_DIR = path.join(process.cwd(), "public", "data");

/**
 * Reads from public/data at build time. The same files are served statically,
 * so client components can fetch them lazily from /data/... instead.
 */
const readJson = cache(async <T,>(rel: string): Promise<T> => {
  const raw = await readFile(path.join(DATA_DIR, rel), "utf-8");
  return JSON.parse(raw) as T;
});

export const getManifest = () => readJson<Manifest>("manifest.json");
export const getTeams = () => readJson<Teams>("teams.json");
export const getLivePlayers = () => readJson<LivePlayers>("players.json");
export const getFixtures = () => readJson<Fixtures>("fixtures.json");
export const getPanel = () => readJson<Panel>("panel.json");
/** Season to team id to FPL short code. */
export const getHistoricalTeams = () =>
  readJson<Record<string, Record<string, string>>>("teams_historical.json");

export const getPredictions = (season: string) =>
  readJson<Predictions>(`season/${season}/predictions.json`);
export const getXi = (season: string) => readJson<Xi>(`season/${season}/xi.json`);
export const getDecisions = (season: string) =>
  readJson<Decisions>(`season/${season}/decisions.json`);
export const getScores = (season: string) => readJson<Scores>(`season/${season}/scores.json`);
export const getLeakage = (season: string) => readJson<Leakage>(`season/${season}/leakage.json`);
export const getCompare = (season: string) => readJson<Compare>(`season/${season}/compare.json`);
export const getMinutes = (season: string) => readJson<Minutes>(`season/${season}/minutes.json`);

/** Team id to short code, resolved per season. */
export async function getTeamCodes(season: string): Promise<Record<number, string>> {
  const manifest = await getManifest();
  if (season === manifest.live_season) {
    const { teams } = await getTeams();
    return Object.fromEntries(teams.map((t) => [t.id, t.code]));
  }
  const historical = await getHistoricalTeams();
  const codes = historical[season] ?? {};
  return Object.fromEntries(Object.entries(codes).map(([id, code]) => [Number(id), code]));
}

export const getStrategies = (season: string) =>
  readJson<Strategies>(`season/${season}/strategies.json`);

/** Historical seasons that have both a Lab and an XI board. */
export async function getLabSeasons(): Promise<string[]> {
  const manifest = await getManifest();
  return manifest.seasons.filter((s) => s.has_lab).map((s) => s.season);
}

/** Every season in the export, including the live prediction-only season. */
export async function getAllSeasons(): Promise<string[]> {
  const manifest = await getManifest();
  return manifest.seasons.map((s) => s.season);
}
