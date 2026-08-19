"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AXIS, GRID, chartTooltip } from "./theme";
import type { Scores } from "@/lib/types";

/**
 * Player-level MAE and Spearman across the season. The late-season improvement
 * is expected: the snapshot accumulates current-season minutes. It is not
 * evidence that preseason V1 is strong (E005).
 */
export function DriftChart({ scores }: { scores: Scores }) {
  const data = scores.gws.map((g) => ({ gw: g.gw, mae: g.mae, spearman: g.spearman }));

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -18 }}>
        <CartesianGrid {...GRID} />
        <XAxis dataKey="gw" {...AXIS} />
        <YAxis yAxisId="mae" domain={[0, "auto"]} {...AXIS} />
        <YAxis yAxisId="rho" orientation="right" domain={[0, 1]} {...AXIS} />
        <Tooltip {...chartTooltip} />
        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 6 }} iconType="plainline" iconSize={10} />
        <Line
          yAxisId="mae"
          type="monotone"
          dataKey="mae"
          name="MAE"
          stroke="var(--color-risk)"
          strokeWidth={1.5}
          dot={false}
        />
        <Line
          yAxisId="rho"
          type="monotone"
          dataKey="spearman"
          name="Spearman"
          stroke="var(--color-model)"
          strokeWidth={1.5}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
