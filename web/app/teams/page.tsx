import { TeamTracker, type PoolPlayer } from "@/components/team-tracker";
import { getFixtures, getLivePlayers, getManifest, getPredictions, getStrategies, getTeamCodes } from "@/lib/data";
import { isGwInProgress } from "@/lib/gw-live";
import type { StrategyKey } from "@/lib/types";

export default async function TeamsPage() {
  const manifest = await getManifest();
  const season = manifest.live_season;
  const [predictions, live, codes, fixtures] = await Promise.all([
    getPredictions(season),
    getLivePlayers(),
    getTeamCodes(season),
    getFixtures(),
  ]);

  let balancedIds: number[] = [];
  try {
    const strategies = await getStrategies(season);
    balancedIds = strategies.squads.balanced.players.map((p) => p.id);
  } catch {
    balancedIds = [];
  }

  const gw = predictions.gws[0] ?? 1;
  const liveEnabled = isGwInProgress(fixtures.fixtures, gw);
  const pool: PoolPlayer[] = Object.entries(predictions.players).map(([id, series]) => {
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
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Teams</h1>
        <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-muted">
          Track public FPL entries by ID. Mark yours, preview the pitch, then open a
          team for Notes vs V1 or rival compare (overlap, xP gap, this-GW edge).
          Scores use the frozen V1 pool — not live FPL xP.
        </p>
      </div>
      <TeamTracker
        gw={gw}
        season={season}
        pool={pool}
        balancedIds={balancedIds}
        strategy={"balanced" as StrategyKey}
        liveEnabled={liveEnabled}
      />
    </div>
  );
}
