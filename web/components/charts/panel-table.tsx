"use client";

import Link from "next/link";
import clsx from "clsx";

import { dec, seasonLabel, signed } from "@/lib/format";
import type { Panel } from "@/lib/types";

/**
 * E013's four-season robustness panel. The point of the table is that the
 * qualitative verdicts hold across regimes, so every row is shown even where
 * one season disagrees.
 */
export function PanelTable({ panel, current }: { panel: Panel; current?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] border-collapse text-[11.5px]">
        <thead>
          <tr className="border-b border-edge">
            <th className="label-xs py-2 pr-4 text-left font-normal">Season</th>
            <th className="label-xs py-2 pr-4 text-right font-normal">B0 flagged</th>
            <th className="label-xs py-2 pr-4 text-right font-normal">Tail n</th>
            <th className="label-xs py-2 pr-4 text-right font-normal">Start % @ ≥0.90</th>
            <th className="label-xs py-2 pr-4 text-right font-normal">p90 fitted</th>
            <th className="label-xs py-2 pr-4 text-right font-normal">XI 0-min</th>
            <th className="label-xs py-2 pr-4 text-right font-normal">V1_GW1 − V1</th>
            <th className="label-xs py-2 pr-4 text-right font-normal">V1</th>
            <th className="label-xs py-2 pr-4 text-right font-normal">B1</th>
            <th className="label-xs py-2 text-right font-normal">B2</th>
          </tr>
        </thead>
        <tbody>
          {panel.seasons.map((row) => {
            const v1 = row.xi_cap.B3_v1 ?? null;
            const b1 = row.xi_cap.B1_season_pts ?? null;
            const b2 = row.xi_cap.B2_pp90 ?? null;
            const beatsBoth = v1 != null && b1 != null && b2 != null && v1 > b1 && v1 > b2;
            const zero = row.xi_zero_min.all;

            return (
              <tr
                key={row.season}
                className={clsx(
                  "border-b border-edge/40",
                  row.season === current && "bg-raised/40",
                )}
              >
                <td className="py-2 pr-4">
                  <Link href={`/lab/${row.season}`} className="font-mono hover:text-model">
                    {seasonLabel(row.season)}
                  </Link>
                </td>
                <td className="tnum py-2 pr-4 text-right text-b0">
                  {row.b0_flagged}/{row.b0_total}
                </td>
                <td className="tnum py-2 pr-4 text-right text-faint">{row.tail_n}</td>
                <td className="tnum py-2 pr-4 text-right text-risk">
                  {dec(row.start_pct_at_90, 1)}
                </td>
                <td className="tnum py-2 pr-4 text-right text-risk">
                  {dec(row.p90_fitted, 1)}
                </td>
                <td className="tnum py-2 pr-4 text-right text-risk">
                  {dec(zero?.pct, 1)}%
                  <span className="ml-1 text-[10px] text-faint">
                    {zero?.zero}/{zero?.slots}
                  </span>
                </td>
                <td
                  className={clsx(
                    "tnum py-2 pr-4 text-right",
                    (row.v1_gw1_minus_v1_clean ?? 0) < 0 ? "text-risk" : "text-muted",
                  )}
                >
                  {signed(row.v1_gw1_minus_v1_clean, 2)}
                </td>
                <td
                  className={clsx(
                    "tnum py-2 pr-4 text-right font-semibold",
                    beatsBoth ? "text-actual" : "text-ink",
                  )}
                >
                  {dec(v1, 1)}
                </td>
                <td className="tnum py-2 pr-4 text-right text-faint">{dec(b1, 1)}</td>
                <td className="tnum py-2 text-right text-faint">{dec(b2, 1)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <p className="mt-3 border-l-2 border-edge-bright pl-3 text-[11px] leading-relaxed text-muted">
        {panel.verdict}
      </p>
      <p className="mt-2 pl-3 text-[10.5px] leading-relaxed text-faint">
        {panel.xi_zero_min_source}
      </p>
    </div>
  );
}
