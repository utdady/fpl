import { getPredictions, getTeamCodes, getXi } from "./data";
import type { CellPlayer } from "@/components/player-cell";
import type { XiPlayer } from "./types";

/**
 * decision_decomp.csv carries no team_id, so club codes and the sigma/P10+ the
 * hover card needs are joined from the frozen prediction records.
 */
export async function buildXi(season: string, gw: number) {
  const [xi, predictions, codes] = await Promise.all([
    getXi(season),
    getPredictions(season),
    getTeamCodes(season),
  ]);

  const rows = xi.gws[String(gw)] ?? [];

  const toCell = (row: XiPlayer, captain: boolean): CellPlayer => {
    const series = predictions.players[String(row.id)];
    const i = series ? series.gw.indexOf(gw) : -1;
    const teamId = series?.team ?? null;
    return {
      id: row.id,
      name: row.name,
      pos: row.pos,
      cost: row.cost,
      teamCode: teamId != null ? (codes[teamId] ?? null) : null,
      mu: row.v1_mu,
      sigma: i >= 0 ? (series!.sigma[i] ?? null) : null,
      pStart: row.v1_p_start,
      p10: i >= 0 ? (series!.p10[i] ?? null) : null,
      pts: row.pts,
      mins: row.mins,
      captain,
    };
  };

  const v1 = rows.filter((r) => r.v1_xi === 1).map((r) => toCell(r, r.v1_cap === 1));
  const b0 = rows
    .filter((r) => r.b0_xi === 1)
    .map((r) => ({ ...toCell(r, r.b0_cap === 1), mu: r.b0_mu }));

  return { rows, v1, b0, caveats: xi.caveats, availableGws: Object.keys(xi.gws).map(Number) };
}
