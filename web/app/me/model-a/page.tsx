import { PreferenceSolve } from "@/components/preference-solve";
import { loadMePool } from "@/lib/me-pool";

export default async function MeModelAPage() {
  const { pool } = await loadMePool();
  return (
    <main className="px-5 pb-16 lg:px-8">
      <PreferenceSolve pool={pool} />
    </main>
  );
}
