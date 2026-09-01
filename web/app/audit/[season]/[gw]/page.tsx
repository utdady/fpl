import { notFound } from "next/navigation";

import { AuditBoard } from "@/components/audit-board";
import { getAudit, getGwDiagnostics, getManifest, getPredictions } from "@/lib/data";

export async function generateStaticParams() {
  const manifest = await getManifest();
  const season = manifest.live_season;
  const predictions = await getPredictions(season).catch(() => null);
  const gws = predictions?.gws ?? [1];
  return gws.map((gw) => ({ season, gw: String(gw) }));
}

export default async function AuditGwPage({
  params,
}: {
  params: Promise<{ season: string; gw: string }>;
}) {
  const { season, gw: gwParam } = await params;
  const gw = Number(gwParam);
  const manifest = await getManifest();
  const meta = manifest.seasons.find((s) => s.season === season);
  if (!meta || !Number.isFinite(gw) || gw < 1 || gw > meta.gws) notFound();

  const [audit, diagnostics, predictions] = await Promise.all([
    getAudit(season),
    getGwDiagnostics(season, gw),
    getPredictions(season).catch(() => null),
  ]);

  return (
    <AuditBoard
      season={season}
      gw={gw}
      audit={audit}
      diagnostics={diagnostics}
      predictions={predictions}
      manifest={manifest}
    />
  );
}
