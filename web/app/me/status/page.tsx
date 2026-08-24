import { MeStatusDashboard } from "@/components/me-status";
import { loadMePool } from "@/lib/me-pool";

export default async function MeStatusPage() {
  const { pool } = await loadMePool();
  return <MeStatusDashboard pool={pool} />;
}
