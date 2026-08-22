import { LiveProvider } from "@/lib/live-context";
import { ManageTeam } from "@/components/manage-team";
import { getFixtures, getLivePlayers, getManifest, getPredictions, getTeamCodes } from "@/lib/data";
import { isGwInProgress } from "@/lib/gw-live";
import type { ComparePoolPlayer } from "@/lib/team-compare";

export default async function MePage() {
  const manifest = await getManifest();
  const season = manifest.live_season;
  const [predictions, live, codes, fixtures] = await Promise.all([
    getPredictions(season),
    getLivePlayers(),
    getTeamCodes(season),
    getFixtures(),
  ]);

  const gw = predictions.gws[0] ?? 1;
  const liveEnabled = isGwInProgress(fixtures.fixtures, gw);
  const pool: ComparePoolPlayer[] = Object.entries(predictions.players).map(([id, series]) => {
    const i = series.gw.indexOf(gw);
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

  return (
    <LiveProvider gw={gw} enabled={liveEnabled}>
      <ManageTeam pool={pool} season={season} gw={gw} />
    </LiveProvider>
  );
}
