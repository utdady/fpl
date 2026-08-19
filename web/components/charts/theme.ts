import type { CSSProperties } from "react";

export const AXIS = {
  stroke: "var(--color-edge-bright)",
  tick: { fill: "var(--color-faint)", fontSize: 10 },
  tickLine: false,
  axisLine: { stroke: "var(--color-edge)" },
} as const;

export const GRID = {
  stroke: "var(--color-edge)",
  strokeDasharray: "2 4",
  vertical: false,
} as const;

const tooltipStyle: CSSProperties = {
  background: "var(--color-panel)",
  border: "1px solid var(--color-edge-bright)",
  borderRadius: 8,
  fontSize: 11,
  padding: "8px 10px",
};

export const chartTooltip = {
  contentStyle: tooltipStyle,
  labelStyle: { color: "var(--color-ink)", marginBottom: 4, fontSize: 11 },
  itemStyle: { padding: 0 },
  cursor: { stroke: "var(--color-edge-bright)", strokeWidth: 1 },
} as const;
