"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { liveDisplay, type LiveDisplay } from "./live-display";
import { useLive, type LiveStat } from "./use-live";

type LiveContextValue = ReturnType<typeof useLive> & {
  /** True when every fixture for that team in this GW is finished (or provisional). */
  fixtureFinishedByTeam: Map<number, boolean>;
};

const LiveContext = createContext<LiveContextValue | null>(null);

type FplFixtureRow = {
  event: number;
  team_h: number;
  team_a: number;
  finished: boolean;
  finished_provisional: boolean;
};

function buildFixtureFinishedMap(fixtures: FplFixtureRow[], gw: number) {
  const map = new Map<number, boolean>();
  for (const f of fixtures) {
    if (f.event !== gw) continue;
    const done = f.finished || f.finished_provisional;
    for (const team of [f.team_h, f.team_a]) {
      const prev = map.get(team);
      map.set(team, prev === undefined ? done : prev && done);
    }
  }
  return map;
}

export function LiveProvider({
  gw,
  enabled,
  children,
}: {
  gw: number;
  enabled: boolean;
  children: React.ReactNode;
}) {
  const live = useLive(gw, enabled);
  const [fixtureFinishedByTeam, setFixtureFinishedByTeam] = useState<Map<number, boolean>>(
    new Map(),
  );

  const loadFixtures = useCallback(async () => {
    try {
      const response = await fetch("/api/fpl/fixtures");
      if (!response.ok) throw new Error(String(response.status));
      const data = (await response.json()) as FplFixtureRow[];
      setFixtureFinishedByTeam(buildFixtureFinishedMap(data, gw));
    } catch {
      setFixtureFinishedByTeam(new Map());
    }
  }, [gw]);

  useEffect(() => {
    if (!enabled) {
      setFixtureFinishedByTeam(new Map());
      return;
    }
    void loadFixtures();
    const timer = setInterval(loadFixtures, 60_000);
    return () => clearInterval(timer);
  }, [enabled, loadFixtures]);

  const value = useMemo(
    () => ({ ...live, fixtureFinishedByTeam }),
    [live, fixtureFinishedByTeam],
  );

  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>;
}

export function useLiveContext(): LiveContextValue | null {
  return useContext(LiveContext);
}

/** Raw in-play row; null when live polling is off or not ready. */
export function useLiveStat(playerId: number): LiveStat | null {
  const live = useContext(LiveContext);
  if (!live || live.status !== "ready") return null;
  return live.stats.get(playerId) ?? null;
}

/** Card-ready live points with pending vs blank handling. */
export function useLiveDisplay(
  playerId: number,
  teamId?: number | null,
): LiveDisplay | null {
  const live = useContext(LiveContext);
  if (!live || live.status !== "ready") return null;
  const stat = live.stats.get(playerId);
  if (!stat) return null;
  const fixtureFinished =
    teamId != null ? (live.fixtureFinishedByTeam.get(teamId) ?? false) : false;
  return liveDisplay(stat, fixtureFinished);
}
