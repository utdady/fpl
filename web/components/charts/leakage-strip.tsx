"use client";

import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AXIS, GRID, chartTooltip } from "./theme";
import type { Leakage } from "@/lib/types";

/**
 * Spearman(xP, actual) per gameweek against the threshold pre-registered in
 * E008 before the query was run.
 */
export function LeakageStrip({ leakage }: { leakage: Leakage }) {
  const data = leakage.gws.map((g) => ({ gw: g.gw, spearman: g.spearman, flag: g.flag }));

  return (
    <ResponsiveContainer width="100%" height={190}>
      <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -18 }}>
        <CartesianGrid {...GRID} />
        <XAxis dataKey="gw" {...AXIS} />
        <YAxis domain={[0, 1]} {...AXIS} />
        <Tooltip
          {...chartTooltip}
          formatter={(value) => [Number(value).toFixed(3), "Spearman"]}
        />
        <ReferenceLine
          y={leakage.threshold}
          stroke="var(--color-risk)"
          strokeDasharray="4 3"
          strokeWidth={1}
          label={{
            value: `pre-registered ${leakage.threshold}`,
            fill: "var(--color-risk)",
            fontSize: 9,
            position: "insideTopRight",
          }}
        />
        <Bar dataKey="spearman" radius={[2, 2, 0, 0]}>
          {data.map((d) => (
            <Cell
              key={d.gw}
              fill={d.flag ? "var(--color-b0)" : "var(--color-edge-bright)"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
