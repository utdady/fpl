"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AXIS, GRID, chartTooltip } from "./theme";
import type { DecisionGw } from "@/lib/types";

const PARTS = [
  { key: "r_squad", label: "Squad", color: "var(--color-oracle)" },
  { key: "r_xi", label: "XI", color: "var(--color-b0)" },
  { key: "r_cap", label: "Captain", color: "var(--color-risk)" },
];

/**
 * R_total = R_squad + R_XI + R_cap = P(oracle) - P(V1 realized). The oracle is
 * named in the section subtitle, per FORMAL.md.
 */
export function RegretChart({ decisions }: { decisions: DecisionGw[] }) {
  const data = decisions.map((d) => ({
    gw: d.gw,
    r_squad: d.r_squad,
    r_xi: d.r_xi,
    r_cap: d.r_cap,
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -18 }}>
        <CartesianGrid {...GRID} />
        <XAxis dataKey="gw" {...AXIS} />
        <YAxis {...AXIS} />
        <Tooltip {...chartTooltip} />
        <Legend wrapperStyle={{ fontSize: 11, paddingTop: 6 }} iconType="square" iconSize={9} />
        {PARTS.map((p) => (
          <Bar key={p.key} dataKey={p.key} name={p.label} stackId="r" fill={p.color} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Season-level share of the three regret components. */
export function RegretShare({ decisions }: { decisions: DecisionGw[] }) {
  const totals = PARTS.map((p) => ({
    ...p,
    value: decisions.reduce(
      (sum, d) => sum + ((d[p.key as keyof DecisionGw] as number | null) ?? 0),
      0,
    ),
  }));
  const total = totals.reduce((s, t) => s + t.value, 0);
  if (total <= 0) return null;

  return (
    <div className="mt-4">
      <div className="flex h-2 overflow-hidden rounded-full bg-raised">
        {totals.map((t) => (
          <div key={t.key} style={{ width: `${(t.value / total) * 100}%`, background: t.color }} />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1">
        {totals.map((t) => (
          <span key={t.key} className="tnum text-[11px] text-muted">
            <span
              className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle"
              style={{ background: t.color }}
            />
            {t.label} {((t.value / total) * 100).toFixed(1)}%
          </span>
        ))}
      </div>
    </div>
  );
}
