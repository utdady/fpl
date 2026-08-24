import { LiveProvider } from "@/lib/live-context";
import { ManageTeam } from "@/components/manage-team";
import { MeGate } from "@/components/me-gate";
import { loadMePool } from "@/lib/me-pool";

export default async function MePickTeamPage() {
  const { season, gw, liveEnabled, pool } = await loadMePool();
  return (
    <LiveProvider gw={gw} enabled={liveEnabled}>
      <MeGate>
        <ManageTeam pool={pool} season={season} gw={gw} view="pick-team" />
      </MeGate>
    </LiveProvider>
  );
}
