"use client";

import type { PlayerSeries } from "@/lib/types";

/**
 * Projected (cyan line) against actual (bars) across a season. Zero-minute
 * gameweeks are drawn in magenta so blanks read at a glance.
 */
export function TrackRecord({
  series,
  highlight,
  height = 120,
}: {
  series: PlayerSeries;
  highlight?: number;
  height?: number;
}) {
  const points = series.gw.map((gw, i) => ({
    gw,
    mu: series.mu[i] ?? 0,
    pts: series.pts[i],
    mins: series.min[i],
  }));

  if (!points.length) return null;

  const width = 400;
  const pad = { top: 8, right: 4, bottom: 14, left: 4 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;

  const maxY = Math.max(
    4,
    ...points.map((p) => Math.max(p.mu, p.pts ?? 0)),
  );
  const step = innerW / points.length;
  const x = (i: number) => pad.left + i * step + step / 2;
  const y = (v: number) => pad.top + innerH - (v / maxY) * innerH;

  const line = points
    .map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.mu).toFixed(1)}`)
    .join(" ");

  const barW = Math.max(1.5, step * 0.55);

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      role="img"
      aria-label="Projected versus actual points by gameweek"
    >
      <line
        x1={pad.left}
        y1={pad.top + innerH}
        x2={width - pad.right}
        y2={pad.top + innerH}
        stroke="var(--color-edge)"
        strokeWidth="1"
      />

      {points.map((p, i) => {
        if (p.pts == null) return null;
        const blank = p.mins === 0;
        const top = y(p.pts);
        return (
          <rect
            key={p.gw}
            x={x(i) - barW / 2}
            y={top}
            width={barW}
            height={Math.max(0.5, pad.top + innerH - top)}
            rx={1}
            fill={blank ? "var(--color-risk)" : "var(--color-actual)"}
            opacity={highlight === p.gw ? 1 : 0.55}
          />
        );
      })}

      <path d={line} fill="none" stroke="var(--color-model)" strokeWidth="1.5" />

      {highlight != null && points.some((p) => p.gw === highlight) && (
        <line
          x1={x(points.findIndex((p) => p.gw === highlight))}
          y1={pad.top}
          x2={x(points.findIndex((p) => p.gw === highlight))}
          y2={pad.top + innerH}
          stroke="var(--color-ink)"
          strokeWidth="0.75"
          strokeDasharray="2 2"
          opacity="0.5"
        />
      )}

      <text x={pad.left} y={height - 2} fill="var(--color-faint)" fontSize="9">
        GW{points[0].gw}
      </text>
      <text
        x={width - pad.right}
        y={height - 2}
        fill="var(--color-faint)"
        fontSize="9"
        textAnchor="end"
      >
        GW{points.at(-1)?.gw}
      </text>
    </svg>
  );
}
