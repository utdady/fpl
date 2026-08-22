import type { Fixture } from "./types";

/** True when at least one fixture in the GW has not finished. */
export function isGwInProgress(fixtures: Fixture[], gw: number): boolean {
  const gwFixtures = fixtures.filter((f) => f.gw === gw);
  if (gwFixtures.length === 0) return false;
  return gwFixtures.some((f) => !f.finished);
}
