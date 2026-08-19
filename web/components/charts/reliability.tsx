"use client";

import { dec, pct } from "@/lib/format";
import type { Minutes } from "@/lib/types";

const BUCKET_MID: Record<string, number> = {
  "0.90-1.00": 0.95,
  "0.80-0.90": 0.85,
  "0.70-0.80": 0.75,
  "0.60-0.70": 0.65,
  "<0.60": 0.3,
};

/**
 * Claimed p_start against observed start rate. Perfect calibration is the
 * diagonal; every bucket sitting below it is overconfidence.
 */
export function Reliability({ minutes }: { minutes: Minutes }) {
  const buckets = minutes.buckets
    .filter((b) => b.split === "all")
    .map((b) => ({
      ...b,
      claimed: BUCKET_MID[b.bucket] ?? 0,
      observed: (b.start_pct ?? 0) / 100,
    }))
    .sort((a, b) => a.claimed - b.claimed);

  const size = 190;
  const pad = 26;
  const scale = (v: number) => pad + v * (size - pad * 2);
  const yScale = (v: number) => size - pad - v * (size - pad * 2);
  const maxN = Math.max(...buckets.map((b) => b.n ?? 0), 1);

  return (
    <div className="flex flex-wrap items-start gap-5">
      <svg viewBox={`0 0 ${size} ${size}`} className="w-[190px] shrink-0" role="img">
        <line
          x1={pad}
          y1={size - pad}
          x2={size - pad}
          y2={pad}
          stroke="var(--color-edge-bright)"
          strokeDasharray="3 3"
          strokeWidth="1"
        />
        <line x1={pad} y1={size - pad} x2={size - pad} y2={size - pad} stroke="var(--color-edge)" />
        <line x1={pad} y1={pad} x2={pad} y2={size - pad} stroke="var(--color-edge)" />

        {buckets.map((b) => (
          <line
            key={`drop-${b.bucket}`}
            x1={scale(b.claimed)}
            y1={yScale(b.observed)}
            x2={scale(b.claimed)}
            y2={yScale(b.claimed)}
            stroke="var(--color-risk)"
            strokeWidth="1"
            opacity="0.45"
          />
        ))}

        {buckets.map((b) => (
          <circle
            key={b.bucket}
            cx={scale(b.claimed)}
            cy={yScale(b.observed)}
            r={3 + 4 * Math.sqrt((b.n ?? 0) / maxN)}
            fill="var(--color-model)"
            fillOpacity="0.75"
          />
        ))}

        <text x={pad} y={size - 8} fontSize="8" fill="var(--color-faint)">
          claimed →
        </text>
        <text
          x={8}
          y={pad + 4}
          fontSize="8"
          fill="var(--color-faint)"
          transform={`rotate(-90 8 ${pad + 4})`}
        >
          observed →
        </text>
      </svg>

      <table className="min-w-[260px] flex-1 border-collapse text-[11.5px]">
        <thead>
          <tr className="border-b border-edge">
            <th className="label-xs py-1.5 text-left font-normal">p_start</th>
            <th className="label-xs py-1.5 text-right font-normal">n</th>
            <th className="label-xs py-1.5 text-right font-normal">Started</th>
            <th className="label-xs py-1.5 text-right font-normal">0 min</th>
            <th className="label-xs py-1.5 text-right font-normal">Avg pts</th>
          </tr>
        </thead>
        <tbody>
          {[...buckets].reverse().map((b) => {
            const gap = b.claimed - b.observed;
            return (
              <tr key={b.bucket} className="border-b border-edge/40">
                <td className="tnum py-1.5 font-mono text-[11px] text-ink">{b.bucket}</td>
                <td className="tnum py-1.5 text-right text-faint">{b.n}</td>
                <td
                  className={`tnum py-1.5 text-right ${gap > 0.08 ? "text-risk" : "text-muted"}`}
                >
                  {pct(b.observed, 1)}
                </td>
                <td className="tnum py-1.5 text-right text-muted">
                  {dec(b.zero_min_pct, 1)}%
                </td>
                <td className="tnum py-1.5 text-right text-muted">{dec(b.avg_pts, 2)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
