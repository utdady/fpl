import { TeamTracker, type PoolPlayer } from "@/components/team-tracker";
import { getLivePlayers, getManifest, getPredictions, getStrategies, getTeamCodes } from "@/lib/data";
import type { StrategyKey } from "@/lib/types";

export default async function TeamsPage() {
  const manifest = await getManifest();
  const season = manifest.live_season;
  const [predictions, live, codes] = await Promise.all([
    getPredictions(season),
    getLivePlayers(),
    getTeamCodes(season),
  ]);

  let balancedIds: number[] = [];
  try {
    const strategies = await getStrategies(season);
    balancedIds = strategies.squads.balanced.players.map((p) => p.id);
  } catch {
    balancedIds = [];
  }

  const gw = predictions.gws[0] ?? 1;
  const pool: PoolPlayer[] = Object.entries(predictions.players).map(([id, series]) => {
    const i = series.gw.indexOf(gw);
    const meta = live.players[id];
    return {
      id: Number(id),
      name: series.name,
      pos: series.pos,
      teamCode: codes[series.team] ?? null,
      cost: i >= 0 ? (series.cost[i] ?? meta?.cost ?? null) : (meta?.cost ?? null),
      mu: i >= 0 ? (series.mu[i] ?? null) : null,
      pStart: i >= 0 ? (series.p_start[i] ?? null) : null,
    };
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Teams</h1>
        <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-muted">
          Track public FPL entries by ID. Picks come from the official API; xP and
          transfer notes come from the frozen V1 pool. Nothing here writes a squad
          back into the model.
        </p>
      </div>
      <TeamTracker gw={gw} pool={pool} balancedIds={balancedIds} strategy={"balanced" as StrategyKey} />
    </div>
  );
}
