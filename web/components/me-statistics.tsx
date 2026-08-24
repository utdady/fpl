"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { MeGate } from "./me-gate";
import { Section } from "./ui/section";
import { Stat, StatRow } from "./ui/stat";
import { fplFetch, type FplHistoryRow } from "@/lib/fpl-entry";
import { useSession } from "@/lib/use-session";

export function MeStatisticsPage() {
  return (
    <MeGate>
      <StatisticsInner />
    </MeGate>
  );
}

function StatisticsInner() {
  const session = useSession();
  const [history, setHistory] = useState<FplHistoryRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!session.entryId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      const res = await fplFetch<{ current?: FplHistoryRow[] }>(
        `entry/${session.entryId}/history`,
      );
      if (cancelled) return;
      setLoading(false);
      if (!res.ok) {
        setError("Could not load history");
        return;
      }
      setHistory(res.data.current ?? []);
    })();
    return () => {
      cancelled = true;
    };
  }, [session.entryId]);

  if (loading) return <p className="text-[12px] text-muted">Loading statistics…</p>;
  if (error) return <p className="text-[13px] text-risk">{error}</p>;

  const latest = history.at(-1);
  const chart = history.map((row) => ({
    gw: row.event,
    points: row.points,
    total: row.total_points,
    rank: row.rank,
  }));

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Statistics</h1>
        <p className="mt-1 text-[12px] text-muted">{session.name} · season history</p>
      </div>

      <Section title="Latest">
        <StatRow>
          <Stat label="GW points" value={latest?.points ?? "—"} tone="actual" />
          <Stat label="Total" value={latest?.total_points ?? "—"} />
          <Stat
            label="Overall rank"
            value={latest?.rank != null ? latest.rank.toLocaleString() : "—"}
          />
          <Stat label="Transfers (GW)" value={latest?.event_transfers ?? "—"} />
        </StatRow>
      </Section>

      <Section title="Points by gameweek" source="entry/{id}/history">
        {chart.length === 0 ? (
          <p className="text-[12px] text-muted">No gameweeks yet.</p>
        ) : (
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--color-edge)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="gw"
                  tick={{ fill: "var(--color-faint)", fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: "var(--color-faint)", fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  width={32}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-panel)",
                    border: "1px solid var(--color-edge)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="points"
                  stroke="var(--color-actual)"
                  strokeWidth={2}
                  dot={false}
                  name="GW points"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </Section>

      <Section title="Gameweek log">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12.5px]">
            <thead className="label-xs text-faint">
              <tr>
                <th className="pb-2 pr-3 font-normal">GW</th>
                <th className="pb-2 pr-3 text-right font-normal">Pts</th>
                <th className="pb-2 pr-3 text-right font-normal">Total</th>
                <th className="pb-2 pr-3 text-right font-normal">Rank</th>
                <th className="pb-2 text-right font-normal">Transfers</th>
              </tr>
            </thead>
            <tbody>
              {[...history].reverse().map((row) => (
                <tr key={row.event} className="border-t border-edge/70">
                  <td className="tnum py-2 pr-3">{row.event}</td>
                  <td className="tnum py-2 pr-3 text-right text-actual">{row.points}</td>
                  <td className="tnum py-2 pr-3 text-right">{row.total_points}</td>
                  <td className="tnum py-2 pr-3 text-right text-muted">
                    {row.rank?.toLocaleString() ?? "—"}
                  </td>
                  <td className="tnum py-2 text-right text-muted">
                    {row.event_transfers}
                    {row.event_transfers_cost > 0 ? ` (−${row.event_transfers_cost})` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
