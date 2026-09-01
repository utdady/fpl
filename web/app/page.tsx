import Link from "next/link";

import { ModelProvenance } from "@/components/model-provenance";
import { PoolTable, type PoolRow } from "@/components/pool-table";
import { Section } from "@/components/ui/section";
import { Stat, StatRow } from "@/components/ui/stat";
import {
  getFixtures,
  getLabSeasons,
  getLivePlayers,
  getManifest,
  getPredictions,
  getTeamCodes,
} from "@/lib/data";
import { seasonLabel } from "@/lib/format";
import { SNAPSHOT_DAY } from "@/lib/snapshot";

export default async function PoolPage() {
  const manifest = await getManifest();
  const season = manifest.live_season;

  const [predictions, live, codes, fixtures, labSeasons] = await Promise.all([
    getPredictions(season),
    getLivePlayers(),
    getTeamCodes(season),
    getFixtures(),
    getLabSeasons(),
  ]);

  const gw = predictions.gws[0] ?? 1;
  const fixturesThisGw = fixtures.fixtures.filter((f) => f.gw === gw);

  const opponent = new Map<number, { code: string; home: boolean; fdr: number | null }>();
  for (const f of fixturesThisGw) {
    opponent.set(f.h, { code: codes[f.a] ?? "—", home: true, fdr: f.hd });
    opponent.set(f.a, { code: codes[f.h] ?? "—", home: false, fdr: f.ad });
  }

  const rows: PoolRow[] = Object.entries(predictions.players).map(([id, series]) => {
    const i = series.gw.indexOf(gw);
    const meta = live.players[id];
    const fixture = opponent.get(series.team);
    return {
      id: Number(id),
      name: series.name,
      pos: series.pos,
      teamCode: codes[series.team] ?? null,
      teamId: series.team,
      cost: i >= 0 ? (series.cost[i] ?? null) : null,
      mu: i >= 0 ? (series.mu[i] ?? null) : null,
      sigma: i >= 0 ? (series.sigma[i] ?? null) : null,
      pStart: i >= 0 ? (series.p_start[i] ?? null) : null,
      p60: i >= 0 ? (series.p_60[i] ?? null) : null,
      p10: i >= 0 ? (series.p10[i] ?? null) : null,
      pts: i >= 0 ? (series.pts[i] ?? null) : null,
      mins: i >= 0 ? (series.min[i] ?? null) : null,
      chanceNext: meta?.chance_next ?? null,
      owned: meta?.owned ?? null,
      epNext: meta?.ep_next ?? null,
      status: meta?.status ?? null,
      news: meta?.news ?? null,
      opponent: fixture?.code ?? null,
      home: fixture?.home ?? null,
      fdr: fixture?.fdr ?? null,
    };
  });

  const withProjection = rows.filter((r) => r.mu != null);
  const flagged = rows.filter((r) => r.news);
  const latestLab = labSeasons.at(-1);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            {seasonLabel(season)} · Gameweek {gw}
          </h1>
          <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-muted">
            The frozen prediction pool (V1 control). μ/σ come from the pre-deadline
            capture; prices, ownership and availability come from the cached FPL
            snapshot{SNAPSHOT_DAY ? ` of ${SNAPSHOT_DAY}` : ""} and are not live.
          </p>
          <ModelProvenance
            className="mt-3 max-w-2xl"
            role="frozen_record"
            config={predictions.model_config ?? manifest.controls?.v1_gw1_baseline}
            manifest={manifest}
          />
        </div>
        {latestLab && (
          <Link
            href={`/lab/${latestLab}`}
            className="rounded-md border border-edge px-3 py-1.5 text-[12px] text-muted transition-colors hover:border-edge-bright hover:text-ink"
          >
            How well does this model do? →
          </Link>
        )}
      </div>

      <Section
        title="Squad selection is not in this record"
        subtitle="capture.py persists player projections only, and the frozen fifteen was solved on a six-gameweek horizon utility the record does not store. It cannot be reconstructed from the artifact, so no eleven is shown for the live season."
        source="records/gw01_v1.0.csv"
      >
        <StatRow>
          <Stat label="Players projected" value={withProjection.length} tone="model" />
          <Stat label="Fixtures" value={fixturesThisGw.length} />
          <Stat
            label="With injury news"
            value={flagged.length}
            tone={flagged.length ? "risk" : "neutral"}
          />
          <Stat
            label="Snapshot"
            value={<span className="text-sm">{live.as_of?.slice(0, 10) ?? "—"}</span>}
          />
        </StatRow>
      </Section>

      <Section
        title="Prediction pool"
        subtitle="Sort any column. Hover a name for the gameweek card, click for the full outlook."
        source="records/gw01_v1.0.csv + .cache/fpl/bootstrap.json"
        caveats={predictions.caveats}
      >
        <PoolTable rows={rows} season={season} gw={gw} />
      </Section>
    </div>
  );
}
