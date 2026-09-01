"use client";

import { dec } from "@/lib/format";

/** Step chart from sim quantiles — not a fitted Normal. */
export function OutcomeDistribution({
  quantiles,
  actual,
  mu,
}: {
  quantiles: [number, number, number, number, number];
  actual?: number | null;
  mu?: number | null;
}) {
  const [q05, q25, q50, q75, q95] = quantiles;
  const width = 360;
  const height = 100;
  const pad = { l: 8, r: 8, t: 8, b: 22 };
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;
  const maxX = Math.max(12, q95, actual ?? 0, mu ?? 0) * 1.15;
  const x = (v: number) => pad.l + (v / maxX) * innerW;

  const steps: [number, number][] = [
    [0, q05],
    [q05, q25],
    [q25, q50],
    [q50, q75],
    [q75, q95],
    [q95, maxX],
  ];

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img">
      <line
        x1={pad.l}
        y1={pad.t + innerH}
        x2={width - pad.r}
        y2={pad.t + innerH}
        stroke="var(--color-edge)"
      />
      {steps.map(([a, b], i) => (
        <rect
          key={i}
          x={x(a)}
          y={pad.t + 12}
          width={Math.max(1, x(b) - x(a))}
          height={innerH - 24}
          fill="var(--color-model)"
          opacity={0.12 + i * 0.06}
        />
      ))}
      {[q05, q25, q50, q75, q95].map((q, i) => (
        <g key={i}>
          <line
            x1={x(q)}
            y1={pad.t + 8}
            x2={x(q)}
            y2={pad.t + innerH}
            stroke="var(--color-model)"
            strokeWidth={i === 2 ? 1.5 : 0.75}
            opacity={i === 2 ? 0.9 : 0.45}
          />
          <text
            x={x(q)}
            y={height - 4}
            textAnchor="middle"
            className="fill-faint text-[8px]"
          >
            {i === 0 ? "5%" : i === 1 ? "25%" : i === 2 ? "50%" : i === 3 ? "75%" : "95%"}
          </text>
        </g>
      ))}
      {mu != null && (
        <circle cx={x(mu)} cy={pad.t + innerH / 2} r={3} fill="var(--color-model)" />
      )}
      {actual != null && (
        <circle cx={x(actual)} cy={pad.t + innerH / 2} r={3.5} fill="var(--color-actual)" />
      )}
      <text x={pad.l} y={pad.t + 6} className="fill-muted text-[9px]">
        median {dec(q50, 1)} · μ {dec(mu, 1)}
        {actual != null ? ` · actual ${actual}` : ""}
      </text>
    </svg>
  );
}
