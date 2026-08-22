"use client";

import { useMemo } from "react";

import { useLiveContext } from "./live-context";
import {
  gwEdge,
  gwEdgeLive,
  type ComparePoolPlayer,
  type GwEdgeExtended,
} from "./team-compare";
import type { FplPick } from "./fpl-entry";

export function useGwEdge(
  minePicks: FplPick[],
  rivalPicks: FplPick[],
  byId: Map<number, ComparePoolPlayer>,
  liveEnabled: boolean,
): GwEdgeExtended {
  const live = useLiveContext();

  return useMemo(() => {
    const frozen = gwEdge(minePicks, rivalPicks, byId);
    if (!liveEnabled || !live || live.status !== "ready" || live.stats.size === 0) {
      return frozen;
    }
    return gwEdgeLive(minePicks, rivalPicks, byId, live.stats, live.fixtureFinishedByTeam);
  }, [minePicks, rivalPicks, byId, liveEnabled, live]);
}
