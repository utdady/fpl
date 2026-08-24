import { LiveProvider } from "@/lib/live-context";
import { ManageTeam } from "@/components/manage-team";
import { MeGate } from "@/components/me-gate";
import { loadMePool } from "@/lib/me-pool";

export default async function MeTransfersPage() {
  const { season, gw, liveEnabled, pool } = await loadMePool();
  return (
    <LiveProvider gw={gw} enabled={liveEnabled}>
      <MeGate>
        <ManageTeam pool={pool} season={season} gw={gw} view="transfers" />
      </MeGate>
    </LiveProvider>
  );
}
