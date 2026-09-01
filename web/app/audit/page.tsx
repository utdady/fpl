import { redirect } from "next/navigation";

import { getManifest, getPredictions } from "@/lib/data";

/** Default audit view: live season, first exported GW. */
export default async function AuditIndexPage() {
  const manifest = await getManifest();
  const season = manifest.live_season;
  let gw = 1;
  try {
    const predictions = await getPredictions(season);
    gw = predictions.gws[0] ?? 1;
  } catch {
    gw = 1;
  }
  redirect(`/audit/${season}/${gw}`);
}
