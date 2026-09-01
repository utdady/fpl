"use client";

import type { Position } from "@/lib/types";
import { pct } from "@/lib/format";

type Point = {
  id: number;
  name: string;
  pos: Position;
  p0: number;
  p10: number;
  mu: number;
  highlight?: boolean;
};

export function BoomQuadrant({
  points,
  onSelect,
}: {
  points: Point[];
  onSelect?: (id: number) => void;
}) {
  const width = 320;
  const height = 220;
  const pad = { l: 36, r: 12, t: 12, b: 28 };
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;
  const x = (p10: number) => pad.l + p10 * innerW;
  const y = (p0: number) => pad.t + (1 - p0) * innerH;

  const midX = x(0.12);
  const midY = y(0.35);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full max-w-md" role="img">
      <rect x={pad.l} y={pad.t} width={innerW} height={innerH} fill="var(--color-raised)" opacity={0.35} />
      <line x1={midX} y1={pad.t} x2={midX} y2={pad.t + innerH} stroke="var(--color-edge)" strokeDasharray="3 3" />
      <line x1={pad.l} y1={midY} x2={pad.l + innerW} y2={midY} stroke="var(--color-edge)" strokeDasharray="3 3" />
      <text x={pad.l + 4} y={pad.t + 10} className="fill-faint text-[8px]">
        high blank risk
      </text>
      <text x={pad.l + innerW - 4} y={pad.t + innerH - 6} textAnchor="end" className="fill-faint text-[8px]">
        P(10+)
      </text>
      {points.map((p) => (
        <g key={p.id}>
          <circle
            cx={x(p.p10)}
            cy={y(p.p0)}
            r={p.highlight ? 5 : 3.5}
            fill={p.highlight ? "var(--color-model)" : "var(--color-model)"}
            opacity={p.highlight ? 1 : 0.55}
            className={onSelect ? "cursor-pointer" : undefined}
            onClick={() => onSelect?.(p.id)}
          />
          {p.highlight && (
            <text x={x(p.p10) + 6} y={y(p.p0) + 3} className="fill-ink text-[9px]">
              {p.name}
            </text>
          )}
        </g>
      ))}
      <text x={width / 2} y={height - 6} textAnchor="middle" className="fill-muted text-[9px]">
        {points.length} players · median split P(10+)≈12%, P(0)≈35%
      </text>
    </svg>
  );
}

export function quadrantLabel(p0: number, p10: number) {
  const boom = p10 >= 0.12;
  const bust = p0 >= 0.35;
  if (boom && !bust) return "boom-leaning";
  if (!boom && bust) return "bust-leaning";
  if (boom && bust) return "volatile";
  return "steady";
}

export function QuadrantLegend() {
  return (
    <p className="text-[10px] leading-relaxed text-faint">
      Axes: sim P(0) vs P(10+). Not 1 − p_start — a nailed starter who blanks is the
      E009 failure mode.
    </p>
  );
}
