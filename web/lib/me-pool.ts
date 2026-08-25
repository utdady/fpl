import { getFixtures, getLivePlayers, getManifest, getPredictions, getTeamCodes } from "@/lib/data";
import { isGwInProgress } from "@/lib/gw-live";
import type { ComparePoolPlayer } from "@/lib/team-compare";

export async function loadMePool(): Promise<{
  season: string;
  gw: number;
  liveEnabled: boolean;
  pool: ComparePoolPlayer[];
}> {
  const manifest = await getManifest();
  const season = manifest.live_season;
  const [predictions, live, codes, fixtures] = await Promise.all([
    getPredictions(season),
    getLivePlayers(),
    getTeamCodes(season),
    getFixtures(),
  ]);

  const modelGw = predictions.gws[0] ?? 1;
  const liveEnabled = isGwInProgress(fixtures.fixtures, modelGw);
  const pool: ComparePoolPlayer[] = Object.entries(predictions.players).map(([id, series]) => {
    const i = series.gw.indexOf(modelGw);
    const meta = live.players[id];
    return {
      id: Number(id),
      name: series.name,
      pos: series.pos,
      teamCode: codes[series.team] ?? null,
      teamId: series.team,
      cost: i >= 0 ? (series.cost[i] ?? meta?.cost ?? null) : (meta?.cost ?? null),
      mu: i >= 0 ? (series.mu[i] ?? null) : null,
      sigma: i >= 0 ? (series.sigma[i] ?? null) : null,
      pStart: i >= 0 ? (series.p_start[i] ?? null) : null,
    };
  });

  return { season, gw: modelGw, liveEnabled, pool };
}
