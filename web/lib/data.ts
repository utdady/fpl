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
  const names = historical[season] ?? {};
  return Object.fromEntries(
    Object.entries(names).map(([id, name]) => [Number(id), shortCode(name)]),
  );
}

const CODE_OVERRIDES: Record<string, string> = {
  "Manchester City": "MCI",
  "Manchester Utd": "MUN",
  "Manchester United": "MUN",
  "Newcastle Utd": "NEW",
  "Nott'm Forest": "NFO",
  "Nottingham Forest": "NFO",
  "Sheffield Utd": "SHU",
  "Tottenham Hotspur": "TOT",
  "West Ham United": "WHU",
  "Wolverhampton Wanderers": "WOL",
  "Leicester City": "LEI",
  "Leeds United": "LEE",
  Brighton: "BHA",
  Spurs: "TOT",
  Wolves: "WOL",
};

function shortCode(name: string): string {
  if (CODE_OVERRIDES[name]) return CODE_OVERRIDES[name];
  const words = name.split(/\s+/).filter(Boolean);
  if (words.length >= 3) return words.map((w) => w[0]).join("").slice(0, 3).toUpperCase();
  return name.slice(0, 3).toUpperCase();
}

/** Historical seasons that have both a Lab and an XI board. */
export async function getLabSeasons(): Promise<string[]> {
  const manifest = await getManifest();
  return manifest.seasons.filter((s) => s.has_lab).map((s) => s.season);
}
