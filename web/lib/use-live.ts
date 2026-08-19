"use client";

import { useCallback, useEffect, useState } from "react";

export type LiveStat = { points: number; minutes: number; bonus: number };

type State = {
  stats: Map<number, LiveStat>;
  status: "off" | "loading" | "ready" | "error";
  fetchedAt: Date | null;
};

/** Matches the proxy's revalidate window, so polling never outruns the cache. */
const POLL_MS = 60_000;

/**
 * In-play points via the server proxy. Off by default: a frozen prediction
 * viewer has no business polling an API until someone asks it to.
 */
export function useLive(gw: number, enabled: boolean) {
  const [state, setState] = useState<State>({
    stats: new Map(),
    status: "off",
    fetchedAt: null,
  });

  const load = useCallback(async () => {
    setState((prev) => ({ ...prev, status: prev.stats.size ? prev.status : "loading" }));
    try {
      const response = await fetch(`/api/fpl/event/${gw}/live`);
      if (!response.ok) throw new Error(String(response.status));
      const data = (await response.json()) as {
        elements?: { id: number; stats?: Record<string, number> }[];
      };
      const stats = new Map<number, LiveStat>();
      for (const element of data.elements ?? []) {
        stats.set(element.id, {
          points: element.stats?.total_points ?? 0,
          minutes: element.stats?.minutes ?? 0,
          bonus: element.stats?.bonus ?? 0,
        });
      }
      setState({ stats, status: "ready", fetchedAt: new Date() });
    } catch {
      setState((prev) => ({ ...prev, status: "error" }));
    }
  }, [gw]);

  useEffect(() => {
    if (!enabled) {
      setState({ stats: new Map(), status: "off", fetchedAt: null });
      return;
    }
    void load();
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [enabled, load]);

  return state;
}
