import { TeamDetail } from "@/components/team-detail";
import { getLivePlayers, getManifest, getPredictions, getStrategies, getTeamCodes } from "@/lib/data";
import type { PoolPlayer } from "@/components/team-tracker";

export default async function TeamDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: raw } = await params;
  const id = Number(raw);
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
  const pool: PoolPlayer[] = Object.entries(predictions.players).map(([pid, series]) => {
    const i = series.gw.indexOf(gw);
    const meta = live.players[pid];
    return {
      id: Number(pid),
      name: series.name,
      pos: series.pos,
      teamCode: codes[series.team] ?? null,
      cost: i >= 0 ? (series.cost[i] ?? meta?.cost ?? null) : (meta?.cost ?? null),
      mu: i >= 0 ? (series.mu[i] ?? null) : null,
      sigma: i >= 0 ? (series.sigma[i] ?? null) : null,
      pStart: i >= 0 ? (series.p_start[i] ?? null) : null,
    };
  });

  if (!Number.isInteger(id) || id <= 0) {
    return (
      <p className="text-[13px] text-risk">Invalid entry ID.</p>
    );
  }

  return (
    <TeamDetail
      id={id}
      gw={gw}
      season={season}
      pool={pool}
      balancedIds={balancedIds}
    />
  );
}
