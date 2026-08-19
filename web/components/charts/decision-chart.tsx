"use client";

import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AXIS, GRID, chartTooltip } from "./theme";
import type { Compare, DecisionGw } from "@/lib/types";

const MODELS = [
  { key: "B3_v1", label: "V1", color: "var(--color-model)" },
  { key: "B0_xp", label: "B0 xP", color: "var(--color-b0)" },
  { key: "B1_season_pts", label: "B1 season pts", color: "var(--color-muted)" },
  { key: "B2_pp90", label: "B2 pp90", color: "var(--color-faint)" },
];

/**
 * XI + captain per gameweek for every model. Weeks where B0 tripped the
 * pre-registered leakage flag are shaded, because reading B0's line on those
 * weeks as a ceiling is the exact mistake E008 warns about.
 */
export function DecisionChart({
  compare,
  decisions,
  flaggedGws,
}: {
  compare: Compare;
  decisions: DecisionGw[];
  flaggedGws: number[];
}) {
  const byGw = new Map<number, Record<string, number | null>>();
  for (const [model, games] of Object.entries(compare.models)) {
    for (const game of games) {
      const row = byGw.get(game.gw) ?? { gw: game.gw };
      row[model] = game.xi;
      byGw.set(game.gw, row);
    }
  }
  const data = [...byGw.values()].sort((a, b) => (a.gw ?? 0)! - (b.gw ?? 0)!);
  const oracle = new Map(decisions.map((d) => [d.gw, d.oracle]));
  for (const row of data) row.oracle = oracle.get(row.gw as number) ?? null;

  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -18 }}>
        <CartesianGrid {...GRID} />
        {flaggedGws.map((gw) => (
          <ReferenceArea
            key={gw}
            x1={gw - 0.5}
            x2={gw + 0.5}
            fill="var(--color-b0)"
            fillOpacity={0.09}
          />
        ))}
        <XAxis dataKey="gw" {...AXIS} />
        <YAxis {...AXIS} />
        <Tooltip {...chartTooltip} />
        <Legend
          wrapperStyle={{ fontSize: 11, paddingTop: 6 }}
          iconType="plainline"
          iconSize={10}
        />
        <Line
          type="monotone"
          dataKey="oracle"
          name="Oracle"
          stroke="var(--color-oracle)"
          strokeWidth={1}
          strokeDasharray="3 3"
          dot={false}
        />
        {MODELS.map((m) => (
          <Line
            key={m.key}
            type="monotone"
            dataKey={m.key}
            name={m.label}
            stroke={m.color}
            strokeWidth={m.key === "B3_v1" ? 2 : 1}
            dot={false}
            opacity={m.key === "B3_v1" || m.key === "B0_xp" ? 1 : 0.6}
          />
        ))}
        <Bar dataKey="__none" fill="transparent" />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
